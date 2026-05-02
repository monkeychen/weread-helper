from __future__ import annotations

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
