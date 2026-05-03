# weread-scrapy Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the single-file weread scraper into an installable CLI tool (`weread`) with multi-format output (PDF/EPUB/Markdown), cookie expiry detection, and robust error handling.

**Architecture:** src-layout Python package with 4 core modules (auth, scraper, converter, cli) behind a `pyproject.toml` build config. Playwright drives headless-capable Chromium for scraping, PyPDF2/ebooklib/pdfplumber handle format conversion. CLI entry point registered via `[project.scripts]`.

**Tech Stack:** Python >=3.9, Playwright, PyPDF2, ebooklib, pdfplumber, argparse

**Spec:** `docs/superpowers/specs/2026-05-02-weread-refactor-design.md`

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Build config, dependencies, CLI entry point |
| `.gitignore` | Ignore venv, temp files, cookies, build artifacts |
| `src/weread/__init__.py` | Package version |
| `src/weread/errors.py` | Custom exception hierarchy |
| `src/weread/utils.py` | Path sanitization, book name extraction |
| `src/weread/auth.py` | Cookie storage, load, expiry detection, login flow |
| `src/weread/scraper.py` | Browser control, chapter-by-chapter PDF capture |
| `src/weread/converter.py` | Merge PDFs, generate EPUB, generate Markdown |
| `src/weread/cli.py` | argparse CLI, progress display, error presentation |
| `tests/test_utils.py` | Tests for path sanitization and name extraction |
| `tests/test_converter.py` | Tests for PDF merge, EPUB generation, Markdown extraction |
| `README.md` | Installation, usage, development instructions |

---

## Task 1: Project scaffolding — git, .gitignore, pyproject.toml, package skeleton

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `src/weread/__init__.py`
- Delete: `requirements.txt` (replaced by pyproject.toml)
- Delete: `venv/` (users will create their own)
- Delete: `scraper.py` (will be replaced by src/weread/scraper.py)
- Delete: `.playwright_state.json` (cookies move to ~/.weread/)
- Delete: `temp_pdfs/` and `book.pdf` (build artifacts)

- [ ] **Step 1: Create .gitignore**

```gitignore
__pycache__/
*.pyc
*.egg-info/
dist/
build/
venv/
.venv/
.playwright_state.json
temp_pdfs/
*.pdf
.DS_Store
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "weread-scrapy"
version = "0.1.0"
description = "Export books from WeRead (微信读书) as PDF, EPUB, or Markdown"
readme = "README.md"
requires-python = ">=3.9"
license = "MIT"
dependencies = [
    "playwright>=1.43",
    "PyPDF2>=3.0",
    "ebooklib>=0.18",
    "pdfplumber>=0.10",
]

[project.scripts]
weread = "weread.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/weread"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Create src/weread/__init__.py**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Remove old files**

```bash
rm -rf venv requirements.txt .playwright_state.json temp_pdfs book.pdf scraper.py .DS_Store
```

- [ ] **Step 5: Create empty module files as placeholders**

Create empty files so the package is importable:
- `src/weread/errors.py`
- `src/weread/utils.py`
- `src/weread/auth.py`
- `src/weread/scraper.py`
- `src/weread/converter.py`
- `src/weread/cli.py`
- `tests/__init__.py`
- `tests/test_utils.py`
- `tests/test_converter.py`

- [ ] **Step 6: Initialize venv and install in dev mode**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" 2>/dev/null || pip install -e .
playwright install chromium
```

Verify: `python -c "from weread import __version__; print(__version__)"` should print `0.1.0`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore pyproject.toml src/ tests/
git commit -m "scaffold: init package structure with pyproject.toml and src layout"
```

---

## Task 2: errors.py — custom exception hierarchy

**Files:**
- Create: `src/weread/errors.py`

- [ ] **Step 1: Write errors.py**

```python
class WereadError(Exception):
    """Base exception for all weread errors."""

class LoginExpiredError(WereadError):
    """Cookie expired and user did not complete login."""

class ChapterLoadError(WereadError):
    """Chapter failed to render within timeout."""
    def __init__(self, chapter_num: int, chapter_name: str, reason: str):
        self.chapter_num = chapter_num
        self.chapter_name = chapter_name
        super().__init__(f"Chapter {chapter_num} ({chapter_name}): {reason}")

class ConvertError(WereadError):
    """Format conversion failed."""
    def __init__(self, format_name: str, reason: str):
        self.format_name = format_name
        super().__init__(f"Failed to convert to {format_name}: {reason}")
```

- [ ] **Step 2: Verify import**

Run: `python -c "from weread.errors import WereadError, LoginExpiredError, ChapterLoadError, ConvertError; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/weread/errors.py
git commit -m "feat: add custom exception hierarchy"
```

---

## Task 3: utils.py — path sanitization and book name helpers

**Files:**
- Create: `src/weread/utils.py`
- Create: `tests/test_utils.py`

- [ ] **Step 1: Write failing tests for sanitize_filename**

```python
# tests/test_utils.py
from weread.utils import sanitize_filename


def test_sanitize_normal_name():
    assert sanitize_filename("认知觉醒") == "认知觉醒"


def test_sanitize_strips_illegal_chars():
    assert sanitize_filename('认知/觉醒:第一版') == "认知_觉醒_第一版"


def test_sanitize_strips_whitespace():
    assert sanitize_filename("  认知觉醒  ") == "认知觉醒"


def test_sanitize_collapses_underscores():
    assert sanitize_filename("a///b") == "a_b"


def test_sanitize_empty_string():
    assert sanitize_filename("") == "untitled"


def test_sanitize_only_illegal_chars():
    assert sanitize_filename("///") == "untitled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_utils.py -v`
Expected: FAIL — `ImportError: cannot import name 'sanitize_filename'`

- [ ] **Step 3: Implement utils.py**

```python
import re
from pathlib import Path

_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_UNDERSCORE = re.compile(r'_+')


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = _ILLEGAL_CHARS.sub("_", name)
    name = _MULTI_UNDERSCORE.sub("_", name)
    name = name.strip("_")
    return name if name else "untitled"


def get_cookie_path() -> Path:
    path = Path.home() / ".weread" / "cookies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_output_dir(book_name: str, base_dir: str | None = None) -> Path:
    safe_name = sanitize_filename(book_name)
    if base_dir:
        out = Path(base_dir) / safe_name
    else:
        out = Path("output") / safe_name
    out.mkdir(parents=True, exist_ok=True)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_utils.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/weread/utils.py tests/test_utils.py
git commit -m "feat: add filename sanitization and path utilities"
```

---

## Task 4: auth.py — login state management with expiry detection

**Files:**
- Create: `src/weread/auth.py`

- [ ] **Step 1: Write auth.py**

```python
import json
from pathlib import Path

from playwright.sync_api import Page, BrowserContext

from weread.errors import LoginExpiredError
from weread.utils import get_cookie_path

_LOGIN_INDICATOR = ".login_dialog_qrcode,.wr_login_dialog_qrcode,.navBar_link_Login"
_READER_CONTENT = ".readerChapterContent,.app_content"
_LOGIN_WAIT_INTERVAL = 2000


def load_cookies(context: BrowserContext) -> bool:
    cookie_path = get_cookie_path()
    if not cookie_path.exists():
        return False
    try:
        state = json.loads(cookie_path.read_text(encoding="utf-8"))
        context.add_cookies(state.get("cookies", []))
        return True
    except (json.JSONDecodeError, KeyError):
        return False


def save_cookies(context: BrowserContext) -> None:
    cookie_path = get_cookie_path()
    state = context.storage_state()
    cookie_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _is_login_required(page: Page) -> bool:
    try:
        page.wait_for_selector(_READER_CONTENT, timeout=8000)
        return False
    except Exception:
        login_el = page.query_selector(_LOGIN_INDICATOR)
        return login_el is not None


def ensure_login(page: Page) -> bool:
    if not _is_login_required(page):
        return True

    print("⚠️  检测到登录态已过期，请扫码登录")
    try:
        answer = input("   扫码完成后按 Enter 继续（Ctrl+C 取消）...")
    except (KeyboardInterrupt, EOFError):
        raise LoginExpiredError("用户取消了登录")

    page.reload()
    page.wait_for_selector(_READER_CONTENT, timeout=15000)

    save_cookies(page.context)
    return True
```

- [ ] **Step 2: Verify import**

Run: `python -c "from weread.auth import ensure_login, load_cookies, save_cookies; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/weread/auth.py
git commit -m "feat: add login state management with cookie expiry detection"
```

---

## Task 5: scraper.py — chapter-by-chapter book scraping

**Files:**
- Create: `src/weread/scraper.py`

- [ ] **Step 1: Write scraper.py**

```python
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
```

- [ ] **Step 2: Verify import**

Run: `python -c "from weread.scraper import scrape, ScrapeResult; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/weread/scraper.py
git commit -m "feat: add chapter-by-chapter scraper with retry and progress"
```

---

## Task 6: converter.py — PDF merge, EPUB and Markdown generation

**Files:**
- Create: `src/weread/converter.py`
- Create: `tests/test_converter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_converter.py
import os
import tempfile
from pathlib import Path

from PyPDF2 import PdfWriter
import pytest

from weread.converter import merge_pdfs, convert_to_markdown, convert_to_epub
from weread.scraper import ChapterInfo, ScrapeResult


def _make_dummy_pdf(path: Path, text: str = "hello") -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300)
    with open(path, "wb") as f:
        writer.write(f)


def _make_result(tmp_path: Path, count: int = 3) -> ScrapeResult:
    chapters = []
    for i in range(1, count + 1):
        pdf = tmp_path / f"chapter_{i}.pdf"
        _make_dummy_pdf(pdf)
        chapters.append(ChapterInfo(num=i, name=f"第{i}章", pdf_path=pdf))
    return ScrapeResult(
        book_name="测试书名", chapters=chapters, temp_dir=str(tmp_path)
    )


class TestMergePdfs:
    def test_merge_creates_file(self, tmp_path):
        result = _make_result(tmp_path)
        out = tmp_path / "out.pdf"
        merge_pdfs(result, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_merge_page_count(self, tmp_path):
        from PyPDF2 import PdfReader

        result = _make_result(tmp_path, count=3)
        out = tmp_path / "out.pdf"
        merge_pdfs(result, out)
        reader = PdfReader(str(out))
        assert len(reader.pages) == 3


class TestConvertToMarkdown:
    def test_creates_md_file(self, tmp_path):
        result = _make_result(tmp_path, count=2)
        out = tmp_path / "book.md"
        convert_to_markdown(result, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "# 第1章" in content
        assert "# 第2章" in content


class TestConvertToEpub:
    def test_creates_epub_file(self, tmp_path):
        result = _make_result(tmp_path, count=2)
        out = tmp_path / "book.epub"
        convert_to_epub(result, out)
        assert out.exists()
        assert out.stat().st_size > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_converter.py -v`
Expected: FAIL — `ImportError: cannot import name 'merge_pdfs'`

- [ ] **Step 3: Implement converter.py**

```python
from pathlib import Path

import pdfplumber
import PyPDF2
from ebooklib import epub

from weread.scraper import ScrapeResult
from weread.errors import ConvertError


def merge_pdfs(result: ScrapeResult, output_path: Path) -> None:
    try:
        merger = PyPDF2.PdfMerger()
        for ch in result.chapters:
            merger.append(str(ch.pdf_path))
        with open(output_path, "wb") as f:
            merger.write(f)
        merger.close()
    except Exception as e:
        raise ConvertError("pdf", str(e)) from e


def _extract_text(pdf_path: Path) -> str:
    text_parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n\n".join(text_parts)


def convert_to_markdown(result: ScrapeResult, output_path: Path) -> None:
    try:
        lines = [f"# {result.book_name}\n"]
        for ch in result.chapters:
            lines.append(f"# {ch.name}\n")
            text = _extract_text(ch.pdf_path)
            lines.append(text if text else "(此章无可提取文本)")
            lines.append("")
        output_path.write_text("\n".join(lines), encoding="utf-8")
    except ConvertError:
        raise
    except Exception as e:
        raise ConvertError("markdown", str(e)) from e


def convert_to_epub(result: ScrapeResult, output_path: Path) -> None:
    try:
        book = epub.EpubBook()
        book.set_identifier(f"weread-{result.book_name}")
        book.set_title(result.book_name)
        book.set_language("zh")

        chapters_epub = []
        for ch in result.chapters:
            text = _extract_text(ch.pdf_path)
            content = text.replace("\n", "<br/>") if text else "<p>此章无可提取文本</p>"

            c = epub.EpubHtml(
                title=ch.name,
                file_name=f"chapter_{ch.num}.xhtml",
                lang="zh",
            )
            c.content = f"<h1>{ch.name}</h1><p>{content}</p>"
            book.add_item(c)
            chapters_epub.append(c)

        book.toc = chapters_epub
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav"] + chapters_epub

        epub.write_epub(str(output_path), book)
    except ConvertError:
        raise
    except Exception as e:
        raise ConvertError("epub", str(e)) from e


def convert(
    result: ScrapeResult,
    formats: list[str],
    output_dir: Path,
) -> dict[str, Path]:
    safe_name = result.book_name or "book"
    outputs: dict[str, Path] = {}

    for fmt in formats:
        out_path = output_dir / f"{safe_name}.{fmt}"
        try:
            if fmt == "pdf":
                print(f"📦 生成 PDF...")
                merge_pdfs(result, out_path)
            elif fmt == "epub":
                print(f"📦 生成 EPUB...")
                convert_to_epub(result, out_path)
            elif fmt == "md":
                print(f"📦 生成 Markdown...")
                convert_to_markdown(result, out_path)
            else:
                print(f"⚠ 未知格式: {fmt}，跳过")
                continue
            outputs[fmt] = out_path
            print(f"   ✓ {out_path}")
        except ConvertError as e:
            print(f"   ✗ {fmt} 转换失败: {e}")

    return outputs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_converter.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/weread/converter.py tests/test_converter.py
git commit -m "feat: add PDF/EPUB/Markdown converter with tests"
```

---

## Task 7: cli.py — CLI entry point with URL validation, progress display, Ctrl+C handling

**Files:**
- Create: `src/weread/cli.py`

- [ ] **Step 1: Write cli.py**

```python
import argparse
import re
import shutil
import sys

from weread import __version__
from weread.converter import convert
from weread.errors import WereadError, LoginExpiredError
from weread.scraper import scrape
from weread.utils import get_output_dir

_WEREAD_URL_PATTERN = re.compile(
    r"^https?://weread\.qq\.com/web/reader/"
)
_VALID_FORMATS = {"pdf", "epub", "md"}


def _parse_formats(raw: str) -> list[str]:
    formats = [f.strip().lower() for f in raw.split(",")]
    invalid = set(formats) - _VALID_FORMATS
    if invalid:
        print(f"✗ 不支持的格式: {', '.join(invalid)}")
        print(f"  支持的格式: {', '.join(sorted(_VALID_FORMATS))}")
        sys.exit(1)
    return formats


def _validate_url(url: str) -> str:
    if not _WEREAD_URL_PATTERN.match(url):
        print("✗ 无效的微信读书 URL")
        print("  正确格式: https://weread.qq.com/web/reader/...")
        sys.exit(1)
    return url


def main():
    parser = argparse.ArgumentParser(
        prog="weread",
        description="Export books from WeRead (微信读书) as PDF, EPUB, or Markdown",
    )
    parser.add_argument("url", help="微信读书阅读页 URL")
    parser.add_argument(
        "-f", "--format", default="pdf", dest="formats",
        help="输出格式，逗号分隔: pdf,epub,md (默认: pdf)",
    )
    parser.add_argument(
        "-o", "--output", default=None, dest="output_dir",
        help="输出目录 (默认: ./output/<书名>/)",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()
    url = _validate_url(args.url)
    formats = _parse_formats(args.formats)

    result = None
    try:
        result = scrape(url)
        if not result.chapters:
            print("✗ 未抓取到任何章节")
            sys.exit(1)

        output_dir = get_output_dir(result.book_name, args.output_dir)
        outputs = convert(result, formats, output_dir)

        if result.skipped:
            print(f"\n⚠ 跳过了 {len(result.skipped)} 个章节:")
            for s in result.skipped:
                print(f"   - {s}")

        if outputs:
            print(f"\n✅ 全部完成，文件已保存到 {output_dir}/")
        else:
            print("\n✗ 所有格式转换均失败")
            sys.exit(1)

    except LoginExpiredError:
        print("\n✗ 登录失败，请重新运行并扫码登录")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断")
        if result and result.chapters:
            print(f"   已抓取 {len(result.chapters)} 章，正在保存已有内容...")
            output_dir = get_output_dir(result.book_name, args.output_dir)
            convert(result, formats, output_dir)
            print(f"   部分结果已保存到 {output_dir}/")
        if result and result.temp_dir:
            shutil.rmtree(result.temp_dir, ignore_errors=True)
        sys.exit(130)
    except WereadError as e:
        print(f"\n✗ {e}")
        sys.exit(1)
    finally:
        if result and result.temp_dir:
            shutil.rmtree(result.temp_dir, ignore_errors=True)
```

- [ ] **Step 2: Verify CLI loads**

Run: `python -m weread.cli --version`
Expected: `weread 0.1.0`

Run: `python -m weread.cli`
Expected: error message about missing url argument

- [ ] **Step 3: Commit**

```bash
git add src/weread/cli.py
git commit -m "feat: add CLI entry point with validation and Ctrl+C handling"
```

---

## Task 8: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
# weread-scrapy

Export books from [WeRead (微信读书)](https://weread.qq.com) as PDF, EPUB, or Markdown.

## Install

```bash
pipx install git+https://github.com/user/weread-scrapy.git
```

Or from source:

```bash
git clone https://github.com/user/weread-scrapy.git
cd weread-scrapy
pip install .
playwright install chromium
```

## Usage

```bash
# Export as PDF (default)
weread https://weread.qq.com/web/reader/xxx

# Export as PDF + EPUB + Markdown
weread https://weread.qq.com/web/reader/xxx -f pdf,epub,md

# Custom output directory
weread https://weread.qq.com/web/reader/xxx -o ~/Books/
```

First run will open a browser window — scan the WeChat QR code to log in. Your session is saved to `~/.weread/cookies.json` for future runs.

## Supported Formats

| Format | Description |
|--------|-------------|
| `pdf`  | Merged PDF of all chapters |
| `epub` | EPUB with chapter structure |
| `md`   | Markdown with chapter headings |

## Development

```bash
git clone https://github.com/user/weread-scrapy.git
cd weread-scrapy
python -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
pytest
```

## License

MIT
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with install and usage instructions"
```

---

## Task 9: End-to-end verification

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Verify CLI entry point works**

```bash
weread --version
weread --help
weread invalid-url
```

Expected:
- `weread 0.1.0`
- Help text with all options
- Error: `✗ 无效的微信读书 URL`

- [ ] **Step 3: Verify package installs cleanly**

```bash
pip install -e .
weread --version
```

- [ ] **Step 4: Final commit if any fixups needed**

```bash
git add -A
git commit -m "chore: final adjustments from end-to-end verification"
```
