# KB-Studio

<p align="center">
  <strong>主动式知识管家 | Proactive Knowledge Butler</strong>
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

KB-Studio 不只是一个 RAG 问答工具——它是一个**主动式知识管家**。上传文档后，管家会自动巡检知识库质量、监控外部数据源变化、从对话中学习你的偏好，并主动推送建议。

### 核心特性

**知识管理**
- 多知识库管理，独立配置和检索
- 40+ 种文档格式支持（PDF、Word、Excel、PPT、Markdown、代码等）
- URL 导入（网页、YouTube、Wikipedia）
- 智能分块：按标题、语义感知、滑动窗口
- 混合检索：向量相似度 + BM25 关键词，可调权重
- 知识质量分析：自动检测矛盾、重复、过时内容

**管家能力**
- **定时任务引擎** — 自动巡检、源监控、摘要生成、记忆同步、建议生成
- **源监控** — 配置 URL 监控列表，内容变化时自动抓取并更新知识库
- **主动建议** — 基于记忆、文档新鲜度、使用模式生成建议
- **通知系统** — 应用内通知 + WebSocket 实时推送
- **内容新鲜度** — 自动标记老化（>7天）和过期（>30天）文档

**记忆与学习**
- 跨 KB 统一记忆，构建全局用户画像
- 对话自动提取关键信息（偏好、结论、领域知识）
- 兴趣识别：从对话中学习用户关注领域

**工具与集成**
- 自定义工具 / AI 生成工具（自然语言描述 → Python 代码）
- MCP 协议支持，连接 Claude Desktop、Cursor 等外部 AI
- 9 个管家 MCP 工具（状态查询、任务触发、建议查看等）
- Agent Pipeline：多步推理流水线

**导入导出**
- 知识库一键导出（ZIP 包含文档、配置、记忆、对话）
- ZIP 导入恢复
- Markdown 全文导出、质量报告导出

**界面**
- 赛博朋克风格 Web UI（Next.js）
- Dark / Light 主题切换
- VS Code 风格布局（活动栏 + 侧边栏 + 面板）
- 管家面板：总览、定时任务、源监控、通知、导出

### 快速开始

#### Docker（推荐）

```bash
git clone https://github.com/szzhangkkk/kb-studio.git
cd kb-studio
docker compose up -d
# 访问 http://localhost:8000
```

#### pip 安装

```bash
git clone https://github.com/szzhangkkk/kb-studio.git
cd kb-studio
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
cp config/active.example.yaml config/active.yaml
# 编辑 config/active.yaml 填入 LLM API Key
kb-studio serve
# 访问 http://localhost:8000
```

### 配置

```yaml
llm:
  provider: deepseek          # deepseek / qwen / zhipu / claude / openai / ollama / custom
  api_key: "your-api-key"
  model: deepseek-chat

embedding:
  provider: local              # "local"（本地）或 "api"（远程）
  model: BAAI/bge-small-zh-v1.5
```

#### 环境变量

| 变量 | 说明 |
|------|------|
| `KB_STUDIO_API_KEY` | 设置后 API 需要 Bearer Token 认证 |
| `KB_STUDIO_CORS_ORIGINS` | CORS 来源（默认 `*`） |
| `HF_ENDPOINT` | HuggingFace 镜像，国内建议 `https://hf-mirror.com` |

### 架构

```
用户 → Web UI (Next.js) → FastAPI Server
                              ├── 文档处理 → 分块 → 向量化
                              ├── 混合检索（向量 + BM25）
                              ├── Chat Engine（RAG 问答）
                              ├── Agent（工具调用 + Pipeline）
                              ├── 管家引擎
                              │   ├── 定时任务调度器
                              │   ├── 源监控（URL 变更检测）
                              │   ├── 知识质量分析
                              │   ├── 主动建议生成
                              │   ├── 全局记忆系统
                              │   └── WebSocket 通知推送
                              ├── 工具系统（自定义 + AI 生成 + MCP）
                              └── 导入导出

存储：文件系统（./data/），无需数据库
```

### CLI 命令

| 命令 | 说明 |
|------|------|
| `kb-studio serve` | 启动服务 |
| `kb-studio create-kb <name>` | 创建知识库 |
| `kb-studio list-kb` | 列出知识库 |
| `kb-studio test-connection` | 测试连接 |

---

## English

### Overview

KB-Studio is not just a RAG Q&A tool — it's a **proactive knowledge butler**. After uploading documents, the butler automatically audits knowledge quality, monitors external sources for changes, learns your preferences from conversations, and proactively pushes suggestions.

### Core Features

**Knowledge Management**
- Multi-KB management with independent configs
- 40+ document formats (PDF, Word, Excel, PPT, Markdown, code, etc.)
- URL import (web pages, YouTube, Wikipedia)
- Smart chunking: heading-based, semantic-aware, sliding window
- Hybrid retrieval: vector similarity + BM25 keyword search
- Quality analysis: auto-detect contradictions, duplicates, staleness

**Butler Capabilities**
- **Scheduled Tasks** — Auto-patrol, source monitoring, digest, memory sync, suggestions
- **Source Monitoring** — Watch URLs for changes, auto-fetch and update KB
- **Proactive Suggestions** — Based on memory, freshness, usage patterns
- **Notifications** — In-app + WebSocket real-time push
- **Content Freshness** — Auto-mark aging (>7d) and stale (>30d) documents

**Memory & Learning**
- Cross-KB unified memory with global user profile
- Auto-extract key info from conversations (preferences, conclusions, domain knowledge)
- Interest recognition from conversation patterns

**Tools & Integration**
- Custom / AI-generated tools (NL description → Python code)
- MCP protocol for Claude Desktop, Cursor integration
- 9 butler MCP tools (status, tasks, suggestions, memory, etc.)
- Agent Pipeline: multi-step reasoning chain

**Import/Export**
- One-click KB export (ZIP with docs, config, memory, conversations)
- ZIP import to restore
- Markdown full-text export, quality report export

**Interface**
- Cyberpunk-themed Web UI (Next.js)
- Dark / Light theme toggle
- VS Code-style layout (activity bar + sidebar + panels)
- Butler panel: overview, tasks, sources, notifications, export

### Quick Start

#### Docker (Recommended)

```bash
git clone https://github.com/szzhangkkk/kb-studio.git
cd kb-studio
docker compose up -d
# Visit http://localhost:8000
```

#### pip Install

```bash
git clone https://github.com/szzhangkkk/kb-studio.git
cd kb-studio
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
cp config/active.example.yaml config/active.yaml
# Edit config/active.yaml with your LLM API key
kb-studio serve
# Visit http://localhost:8000
```

### License

MIT
