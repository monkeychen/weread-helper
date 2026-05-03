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
        chapters.append(ChapterInfo(num=i, name=f"第{i}章", pdf_path=pdf, text=f"第{i}章的正文内容。\n这是第二段。"))
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
        assert "## 第1章" in content
        assert "## 第2章" in content
        assert "第1章的正文内容" in content


class TestConvertToEpub:
    def test_creates_epub_file(self, tmp_path):
        result = _make_result(tmp_path, count=2)
        out = tmp_path / "book.epub"
        convert_to_epub(result, out)
        assert out.exists()
        assert out.stat().st_size > 0
