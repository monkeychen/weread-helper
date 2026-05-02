from __future__ import annotations

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
