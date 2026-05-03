# weread-scrapy Refactor Design Spec

## Overview

将现有的微信读书单文件爬虫脚本重构为可安装的 CLI 工具包，支持多格式输出、登录态过期检测、优雅错误处理。目标是开源发布，用户可通过 `pipx install` 安装后直接使用。

## 项目结构

```
weread-scrapy/
├── pyproject.toml          # 构建配置 + 依赖 + CLI 入口点
├── README.md
├── LICENSE
├── .gitignore
├── src/
│   └── weread/
│       ├── __init__.py     # 版本号
│       ├── cli.py          # CLI 入口，argparse
│       ├── auth.py         # 登录态管理、cookie 过期检测
│       ├── scraper.py      # 章节抓取核心逻辑
│       ├── converter.py    # PDF → EPUB / Markdown 格式转换
│       └── utils.py        # 通用工具函数（路径、日志等）
└── tests/
    └── test_converter.py   # converter 是唯一可脱离浏览器单测的模块
```

- 包名：`weread`
- 安装后命令：`weread <url>`
- src layout，避免开发时 import 混乱
- Python >= 3.9（Playwright 最低要求）

## CLI 接口

```bash
# 基本用法
weread https://weread.qq.com/web/reader/xxx

# 指定输出格式（默认 pdf）
weread https://weread.qq.com/web/reader/xxx --format pdf,epub,md

# 指定输出目录（默认 ./output/<书名>/）
weread https://weread.qq.com/web/reader/xxx -o ~/Books/

# 查看版本
weread --version
```

### 参数

| 参数 | 短选项 | 默认值 | 说明 |
|---|---|---|---|
| `url` | 位置参数 | 必填 | 微信读书阅读页 URL |
| `--format` | `-f` | `pdf` | 输出格式，逗号分隔：pdf, epub, md |
| `--output` | `-o` | `./output/<书名>/` | 输出目录 |
| `--version` | `-v` | - | 打印版本号 |

### 交互流程

```
$ weread https://weread.qq.com/web/reader/xxx -f pdf,epub

🔍 正在打开微信读书...
⚠️  检测到登录态已过期，请扫码登录
   扫码完成后按 Enter 继续...

📖 开始抓取《xxx》
   [1/12] 第一章 已保存
   [2/12] 第二章 已保存
   ...
📦 生成 PDF... 完成
📦 生成 EPUB... 完成
✅ 全部完成，文件已保存到 ./output/xxx/
```

- 进度提示包含章节编号和章节名（从页面提取）
- cookie 有效时静默跳过登录步骤，过期时主动提示
- 出错时提示具体原因和建议操作，而非裸 traceback

## 核心模块

### auth.py — 登录态管理

**职责：** 管理 cookie 的存储、加载、过期检测。

**cookie 存储位置：** `~/.weread/cookies.json`（用户级别，不放项目目录，避免泄露到 git）

**过期检测策略：**
- 加载 cookie 后访问书籍阅读页
- 检查页面是否出现登录二维码元素（`.login__QRcode` 或类似选择器）
- 出现则判定过期，提示用户重新扫码
- 扫码成功后自动保存新 cookie

**接口：**
- `ensure_login(page) -> bool` — 确保登录态有效，需要时引导用户扫码，返回是否成功

### scraper.py — 章节抓取

**职责：** 控制浏览器逐章抓取，输出每章的临时 PDF。

**改进点（相比现有）：**
- 用「等待特定元素渲染完成」替代 `time.sleep` 固定等待
  - 等待 `.readerChapterContent` 出现且稳定（高度不再变化）
- 抓取前先从目录页提取章节总数和章节名，用于进度显示
- 临时 PDF 存到系统临时目录（`tempfile.mkdtemp()`），脚本结束自动清理

**接口：**
- `scrape(url, on_progress) -> ScrapeResult` — 抓取整本书，通过回调报告进度
- `ScrapeResult` 包含：书名、章节列表（名称 + 临时 PDF 路径）

### converter.py — 格式转换

**职责：** 把临时章节 PDF 转换为目标格式。

| 格式 | 实现方式 |
|---|---|
| PDF | PyPDF2 合并章节 PDF |
| EPUB | `ebooklib` 生成，从 PDF 提取文本 + 保留基本结构 |
| Markdown | `pdfplumber` 提取文本，按章节组织为 `.md` 文件 |

**接口：**
- `convert(scrape_result, formats, output_dir)` — 按指定格式输出到目标目录

### 依赖

```toml
dependencies = [
    "playwright>=1.43",
    "PyPDF2>=3.0",
    "ebooklib>=0.18",
    "pdfplumber>=0.10",
]
```

## 错误处理

### 自定义异常

```python
class WereadError(Exception): ...        # 基类
class LoginExpiredError(WereadError): ... # cookie 过期且用户未完成扫码
class ChapterLoadError(WereadError): ... # 章节渲染超时或加载失败
class ConvertError(WereadError): ...      # 格式转换失败
```

模块内部抛自定义异常，cli.py 统一捕获并转为用户友好提示。

### 各场景处理

| 场景 | 行为 |
|---|---|
| URL 格式不对 | CLI 层直接校验拒绝，提示正确格式 |
| cookie 过期 | 提示扫码，用户 Ctrl+C 退出时保留已抓内容 |
| 某章渲染超时（15s） | 重试 1 次，仍失败则跳过该章并记录，继续后续章节 |
| 下一章按钮找不到 | 判定为全书结束，正常收尾 |
| 格式转换失败 | 报告哪个格式失败，不影响其他格式的输出 |
| 用户 Ctrl+C 中断 | 优雅退出：关闭浏览器，合并已抓取章节并输出，清理临时文件 |

### Ctrl+C 优雅退出

1. 停止抓取循环
2. 用已有章节执行转换
3. 输出提示：「已抓取 N/M 章，部分结果已保存到 xxx」
4. 清理临时文件，关闭浏览器

## 输出目录结构

```
output/
└── 认知觉醒/
    ├── 认知觉醒.pdf
    ├── 认知觉醒.epub
    └── 认知觉醒.md
```

- 默认输出到 `./output/<书名>/`，`-o` 参数可覆盖父目录
- 书名从页面 `document.title` 或 `.readerTopBar_title` 提取，去除非法文件名字符
- 文件名 = 书名 + 格式后缀

## 测试策略

- `test_converter.py`：converter 模块是唯一可脱离浏览器单测的模块
  - 测试 PDF 合并、EPUB 生成、Markdown 提取
- scraper / auth 依赖浏览器和微信读书在线环境，不写自动化测试，通过手动验证
