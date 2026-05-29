# KB-Studio

<p align="center">
  <strong>自部署的知识库问答平台 | Self-deployable Knowledge Base Q&A Platform</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Docker-Ready-blue" alt="Docker">
</p>

[中文](#中文) | [English](#english)

---

## 中文

### 简介

KB-Studio 是一个开箱即用的 RAG 知识库问答平台。上传文档，配置 LLM，即可获得一个基于你私有数据的智能问答服务。

### 功能特性

- **知识库管理** — 创建多个知识库，独立管理文档和配置
- **多格式文档支持** — PDF、Word、Excel、PPT、Markdown、HTML、代码文件等 40+ 种格式
- **URL 导入** — 直接导入网页、YouTube 字幕、Wikipedia 文章
- **智能分块** — 三种分块策略：按标题、语义感知、滑动窗口
- **混合检索** — 向量相似度 + BM25 关键词检索，可调权重
- **多轮对话** — 带上下文的连续问答，对话管理（创建/切换/删除/导出）
- **记忆系统** — 自动从对话中提取关键信息，注入后续问答
- **Agent Pipeline** — 多步推理流水线：检索 → 分析 → 生成 → 审核
- **多 LLM 支持** — DeepSeek、Qwen、智谱、Moonshot、Claude、OpenAI、Ollama 及任意 OpenAI 兼容 API
- **Web UI** — 内置 Cyberpunk 风格的现代化 Web 界面
- **API Key 认证** — 可选的 Bearer Token 认证保护

### 快速开始

#### Docker（推荐）

```bash
git clone https://github.com/szzhangkkk/kb-studio.git
cd kb-studio

# 一键启动
docker compose up -d

# 访问 http://localhost:8000
```

首次启动后，在 Web 界面的"配置"页面填写你的 LLM API Key 即可使用。

**启用本地 Embedding（可选）：**

本地 Embedding 使用 sentence-transformers，无需 Embedding API，但镜像较大（~2GB）。编辑 `docker-compose.yml`，将 `target: slim` 改为 `target: full`，取消 `hf-cache` 相关注释，然后：

```bash
docker compose up -d --build
```

#### pip 安装

```bash
git clone https://github.com/szzhangkkk/kb-studio.git
cd kb-studio

python -m venv .venv && source .venv/bin/activate

# 基础安装
pip install -e .

# 完整安装（含本地 Embedding + Claude 支持）
pip install -e ".[all]"

# 配置
cp config/active.example.yaml config/active.yaml
# 编辑 config/active.yaml 填入你的 LLM API Key

# 启动
kb-studio serve
# 访问 http://localhost:8000
```

### 配置

编辑 `config/active.yaml` 或在 Web 界面配置：

```yaml
llm:
  provider: deepseek          # deepseek / qwen / zhipu / moonshot / claude / openai / ollama / custom
  base_url: https://api.deepseek.com/v1
  api_key: "your-api-key"
  model: deepseek-chat
  temperature: 0.7
  max_tokens: 4096

embedding:
  provider: local              # "local"（本地模型）或 "api"（远程 API）
  model: BAAI/bge-small-zh-v1.5
```

**支持的 LLM 提供商：** DeepSeek、通义千问、智谱 GLM、Moonshot、Claude、OpenAI、Ollama 及任意 OpenAI 兼容 API。

#### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `KB_STUDIO_API_KEY` | 空（不启用） | 设置后所有 API 需要 `Authorization: Bearer <key>` |
| `KB_STUDIO_CORS_ORIGINS` | `*` | 允许的 CORS 来源，逗号分隔 |
| `HF_ENDPOINT` | 空 | HuggingFace 镜像地址，国内建议设为 `https://hf-mirror.com` |

### 架构

```
用户 → Web UI (Next.js) → FastAPI Server
                              ├── 文档处理（markitdown → 分块）
                              ├── 混合检索（向量 + BM25）
                              ├── Chat Engine（RAG 问答）
                              ├── Agent Pipeline（多步推理）
                              └── LLM Client（多 Provider 适配）

存储：文件系统（./data/{kb_name}/），无需数据库
```

### 支持的文件格式

| 类别 | 格式 |
|------|------|
| 文档 | PDF, DOCX, PPTX, XLSX, EPUB, MSG |
| 表格 | CSV, TSV |
| 标记语言 | HTML, XML, JSON, RSS, Atom |
| 文本/代码 | TXT, MD, RST, YAML, TOML, Python, JS, Go, Rust, SQL 等 |
| 笔记本 | Jupyter Notebook (.ipynb) |
| 媒体 | JPG, PNG, WAV, MP3, MP4（需配合多模态 LLM） |
| 压缩包 | ZIP（递归解析） |
| URL | 网页、YouTube、Wikipedia |

### CLI 命令

| 命令 | 说明 |
|------|------|
| `kb-studio serve` | 启动 Web 服务 |
| `kb-studio create-kb <name>` | 创建知识库 |
| `kb-studio list-kb` | 列出所有知识库 |
| `kb-studio test-connection` | 测试 LLM 连接 |

### 开发指南

```bash
pip install -e ".[all]"
pip install pytest

pytest                        # 运行测试
kb-studio serve --port 8000   # 启动开发服务器
```

### 项目结构

```
kb-studio/
├── kb_studio/
│   ├── cli.py              # CLI 命令
│   ├── server.py           # FastAPI 服务器
│   ├── kb_manager.py       # 知识库管理
│   ├── chat_engine.py      # RAG 对话引擎
│   ├── agent_pipeline.py   # Agent Pipeline
│   └── core/
│       ├── llm/            # LLM 客户端
│       ├── retrieval/      # 检索策略
│       ├── vector_store/   # 向量存储
│       └── doc_processor/  # 文档处理
├── web/frontend/           # Next.js Web UI
├── config/                 # 配置文件
├── data/                   # 数据目录（运行时生成）
├── tests/                  # 测试
├── Dockerfile              # Docker 构建文件
└── docker-compose.yml      # Docker Compose 配置
```

---

## English

### Overview

KB-Studio is a ready-to-use RAG (Retrieval-Augmented Generation) knowledge base Q&A platform. Upload documents, configure your LLM, and get an intelligent Q&A service powered by your private data.

### Features

- **Knowledge Base Management** — Create multiple knowledge bases with independent documents and configs
- **Multi-format Support** — PDF, Word, Excel, PPT, Markdown, HTML, source code, and 40+ formats
- **URL Import** — Import web pages, YouTube transcripts, and Wikipedia articles directly
- **Smart Chunking** — Three strategies: heading-based, semantic-aware, sliding window
- **Hybrid Retrieval** — Vector similarity + BM25 keyword search with adjustable weights
- **Multi-turn Conversations** — Contextual Q&A with conversation management (create/switch/delete/export)
- **Memory System** — Auto-extract key information from conversations, inject into future Q&A
- **Agent Pipeline** — Multi-step reasoning: retrieve → analyze → generate → review
- **Multi-LLM Support** — DeepSeek, Qwen, Zhipu, Moonshot, Claude, OpenAI, Ollama, and any OpenAI-compatible API
- **Web UI** — Built-in cyberpunk-themed modern web interface
- **API Key Auth** — Optional Bearer Token authentication

### Quick Start

#### Docker (Recommended)

```bash
git clone https://github.com/szzhangkkk/kb-studio.git
cd kb-studio

docker compose up -d

# Visit http://localhost:8000
```

After first launch, configure your LLM API Key in the Settings page of the web UI.

**Enable Local Embedding (Optional):**

Edit `docker-compose.yml`, change `target: slim` to `target: full`, uncomment `hf-cache` volume, then:

```bash
docker compose up -d --build
```

#### pip Install

```bash
git clone https://github.com/szzhangkkk/kb-studio.git
cd kb-studio

python -m venv .venv && source .venv/bin/activate

# Basic install
pip install -e .

# Full install (local embedding + Claude support)
pip install -e ".[all]"

# Configure
cp config/active.example.yaml config/active.yaml
# Edit config/active.yaml with your LLM API key

# Start
kb-studio serve
# Visit http://localhost:8000
```

### Configuration

Edit `config/active.yaml` or configure via the web UI:

```yaml
llm:
  provider: deepseek          # deepseek / qwen / zhipu / moonshot / claude / openai / ollama / custom
  base_url: https://api.deepseek.com/v1
  api_key: "your-api-key"
  model: deepseek-chat

embedding:
  provider: local              # "local" (runs locally) or "api" (remote service)
  model: BAAI/bge-small-zh-v1.5
```

**Supported LLM Providers:** DeepSeek, Qwen, Zhipu GLM, Moonshot, Claude, OpenAI, Ollama, and any OpenAI-compatible API.

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KB_STUDIO_API_KEY` | Empty (disabled) | When set, all API requests require `Authorization: Bearer <key>` |
| `KB_STUDIO_CORS_ORIGINS` | `*` | Comma-separated list of allowed CORS origins |
| `HF_ENDPOINT` | Empty | HuggingFace mirror URL. Recommended for China: `https://hf-mirror.com` |

### Architecture

```
User → Web UI (Next.js) → FastAPI Server
                              ├── Document Processing (markitdown → chunking)
                              ├── Hybrid Retrieval (vector + BM25)
                              ├── Chat Engine (RAG Q&A)
                              ├── Agent Pipeline (multi-step reasoning)
                              └── LLM Client (multi-provider adapter)

Storage: Filesystem (./data/{kb_name}/) — no database required
```

### Supported File Formats

| Category | Formats |
|----------|---------|
| Documents | PDF, DOCX, PPTX, XLSX, EPUB, MSG |
| Spreadsheets | CSV, TSV |
| Markup | HTML, XML, JSON, RSS, Atom |
| Text/Code | TXT, MD, RST, YAML, TOML, Python, JS, Go, Rust, SQL, etc. |
| Notebooks | Jupyter Notebook (.ipynb) |
| Media | JPG, PNG, WAV, MP3, MP4 (requires multimodal LLM) |
| Archives | ZIP (recursive parsing) |
| URL | Web pages, YouTube, Wikipedia |

### CLI Commands

| Command | Description |
|---------|-------------|
| `kb-studio serve` | Start web server |
| `kb-studio create-kb <name>` | Create knowledge base |
| `kb-studio list-kb` | List all knowledge bases |
| `kb-studio test-connection` | Test LLM connection |

### Development

```bash
pip install -e ".[all]"
pip install pytest

pytest                        # Run tests
kb-studio serve --port 8000   # Start dev server
```

## License

MIT
