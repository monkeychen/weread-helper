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
