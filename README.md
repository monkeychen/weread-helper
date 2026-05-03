# weread-helper

Export books from [WeRead (微信读书)](https://weread.qq.com) as PDF, EPUB, or Markdown.

## Install

```bash
pipx install git+https://github.com/monkeychen/weread-helper.git
```

Or from source:

```bash
git clone https://github.com/monkeychen/weread-helper.git
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
git clone https://github.com/monkeychen/weread-helper.git
cd weread-scrapy
python -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
pytest
```

## ⚠️ Disclaimer

> **This project is intended solely for personal learning, research, and technical exchange. Do not use it for any commercial or illegal purposes.**

- This project does not provide any book resources. All content comes from the user's own purchased WeRead account.
- Exported content is for personal reading backup only. Redistribution, sharing, or commercial use is strictly prohibited.
- Users must comply with WeRead's [Terms of Service](https://weread.qq.com/web/copyright) and all applicable laws and regulations. The developer assumes no responsibility for any consequences arising from misuse.
- If this project infringes on your rights, please contact us via [Issues](https://github.com/monkeychen/weread-helper/issues) and we will address it promptly.

## License

MIT
