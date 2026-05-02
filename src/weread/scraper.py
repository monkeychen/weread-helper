from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import sync_playwright, Page

from weread.auth import load_cookies, save_cookies, ensure_login
from weread.errors import ChapterLoadError

_CHAPTER_CONTENT = ".readerChapterContent"
_FOOTER_BTN = ".readerFooter_button:visible"
_CHAPTER_TITLE = ".readerTopBar_title_link,.readerTopBar_title"
_RENDER_TIMEOUT = 15000
_MAX_RETRY = 1


@dataclass
class ChapterInfo:
    num: int
    name: str
    pdf_path: Path


@dataclass
class ScrapeResult:
    book_name: str
    chapters: list[ChapterInfo] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    temp_dir: str = ""


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
    page: Page, chapter_num: int, temp_dir: str
) -> ChapterInfo:
    chapter_name = _get_chapter_name(page)

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

    pdf_path = Path(temp_dir) / f"chapter_{chapter_num}.pdf"
    page.emulate_media(media="screen")
    page.pdf(
        path=str(pdf_path),
        print_background=True,
        width="800px",
        height="1200px",
        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
    )

    return ChapterInfo(num=chapter_num, name=chapter_name, pdf_path=pdf_path)


def scrape(
    url: str,
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> ScrapeResult:
    temp_dir = tempfile.mkdtemp(prefix="weread_")
    result = ScrapeResult(book_name="", temp_dir=temp_dir)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 800, "height": 1200}
        )
        load_cookies(context)
        page = context.new_page()

        print(f"🔍 正在打开微信读书...")
        page.goto(url, wait_until="domcontentloaded")
        ensure_login(page)
        save_cookies(context)

        result.book_name = _get_book_name(page)
        print(f"📖 开始抓取《{result.book_name}》")

        chapter_num = 1
        while True:
            try:
                info = _capture_chapter(page, chapter_num, temp_dir)
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
