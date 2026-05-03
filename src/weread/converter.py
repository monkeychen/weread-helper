from __future__ import annotations

import re
import shutil
from pathlib import Path

import PyPDF2
from ebooklib import epub

from weread.scraper import ScrapeResult
from weread.errors import ConvertError


def _format_chapter_text(text: str) -> str:
    """Join physical canvas lines within each paragraph; preserve images and paragraph breaks."""
    paragraphs = re.split(r"\n\n+", text)
    formatted = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if para.startswith("![]("):
            formatted.append(para)
        else:
            # Join physical lines — no space needed for Chinese text
            joined = "".join(line.strip() for line in para.splitlines() if line.strip())
            if joined:
                formatted.append(joined)
    return "\n\n".join(formatted)


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


def convert_to_markdown(result: ScrapeResult, output_path: Path) -> None:
    try:
        lines = [f"# {result.book_name}\n"]
        for ch in result.chapters:
            lines.append(f"## {ch.name}\n")
            if ch.text:
                lines.append(_format_chapter_text(ch.text))
            else:
                lines.append("*(此章无内容)*")
            lines.append("")
        output_path.write_text("\n".join(lines), encoding="utf-8")

        # Copy images directory alongside the markdown file
        src_images = Path(result.temp_dir) / "images"
        if src_images.exists() and any(src_images.iterdir()):
            dst_images = output_path.parent / "images"
            if dst_images.exists():
                shutil.rmtree(dst_images)
            shutil.copytree(str(src_images), str(dst_images))
    except Exception as e:
        raise ConvertError("markdown", str(e)) from e


def convert_to_epub(result: ScrapeResult, output_path: Path) -> None:
    try:
        book = epub.EpubBook()
        book.set_identifier(f"weread-{result.book_name}")
        book.set_title(result.book_name)
        book.set_language("zh")

        # Pre-register images so chapters can reference them
        images_dir = Path(result.temp_dir) / "images"
        _MEDIA_TYPES = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "gif": "image/gif", "webp": "image/webp",
        }
        added_images: set[str] = set()

        def _add_image(fname: str) -> None:
            if fname in added_images or not images_dir.exists():
                return
            img_path = images_dir / fname
            if not img_path.exists():
                return
            ext = img_path.suffix.lower().lstrip(".")
            img_item = epub.EpubImage()
            img_item.uid = f"img_{re.sub(r'[^a-zA-Z0-9]', '_', fname)}"
            img_item.file_name = f"images/{fname}"
            img_item.media_type = _MEDIA_TYPES.get(ext, "image/jpeg")
            img_item.content = img_path.read_bytes()
            book.add_item(img_item)
            added_images.add(fname)

        chapters_epub = []
        for ch in result.chapters:
            html_parts: list[str] = []
            if ch.text:
                for block in re.split(r"\n\n+", ch.text):
                    block = block.strip()
                    if not block:
                        continue
                    m = re.fullmatch(r"!\[\]\(images/([^)]+)\)", block)
                    if m:
                        fname = m.group(1)
                        _add_image(fname)
                        html_parts.append(
                            f'<img src="images/{fname}" alt="" style="max-width:100%;"/>'
                        )
                    else:
                        joined = "".join(
                            line.strip() for line in block.splitlines() if line.strip()
                        )
                        if joined:
                            html_parts.append(f"<p>{joined}</p>")
            else:
                html_parts = ["<p>此章无内容</p>"]

            c = epub.EpubHtml(
                title=ch.name,
                file_name=f"chapter_{ch.num}.xhtml",
                lang="zh",
            )
            c.content = f"<h1>{ch.name}</h1>" + "".join(html_parts)
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
                print("📦 生成 PDF...")
                merge_pdfs(result, out_path)
            elif fmt == "epub":
                print("📦 生成 EPUB...")
                convert_to_epub(result, out_path)
            elif fmt == "md":
                print("📦 生成 Markdown...")
                convert_to_markdown(result, out_path)
            else:
                print(f"⚠ 未知格式: {fmt}，跳过")
                continue
            outputs[fmt] = out_path
            print(f"   ✓ {out_path}")
        except ConvertError as e:
            print(f"   ✗ {fmt} 转换失败: {e}")

    return outputs
