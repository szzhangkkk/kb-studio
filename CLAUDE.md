# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KB-Studio is a self-deployable knowledge base Q&A platform. Users upload documents, configure system prompts, and deploy a RAG-based chat service.

**Tech Stack**: Python 3.10+, FastAPI, OpenAI-compatible LLM API, Milvus vector store (optional), jieba for Chinese tokenization, BM25 + vector hybrid search.

## Commands

### Development Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp config/active.example.yaml config/active.yaml
# Edit config/active.yaml with your LLM API key
```

### Running
```bash
kb-studio serve                    # Start web server on port 8000
kb-studio serve --port 8080        # Custom port
```

### CLI Commands
```bash
kb-studio create-kb <name>         # Create knowledge base
kb-studio list-kb                  # List all knowledge bases
kb-studio test-connection          # Test LLM and embedding connections
```

### Testing
```bash
pytest                             # Run all tests
pytest tests/test_specific.py      # Run specific test file
pytest -k "test_name"              # Run specific test by name
```

## Architecture

### Core Components

**`kb_studio/cli.py`** - Click-based CLI with commands: `serve`, `create-kb`, `list-kb`, `test-connection`

**`kb_studio/server.py`** - FastAPI application with REST API endpoints:
- `/kb/list`, `/kb/create`, `/kb/{name}` - Knowledge base CRUD
- `/kb/{name}/upload` - Document upload
- `/kb/{name}/chat` - RAG chat endpoint
- `/config` - LLM/embedding configuration
- `/test-connection` - Connection health check

**`kb_studio/kb_manager.py`** - Knowledge base lifecycle management:
- Creates KB directory structure in `./data/{kb_name}/`
- Stores config in `config.yaml`, chunks in `chunks.json`, docs in `docs/`
- Handles document conversion and chunking

**`kb_studio/chat_engine.py`** - RAG chat engine per knowledge base:
- Loads chunks, builds vector + BM25 indices
- Retrieves relevant context, generates answers via LLM
- Maintains conversation history (last 20 messages)

### Core Modules (`kb_studio/core/`)

**`llm/client.py`** - Unified LLM client supporting OpenAI-compatible APIs and Claude:
- `LLMClient` - Chat completions with tool calling support
- `EmbeddingClient` - Text embeddings (OpenAI-compatible)
- Handles provider-specific message formatting (Claude vs OpenAI)

**`llm/providers.py`** - Provider templates (deepseek, qwen, claude, openai, ollama, etc.)

**`llm/local_embedder.py`** - Local embedding using sentence-transformers (no API key needed)

**`retrieval/hybrid_search.py`** - Hybrid retrieval combining:
- Vector similarity search
- BM25 keyword search (via jieba tokenization)
- Configurable weights (default: 70% vector, 30% BM25)
- Optional reranking

**`vector_store/`** - Vector storage backends:
- `memory_store.py` - In-memory numpy-based store
- `milvus_store.py` - Milvus integration (optional)

**`doc_processor/`** - Document processing:
- `converter.py` - Document → Markdown conversion (via markitdown)
- `chunker.py` - Multiple strategies: heading-based, semantic, sliding window

### Data Flow

1. **Upload**: Document → markitdown → Markdown → Chunker → chunks.json
2. **Chat**: Question → Embed → Hybrid Search (vector + BM25) → Context → LLM → Answer

### Configuration

**Global config**: `config/active.yaml` - LLM provider, API keys, embedding model

**Per-KB config**: `./data/{kb_name}/config.yaml` - system_prompt, description

**Key config options**:
- `llm.provider` - deepseek/qwen/claude/openai/ollama/custom
- `embedding.provider` - local (sentence-transformers) or API-based
- `retrieval.strategy` - hybrid/hybrid_rerank/vector/bm25

## Important Notes

- **No database**: All data stored as files in `./data/` directory
- **Lazy imports**: Heavy dependencies (pymilvus, sentence-transformers) imported only when needed
- **Chinese-first**: Default prompts and tokenization optimized for Chinese text
- **Singleton pattern**: Server uses global singletons for LLM client, embedding client, and KB manager
- **Engine caching**: ChatEngine instances cached per knowledge base, reset on document upload
