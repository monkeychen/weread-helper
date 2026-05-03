# weread-scrapy

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

## ⚠️ 免责声明

> **本项目仅供个人学习研究与技术交流使用，请勿用于任何商业或非法用途。**

- 本项目不提供任何书籍资源，所有内容均来自用户已购买的微信读书账户。
- 使用本工具导出的内容仅供个人阅读备份，严禁用于传播、分发或商业牟利。
- 用户应遵守微信读书的[服务协议](https://weread.qq.com/web/copyright)及相关法律法规，因违规使用造成的一切后果由用户自行承担，与本项目开发者无关。
- 如本项目侵犯了您的权益，请通过 [Issues](https://github.com/monkeychen/weread-helper/issues) 联系我们，我们将及时处理。

## License

MIT
