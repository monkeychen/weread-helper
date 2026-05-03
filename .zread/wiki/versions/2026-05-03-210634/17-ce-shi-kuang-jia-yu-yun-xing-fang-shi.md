本项目的测试体系围绕 **pytest** 框架构建，采用轻量级配置与清晰的组织结构，对核心的转换器模块和工具函数模块进行单元测试覆盖。本文将从测试框架选型、项目配置、目录结构、运行方式以及测试设计模式五个维度，帮助你快速理解并掌握本项目的测试体系。

Sources: [pyproject.toml](pyproject.toml#L24-L25), [tests/__init__.py](tests/__init__.py#L1)

## 测试框架选型：为什么是 pytest

项目选择 **pytest** 作为测试框架，这一决策体现在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 配置段中。pytest 在 Python 生态中拥有压倒性的主流地位，其核心优势在于：**零样板的函数式测试编写**（不需要继承 `TestCase` 类）、**强大的 fixture 机制**（如本项目大量使用的 `tmp_path` 内置 fixture）、以及**灵活的发现规则**（自动匹配 `test_*.py` 文件和 `test_*` 函数/类）。

对于本项目而言，pytest 的内置 `tmp_path` fixture 尤为关键——转换器测试需要在临时目录中创建 PDF 文件、生成 Markdown 和 EPUB 输出，`tmp_path` 为每个测试自动创建隔离的临时目录，测试结束后自动清理，完全消除了测试间的状态干扰。

Sources: [pyproject.toml](pyproject.toml#L24-L25)

## 项目配置与发现规则

pytest 的行为通过 `pyproject.toml` 中的 `[tool.pytest.ini_options]` 配置段控制，项目仅指定了一项关键配置：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

`testpaths` 限制 pytest 仅在 `tests/` 目录下搜索测试用例，这避免了框架意外扫描 `src/` 目录中的模块。由于 pytest 的默认发现规则已经足够智能（自动识别以 `test_` 开头的文件名、以 `Test` 开头的类名、以 `test_` 开头的函数名），项目无需额外配置即可正常工作。

整个测试配置的精简程度体现了项目的设计哲学：**依赖约定优于配置，保持最小化设置**。

Sources: [pyproject.toml](pyproject.toml#L24-L26)

## 测试目录结构与测试清单

测试目录独立于源代码，形成了清晰的物理隔离：

```
tests/
├── __init__.py          # 包标识文件（空文件）
├── test_converter.py    # 转换器模块测试（4 个测试用例）
└── test_utils.py        # 工具函数模块测试（6 个测试用例）
```

当前项目共收录 **10 个测试用例**，按被测模块分为两个测试文件。以下表格展示了完整的测试清单及其对应的被测功能：

| 测试文件 | 测试类/函数 | 被测目标 | 验证内容 |
|---------|-----------|---------|---------|
| [test_converter.py](tests/test_converter.py) | `TestMergePdfs::test_merge_creates_file` | `merge_pdfs()` | PDF 文件生成并非空 |
| [test_converter.py](tests/test_converter.py) | `TestMergePdfs::test_merge_page_count` | `merge_pdfs()` | 合并后页数等于章节数 |
| [test_converter.py](tests/test_converter.py) | `TestConvertToMarkdown::test_creates_md_file` | `convert_to_markdown()` | MD 文件包含章节标题和正文 |
| [test_converter.py](tests/test_converter.py) | `TestConvertToEpub::test_creates_epub_file` | `convert_to_epub()` | EPUB 文件生成并非空 |
| [test_utils.py](tests/test_utils.py) | `test_sanitize_normal_name` | `sanitize_filename()` | 正常中文书名原样保留 |
| [test_utils.py](tests/test_utils.py) | `test_sanitize_strips_illegal_chars` | `sanitize_filename()` | 非法字符替换为下划线 |
| [test_utils.py](tests/test_utils.py) | `test_sanitize_strips_whitespace` | `sanitize_filename()` | 首尾空白被移除 |
| [test_utils.py](tests/test_utils.py) | `test_sanitize_collapses_underscores` | `sanitize_filename()` | 连续非法字符合并为单下划线 |
| [test_utils.py](tests/test_utils.py) | `test_sanitize_empty_string` | `sanitize_filename()` | 空字符串返回 `untitled` |
| [test_utils.py](tests/test_utils.py) | `test_sanitize_only_illegal_chars` | `sanitize_filename()` | 全非法字符返回 `untitled` |

Sources: [test_converter.py](tests/test_converter.py#L1-L67), [test_utils.py](tests/test_utils.py#L1-L26)

## 运行测试：命令与方式

运行测试的前提是项目依赖已安装（`pip install -e ".[dev]"` 或手动安装 pytest）。以下是常用的运行命令：

**运行全部测试**（最常用）：
```bash
python -m pytest
```

**运行指定测试文件**：
```bash
python -m pytest tests/test_utils.py
```

**运行指定测试类或单个用例**：
```bash
python -m pytest tests/test_converter.py::TestMergePdfs
python -m pytest tests/test_converter.py::TestMergePdfs::test_merge_page_count
```

**显示详细输出**（每个用例的名称和结果逐行展示）：
```bash
python -m pytest -v
```

**仅收集用例不执行**（快速确认测试发现是否正确）：
```bash
python -m pytest --co -q
```

使用 `python -m pytest` 而非直接执行 `pytest` 命令是一个值得养成的习惯——前者确保使用的是当前虚拟环境中的 pytest，避免因系统级 pytest 版本不一致导致的意外行为。

Sources: [pyproject.toml](pyproject.toml#L24-L26)

## 测试设计模式：工厂函数与数据构建

本项目的测试代码展现了两种核心设计模式，理解它们有助于阅读和编写新的测试用例。

### 模式一：模块级工厂函数

[test_converter.py](tests/test_converter.py) 中定义了两个以 `_` 开头的私有辅助函数，它们充当测试数据的"工厂"，负责构造被测函数所需的输入数据：

```
测试数据构建流程
─────────────────────────────────────────────
_make_dummy_pdf()     → 生成包含空白页的 PDF 文件
        ↓
_make_result()        → 组装 ScrapeResult 对象
        ↓                  （内含多个 ChapterInfo）
被测函数调用          → merge_pdfs() / convert_to_markdown() / convert_to_epub()
        ↓
断言验证             → 检查输出文件存在性、内容正确性
```

其中 `_make_result()` 函数是转换器测试的核心基础设施。它接受 `tmp_path` 和章节数量 `count` 两个参数，返回一个完整的 `ScrapeResult` 数据对象——包含书名、章节列表（每个章节带有编号、名称、PDF 路径和正文文本）以及临时目录路径。这种设计将测试数据的构建逻辑集中管理，使得每个测试方法只需关注自己的验证逻辑。

Sources: [test_converter.py](tests/test_converter.py#L12-L27)

### 模式二：类分组 vs 函数式测试

两个测试文件采用了不同的组织风格：

| 风格 | 文件 | 适用场景 | 示例 |
|-----|------|---------|------|
| **类分组**（`class Test*`） | [test_converter.py](tests/test_converter.py) | 同一被测函数有多个测试角度 | `TestMergePdfs` 将文件存在性检查和页数验证归为一组 |
| **函数式**（`def test_*`） | [test_utils.py](tests/test_utils.py) | 每个测试独立验证一个边界条件 | 每个函数名即完整描述测试意图 |

[test_converter.py](tests/test_converter.py) 的类分组方式将 `merge_pdfs` 的两个测试（文件创建验证、页数计数验证）归入 `TestMergePdfs` 类，将 `convert_to_markdown` 的测试归入 `TestConvertToMarkdown`，将 `convert_to_epub` 的测试归入 `TestConvertToEpub`。这种按被测函数分组的方式在测试用例增长时能保持良好的可浏览性。

[test_utils.py](tests/test_utils.py) 则采用了更轻量的函数式风格——每个测试函数直接以 `test_sanitize_` 前缀命名，函数名本身就描述了测试的边界条件（`normal_name`、`strips_illegal_chars`、`empty_string` 等），无需额外的类层级包装。

Sources: [test_converter.py](tests/test_converter.py#L30-L66), [test_utils.py](tests/test_utils.py#L1-L26)

### 模式三：pytest 内置 fixture 的使用

项目没有自定义 `conftest.py` 或任何 fixture，完全依赖 pytest 内置的 `tmp_path` fixture。这个 fixture 在测试函数参数中以同名变量接收，pytest 会自动为每个测试创建一个唯一的临时目录（位于系统临时路径下），测试结束后自动清理。

在 `_make_result()` 工厂函数中，`tmp_path` 被用于存放生成的 PDF 文件，同时也作为 `ScrapeResult.temp_dir` 的值传递给被测函数。这确保了每次测试都在完全隔离的文件环境中运行。

Sources: [test_converter.py](tests/test_converter.py#L19-L27)

## 测试覆盖范围概览

通过以下图示可以直观理解测试与源代码模块的对应关系：

```
┌──────────────────────────────────────────────────────────────┐
│                       src/weread/                            │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐     │
│  │   utils.py   │   │ converter.py │   │  scraper.py  │     │
│  │              │   │              │   │              │     │
│  │ sanitize_    │   │ merge_pdfs   │   │ (未测试)     │     │
│  │ filename()   │   │ convert_to_  │   │              │     │
│  │              │   │ markdown()   │   │              │     │
│  │ get_cookie_  │   │ convert_to_  │   │              │     │
│  │ path()       │   │ epub()       │   │              │     │
│  │              │   │              │   │              │     │
│  │ get_output_  │   │ convert()    │   │              │     │
│  │ dir()        │   │ (入口，未测) │   │              │     │
│  └──────┬───────┘   └──────┬───────┘   └──────────────┘     │
│         │                  │                                │
└─────────┼──────────────────┼────────────────────────────────┘
          │                  │
          ▼                  ▼
┌──────────────────────────────────────────────────────────────┐
│                        tests/                                │
│  ┌──────────────┐   ┌──────────────────────────────────┐    │
│  │test_utils.py │   │      test_converter.py           │    │
│  │  6 个用例     │   │  4 个用例                         │    │
│  │              │   │  ┌─ TestMergePdfs (2)            │    │
│  │              │   │  ├─ TestConvertToMarkdown (1)    │    │
│  │              │   │  └─ TestConvertToEpub (1)        │    │
│  └──────────────┘   └──────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

值得注意的是，`scraper.py`（浏览器自动化与内容抓取）、`auth.py`（登录状态管理）、`cli.py`（命令行入口）等模块目前不在单元测试覆盖范围内。这些模块强依赖外部环境（浏览器实例、网络请求、微信读书服务端状态），对其进行测试需要引入 mock 或集成测试策略，属于更高级的测试范畴。

Sources: [test_converter.py](tests/test_converter.py#L1-L8), [test_utils.py](tests/test_utils.py#L1)

## 延伸阅读

测试体系的设计与源代码架构紧密关联。如果你想深入了解各测试用例的具体验证策略和边界条件设计，推荐按以下顺序阅读：

- [转换器单元测试：PDF、Markdown、EPUB 验证策略](18-zhuan-huan-qi-dan-yuan-ce-shi-pdf-markdown-epub-yan-zheng-ce-lue) — 深入解析 `test_converter.py` 中每个测试用例的设计意图与断言逻辑
- [工具函数单元测试：文件名清洗边界用例](19-gong-ju-han-shu-dan-yuan-ce-shi-wen-jian-ming-qing-xi-bian-jie-yong-li) — 解析 `test_utils.py` 如何通过 6 个用例覆盖 `sanitize_filename()` 的各种边界场景