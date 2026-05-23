# KB-Studio

<p align="center">
  <strong>上传文档，配置 Prompt，部署你的知识库问答服务</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.10-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## 这是什么？

KB-Studio 是一个简洁的知识库问答平台。上传文档 → 手动配置 system prompt → 对话测试 → 一键部署。

没有复杂的 Agent 概念，**就是好用的知识库问答**。

```
创建知识库 → 上传文档 → 配置 Prompt → 对话测试 → 导出部署
```

## 快速开始

```bash
# 安装
git clone git@github.com:szzhangkkk/kb-studio.git
cd kb-studio
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 配置
cp config/active.example.yaml config/active.yaml
# 编辑 config/active.yaml，填入 LLM API key

# 启动
kb-studio serve
# 浏览器打开 http://localhost:8000
```

## 核心概念

### 知识库

每个知识库是独立的：有自己的文档、自己的 system prompt、自己的对话历史。

### 工作流

1. **创建知识库** — 给它起个名字，写个描述
2. **上传文档** — PDF/Word/TXT/HTML 等格式自动转换
3. **配置 Prompt** — 告诉 LLM 怎么回答（这是你控制 Agent 行为的地方）
4. **对话测试** — 实时看效果，调到满意为止
5. **导出部署** — 生成独立 Docker 包，部署到任何地方

## CLI 命令

| 命令 | 说明 |
|------|------|
| `kb-studio serve` | 启动 Web 服务 |
| `kb-studio create-kb <name>` | 创建知识库 |
| `kb-studio list-kb` | 列出所有知识库 |
| `kb-studio test-connection` | 测试 LLM 连接 |

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/kb/list` | 列出知识库 |
| `POST` | `/kb/create` | 创建知识库 |
| `DELETE` | `/kb/{name}` | 删除知识库 |
| `POST` | `/kb/{name}/upload` | 上传文档 |
| `POST` | `/kb/{name}/chat` | 对话 |
| `DELETE` | `/kb/{name}/history` | 清除对话历史 |

## 配置

```yaml
llm:
  provider: deepseek
  api_key: your-key
  base_url: https://api.deepseek.com/v1
  model: deepseek-chat

embedding:
  provider: local
  model: BAAI/bge-small-zh-v1.5
```

## License

MIT
