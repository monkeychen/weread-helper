from __future__ import annotations

import hashlib
import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, Page, BrowserContext

from weread.auth import get_storage_state_path, ensure_login
from weread.errors import ChapterLoadError

_CHAPTER_CONTENT = ".readerChapterContent"
_FOOTER_BTN = ".readerFooter_button:visible"
_CHAPTER_TITLE = ".readerTopBar_title_link,.readerTopBar_title"
_RENDER_TIMEOUT = 15000
_MAX_RETRY = 1

_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
]
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# Injected before page scripts run — intercepts fillText (text) and drawImage (images)
_CANVAS_INTERCEPT = """
window.__wr_text_log__ = [];
window.__wr_img_log__ = [];

const _origFill = CanvasRenderingContext2D.prototype.fillText;
CanvasRenderingContext2D.prototype.fillText = function(text, x, y) {
    if (text && text.trim().length > 0) {
        const width = Math.round(this.measureText(text).width);
        window.__wr_text_log__.push([String(text), Math.round(x), Math.round(y), width]);
    }
    return _origFill.apply(this, arguments);
};

const _origDraw = CanvasRenderingContext2D.prototype.drawImage;
CanvasRenderingContext2D.prototype.drawImage = function() {
    const src = arguments[0];
    let imgUrl = null;
    if (src instanceof HTMLImageElement) {
        imgUrl = src.currentSrc || src.src || null;
    }
    if (imgUrl && !imgUrl.startsWith('data:')) {
        const nArgs = arguments.length;
        const dy = nArgs >= 9 ? arguments[6] : (nArgs >= 3 ? arguments[2] : 0);
        window.__wr_img_log__.push([imgUrl, Math.round(dy || 0)]);
    }
    return _origDraw.apply(this, arguments);
};
"""

# Font-test line WeRead draws on every page load (used to measure glyph widths)
_FONT_TEST_PREFIX = "abcdefghijklmnopqrstuvwxyz"


def _text_fingerprint(s: str) -> str:
    """Normalize text for fuzzy comparison — strip whitespace, punctuation, case."""
    return re.sub(r'[^\w]', '', s, flags=re.UNICODE).lower()


def _download_image(context: BrowserContext, src: str, images_dir: Path) -> Optional[str]:
    """Download an image using the browser's authenticated session; return filename or None."""
    try:
        response = context.request.get(src, timeout=10000)
        if not response.ok:
            return None
        parsed = urlparse(src)
        fname = Path(parsed.path).name
        if not fname or "." not in fname:
            fname = hashlib.md5(src.encode()).hexdigest()[:16] + ".jpg"
        local_path = images_dir / fname
        local_path.write_bytes(response.body())
        return fname
    except Exception:
        return None


def _join_line_fragments(frags: list[tuple[str, int, int, int]]) -> str:
    """Join canvas fillText fragments on the same Y line, inserting spaces at X gaps."""
    if not frags:
        return ""
    if len(frags) == 1:
        return frags[0][0]
    parts = [frags[0][0]]
    prev_end = frags[0][1] + frags[0][3]  # x + w
    for text, x, _y, w in frags[1:]:
        gap = x - prev_end
        if gap > 2:
            parts.append(" ")
        parts.append(text)
        prev_end = x + w
    return "".join(parts)


def _collect_chapter_content(
    page: Page,
    text_start: int = 0,
    img_start: int = 0,
    images_dir: Optional[Path] = None,
) -> str:
    """Scroll to trigger all canvas renders, extract text + images, return markdown string."""
    page.evaluate("""async () => {
        const h = document.documentElement.scrollHeight;
        const step = 400;
        for (let y = 0; y < h; y += step) {
            window.scrollTo(0, y);
            await new Promise(r => setTimeout(r, 80));
        }
        window.scrollTo(0, 0);
    }""")
    page.wait_for_timeout(1000)

    # --- Text: filter font-test block, group by Y (±4px), sort by X ---
    all_text = page.evaluate("window.__wr_text_log__") or []
    raw_text = all_text[text_start:]

    entries = []
    skip = True
    for item in raw_text:
        if len(item) >= 4:
            text, x, y, w = item[0], item[1], item[2], item[3]
        else:
            text, x, y, w = item[0], item[1], item[2], 0
        if skip:
            if text == "a" or text.startswith(_FONT_TEST_PREFIX):
                continue
            skip = False
        entries.append((text, x, y, w))

    text_lines: list[tuple[str, int, int]] = []  # (line_text, line_y, start_x)
    if entries:
        entries.sort(key=lambda e: (e[2], e[1]))
        cur_line: list[tuple[str, int, int, int]] = []  # (text, x, y, w)
        cur_y = entries[0][2]
        for text, x, y, w in entries:
            if abs(y - cur_y) > 4:
                if cur_line:
                    cur_line.sort(key=lambda e: e[1])
                    joined = _join_line_fragments(cur_line)
                    if not joined.startswith(_FONT_TEST_PREFIX):
                        text_lines.append((joined, cur_y, cur_line[0][1]))
                cur_line = [(text, x, y, w)]
                cur_y = y
            else:
                cur_line.append((text, x, y, w))
        if cur_line:
            cur_line.sort(key=lambda e: e[1])
            joined = _join_line_fragments(cur_line)
            if not joined.startswith(_FONT_TEST_PREFIX):
                text_lines.append((joined, cur_y, cur_line[0][1]))

    # --- Canvas top offset: convert canvas-local Y to document Y ---
    canvas_top: int = page.evaluate("""() => {
        const canvases = Array.from(document.querySelectorAll('canvas'));
        if (!canvases.length) return 0;
        const best = canvases.reduce((a, b) =>
            (a.width * a.height > b.width * b.height) ? a : b);
        return Math.round(best.getBoundingClientRect().top + window.scrollY);
    }""")

    # --- Images: DOM query (primary) + canvas drawImage log (fallback) ---
    img_refs: list[tuple[str, int]] = []  # (md_ref, doc_y)
    if images_dir:
        seen_urls: set = set()
        img_candidates: list[tuple[str, int]] = []  # (url, doc_y)

        # Primary: DOM <img> elements inside the reader (reliable for WeRead)
        dom_imgs = page.evaluate("""() => {
            function isInContentFlow(el) {
                // Skip images inside fixed/sticky containers (top bar, sidebars)
                let node = el;
                while (node && node !== document.body) {
                    const pos = window.getComputedStyle(node).position;
                    if (pos === 'fixed' || pos === 'sticky') return false;
                    node = node.parentElement;
                }
                return true;
            }
            function isUIAsset(src) {
                // Webpack-hashed static assets (e.g. loading_dark.41a70b39.png)
                if (/\\.[0-9a-f]{8}\\.[a-z]+$/.test(src)) return true;
                // Explicit loading / spinner patterns
                if (/loading|spinner|placeholder/i.test(src)) return true;
                return false;
            }
            // Prefer scoped query; fall back to all imgs if container not found
            let imgs = document.querySelectorAll(
                '.readerChapterContent img, .reader_main img, .readerContent img');
            if (!imgs.length) {
                imgs = document.querySelectorAll('img[src]');
            }
            return Array.from(imgs)
                .filter(img =>
                    img.naturalWidth > 80 &&
                    img.naturalHeight > 80 &&
                    img.src && !img.src.startsWith('data:') &&
                    !isUIAsset(img.src) &&
                    isInContentFlow(img))
                .map(img => ({
                    url: img.src,
                    y: Math.round(img.getBoundingClientRect().top + window.scrollY)
                }));
        }""") or []
        for item in dom_imgs:
            url = item["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                img_candidates.append((url, item["y"]))

        # Fallback: canvas drawImage intercept (catches canvas-rendered images)
        all_imgs = page.evaluate("window.__wr_img_log__") or []
        raw_imgs = all_imgs[img_start:]
        seen_canvas: set = set()
        for url, canvas_y in raw_imgs:
            key = (url, canvas_y // 50)
            if key in seen_canvas:
                continue
            seen_canvas.add(key)
            if url not in seen_urls:
                seen_urls.add(url)
                img_candidates.append((url, canvas_top + canvas_y))

        for url, doc_y in img_candidates:
            fname = _download_image(page.context, url, images_dir)
            if fname:
                img_refs.append((f"![](images/{fname})", doc_y))

    # Convert text line Y to document space for merging with images
    text_lines_doc = [(text, canvas_top + y, sx) for text, y, sx in text_lines]

    if not text_lines_doc and not img_refs:
        return ""

    # --- Paragraph detection: X-indent (primary) + Y-gap (fallback) ---
    start_xs = [sx for _, _, sx in text_lines_doc]
    base_x = min(start_xs) if start_xs else 0
    indent_threshold = 15

    line_ys = sorted(set(y for _, y, _ in text_lines_doc))
    if len(line_ys) >= 3:
        gaps = sorted(b - a for a, b in zip(line_ys, line_ys[1:]) if b > a)
        median_gap = gaps[len(gaps) // 2]
        y_para_threshold = median_gap * 3
    else:
        y_para_threshold = 100

    # Merge text and images by document Y
    all_items: list[tuple[int, str, bool, int]] = (
        [(y, text, False, sx) for text, y, sx in text_lines_doc]
        + [(y, ref, True, 0) for ref, y in img_refs]
    )
    all_items.sort(key=lambda x: x[0])

    result: list[str] = []
    prev_text_y: Optional[int] = None
    for y, content, is_img, start_x in all_items:
        if is_img:
            if result and result[-1] != "":
                result.append("")
            result.append(content)
            result.append("")
            prev_text_y = None
        else:
            is_paragraph_start = False
            # Primary: indent detection
            if start_x > base_x + indent_threshold:
                is_paragraph_start = True
            # Fallback: large Y gap
            if prev_text_y is not None and (y - prev_text_y) > y_para_threshold:
                is_paragraph_start = True
            if is_paragraph_start and result and result[-1] != "":
                result.append("")
            result.append(content)
            prev_text_y = y

    # Strip trailing blank lines
    while result and result[-1] == "":
        result.pop()

    return "\n".join(result)


def _wait_for_render(page: Page) -> None:
    page.wait_for_selector(_CHAPTER_CONTENT, timeout=_RENDER_TIMEOUT)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)


def _get_chapter_name(page: Page) -> str:
    el = page.query_selector(_CHAPTER_TITLE)
    if el:
        return el.inner_text().strip()
    return ""


def _get_book_name(page: Page) -> str:
    title = page.title()
    parts = title.split("-")
    if len(parts) >= 2:
        return parts[0].strip()
    return title.strip()


def _has_next_chapter(page: Page) -> bool:
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(800)

    btn = page.locator(_FOOTER_BTN)
    if btn.count() > 0:
        text = btn.first.inner_text()
        if "下一" in text:
            btn.first.click()
            return True
        return False

    text_btn = page.locator("text='下一章'")
    if text_btn.count() > 0 and text_btn.first.is_visible():
        text_btn.first.click()
        return True

    return False


def _capture_chapter(
    page: Page, chapter_num: int, temp_dir: str, images_dir: Path, book_name: str = ""
) -> ChapterInfo:
    chapter_name = _get_chapter_name(page)

    # The top bar element may contain both book name and chapter title on separate lines.
    # Extract just the chapter title (the line that's not the book name).
    if chapter_name and '\n' in chapter_name:
        book_fp = _text_fingerprint(book_name)
        non_book = [
            l.strip() for l in chapter_name.split('\n')
            if l.strip() and _text_fingerprint(l.strip()) != book_fp
        ]
        if non_book:
            chapter_name = non_book[0]

    # Record log positions BEFORE render so initial viewport draws are captured
    text_start = page.evaluate("window.__wr_text_log__.length")
    img_start = page.evaluate("window.__wr_img_log__.length")

    for attempt in range(_MAX_RETRY + 1):
        try:
            _wait_for_render(page)
            break
        except Exception:
            if attempt == _MAX_RETRY:
                raise ChapterLoadError(
                    chapter_num, chapter_name, "渲染超时，重试后仍失败"
                )
            page.reload()
            text_start = 0  # init script reinitialises logs on full reload
            img_start = 0

    text = _collect_chapter_content(
        page,
        text_start=text_start,
        img_start=img_start,
        images_dir=images_dir,
    )

    # WeRead top bar shows the book title, not the chapter title.
    # Always try to extract the real chapter title from text content.
    book_fp = _text_fingerprint(book_name)
    if text and (not chapter_name or _text_fingerprint(chapter_name) == book_fp):
        lines = text.split("\n")
        consumed = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("!["):
                continue
            if _text_fingerprint(stripped) == book_fp:
                continue
            chapter_name = stripped
            consumed = i + 1
            break

        if consumed:
            body_lines = lines[consumed:]
            # Remove duplicate chapter title (e.g. Chinese+English combined line)
            while body_lines:
                first = body_lines[0].strip()
                if not first:
                    body_lines.pop(0)
                    continue
                if first.startswith(chapter_name) and first != chapter_name:
                    body_lines.pop(0)
                    while body_lines and not body_lines[0].strip():
                        body_lines.pop(0)
                else:
                    break
            text = "\n".join(body_lines)

    pdf_path = Path(temp_dir) / f"chapter_{chapter_num}.pdf"
    page.emulate_media(media="screen")
    scroll_height = page.evaluate("document.documentElement.scrollHeight")
    page.pdf(
        path=str(pdf_path),
        print_background=True,
        width="800px",
        height=f"{scroll_height}px",
        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
    )

    return ChapterInfo(num=chapter_num, name=chapter_name, pdf_path=pdf_path, text=text)


@dataclass
class ChapterInfo:
    num: int
    name: str
    pdf_path: Path
    text: str = ""


@dataclass
class ScrapeResult:
    book_name: str
    chapters: list[ChapterInfo] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    temp_dir: str = ""


def scrape(
    url: str,
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> ScrapeResult:
    logging.getLogger("pdfminer").setLevel(logging.ERROR)

    temp_dir = tempfile.mkdtemp(prefix="weread_")
    images_dir = Path(temp_dir) / "images"
    images_dir.mkdir()
    result = ScrapeResult(book_name="", temp_dir=temp_dir)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",
            args=_BROWSER_ARGS,
        )

        state_path = get_storage_state_path()
        context_kwargs: dict = {
            "viewport": {"width": 800, "height": 1200},
            "user_agent": _USER_AGENT,
        }
        if state_path:
            context_kwargs["storage_state"] = str(state_path)

        context = browser.new_context(**context_kwargs)
        context.add_init_script(_CANVAS_INTERCEPT)
        page = context.new_page()

        print("🔍 正在打开微信读书...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        ensure_login(page)

        result.book_name = _get_book_name(page)
        print(f"📖 开始抓取《{result.book_name}》")

        chapter_num = 1
        while True:
            try:
                info = _capture_chapter(page, chapter_num, temp_dir, images_dir, result.book_name)
                result.chapters.append(info)
                display_name = info.name or f"第{chapter_num}章"
                if on_progress:
                    on_progress(chapter_num, display_name)
                else:
                    print(f"   [{chapter_num}] {display_name} ✓")
            except ChapterLoadError as e:
                result.skipped.append(str(e))
                print(f"   [{chapter_num}] ⚠ 跳过: {e}")

            if not _has_next_chapter(page):
                break
            chapter_num += 1

        browser.close()

    return result
