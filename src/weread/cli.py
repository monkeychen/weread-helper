from __future__ import annotations

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
