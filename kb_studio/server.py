"""KB-Studio API server."""

import json
import os
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from kb_studio.kb_manager import KBManager
from kb_studio.chat_engine import ChatEngine
from kb_studio.core.llm.client import LLMClient
from kb_studio.core.llm.local_embedder import LocalEmbedder

app = FastAPI(title="KB-Studio", version="0.1.0")

# WebSocket broadcaster
from kb_studio.ws_broadcaster import WSBroadcaster
_ws_broadcaster = WSBroadcaster()

# CORS — restrict origins in production via KB_STUDIO_CORS_ORIGINS env var
_cors_origins = os.environ.get("KB_STUDIO_CORS_ORIGINS", "*").split(",")
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_methods=["*"], allow_headers=["*"])

# Optional API key auth — set KB_STUDIO_API_KEY env var to enable
_API_KEY = os.environ.get("KB_STUDIO_API_KEY", "")


from fastapi.responses import JSONResponse

# Paths that don't require authentication (public/static)
_PUBLIC_PATHS = ("/health", "/", "/favicon.ico")
_PUBLIC_PREFIXES = ("/_next",)

# Paths that are API endpoints (require auth when key is set)
_API_PREFIXES = ("/kb/", "/config", "/test-", "/providers", "/supported", "/pipeline", "/tools", "/agent/", "/mcp/", "/scheduler/", "/notifications", "/sources", "/export/")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Protect API endpoints when KB_STUDIO_API_KEY is set."""
    if not _API_KEY:
        return await call_next(request)  # No key configured — open access

    path = request.url.path

    # Always allow public paths and static assets
    if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
        return await call_next(request)

    # All API endpoints require auth
    if any(path.startswith(p) for p in _API_PREFIXES):
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {_API_KEY}":
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

    # Static file serving (index.html, etc.) — allow without auth
    return await call_next(request)

CONFIG_PATH = "config/active.yaml"


@app.on_event("startup")
async def _check_config():
    cfg = _load_config()
    llm_key = cfg.get("llm", {}).get("api_key", "")
    if llm_key.lower() in ("your-api-key-here", "your-api-key", "sk-xxx"):
        print("\n⚠️  LLM API key 未配置！请编辑 config/active.yaml 填入真实 API key。\n")
    # Start the scheduler
    scheduler = _get_scheduler()
    await scheduler.start()


@app.on_event("shutdown")
async def _shutdown():
    scheduler = _get_scheduler()
    await scheduler.stop()


# Singletons
_kb_manager = None
_llm_client = None
_emb_client = None
_engines: dict[str, ChatEngine] = {}


def _load_config():
    p = Path(CONFIG_PATH)
    if p.exists():
        return yaml.safe_load(p.read_text())
    return {}


def _get_manager():
    global _kb_manager
    if _kb_manager is None:
        _kb_manager = KBManager()
    return _kb_manager


def _get_llm():
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient(_load_config().get("llm", {}))
    return _llm_client


def _get_emb():
    global _emb_client
    if _emb_client is None:
        cfg = _load_config().get("embedding", {})
        if cfg.get("provider") == "local" or not cfg.get("api_key"):
            _emb_client = LocalEmbedder(cfg.get("model", "BAAI/bge-small-zh-v1.5"))
        else:
            from kb_studio.core.llm.client import EmbeddingClient
            _emb_client = EmbeddingClient(cfg)
    return _emb_client


def _get_engine(kb_name: str) -> ChatEngine:
    if kb_name not in _engines:
        mgr = _get_manager()
        chunks = mgr.get_chunks(kb_name)
        cfg = mgr.get_config(kb_name)
        retrieval_cfg = cfg.get("retrieval", {})
        _engines[kb_name] = ChatEngine(
            llm_client=_get_llm(), embedding_client=_get_emb(),
            chunks=chunks, system_prompt=cfg.get("system_prompt", ""),
            retrieval_config=retrieval_cfg,
        )
    return _engines[kb_name]


# ── Tool Registry ──

_tool_registry = None


def _get_tool_registry():
    global _tool_registry
    if _tool_registry is None:
        from kb_studio.tools.registry import ToolRegistry
        from kb_studio.tools.builtin import register_builtin_tools
        from kb_studio.tools.storage import ToolStorage
        from kb_studio.tools.loader import ToolLoader
        _tool_registry = ToolRegistry()
        register_builtin_tools(
            _tool_registry,
            get_manager=_get_manager,
            get_engine=_get_engine,
            get_engines=lambda: _engines,
        )
        # Register butler tools for MCP exposure
        from kb_studio.tools.butler_tools import register_butler_tools
        register_butler_tools(
            _tool_registry,
            get_scheduler=_get_scheduler,
            get_notifications=_get_notifications,
            get_suggestions=_get_suggestions,
            get_global_memory=_get_global_memory,
            get_manager=_get_manager,
            get_source_monitor=_get_source_monitor,
        )
        # Load custom tools from disk
        storage = ToolStorage()
        loader = ToolLoader()
        _tool_registry.load_from_storage(storage, loader)
    return _tool_registry


# ── Models ──

class CreateKBRequest(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""


class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None


class ConfigUpdate(BaseModel):
    llm: dict | None = None
    embedding: dict | None = None


class RechunkRequest(BaseModel):
    strategy: str = "semantic"
    max_chunk_size: int = 512
    overlap: int = 128


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    strategy: str = "hybrid"
    vector_weight: float = 0.7
    bm25_weight: float = 0.3


class RetrievalConfigUpdate(BaseModel):
    top_k: int | None = None
    strategy: str | None = None
    vector_weight: float | None = None
    bm25_weight: float | None = None
    chunk_strategy: str | None = None
    chunk_params: dict | None = None


class CreateConversationRequest(BaseModel):
    name: str = "New Chat"
    system_prompt: str | None = None


class RenameRequest(BaseModel):
    name: str


# ── Endpoints ──

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/providers")
async def list_providers():
    from kb_studio.core.llm.providers import list_providers as lp
    return lp()


@app.post("/config")
async def update_config(update: ConfigUpdate):
    global _llm_client, _emb_client
    config_path = Path(CONFIG_PATH)
    existing = {}
    if config_path.exists():
        existing = yaml.safe_load(config_path.read_text()) or {}
    for key in ["llm", "embedding"]:
        val = getattr(update, key)
        if val is not None:
            existing[key] = val
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(existing, allow_unicode=True))
    _llm_client = None
    _emb_client = None
    _engines.clear()
    return {"status": "ok"}


@app.post("/test-connection")
async def test_connection():
    results = {}
    try:
        llm = _get_llm()
        resp = llm.chat_text(messages=[{"role": "user", "content": "Say OK"}], max_tokens=10)
        results["llm"] = {"status": "ok", "response": resp.strip()}
    except Exception as e:
        results["llm"] = {"status": "error", "error": str(e)}
    try:
        emb = _get_emb()
        v = emb.embed("test")
        results["embedding"] = {"status": "ok", "dimension": len(v)}
    except Exception as e:
        results["embedding"] = {"status": "error", "error": str(e)}
    return results


@app.get("/kb/list")
async def list_knowledge_bases():
    mgr = _get_manager()
    kbs = mgr.list()
    return {"knowledge_bases": [
        {"name": kb.name, "description": kb.description, "system_prompt": kb.system_prompt,
         "doc_count": kb.doc_count, "chunk_count": kb.chunk_count}
        for kb in kbs
    ]}


@app.post("/kb/create")
async def create_knowledge_base(req: CreateKBRequest):
    mgr = _get_manager()
    try:
        kb = mgr.create(req.name, req.description, req.system_prompt)
        return {"status": "ok", "name": kb.name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/kb/{name}")
async def delete_knowledge_base(name: str):
    mgr = _get_manager()
    try:
        mgr.delete(name)
        _engines.pop(name, None)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/kb/{name}/upload")
async def upload_document(name: str, file: UploadFile = File(...)):
    mgr = _get_manager()
    # Sanitize filename — strip directory components to prevent path traversal
    safe_name = Path(file.filename).name
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    tmp = Path("/tmp") / safe_name
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:  # 100MB limit
        raise HTTPException(status_code=413, detail="File too large (max 100MB)")
    tmp.write_bytes(content)
    try:
        result = mgr.add_document(name, str(tmp), embedding_client=_get_emb(), llm_client=_get_llm())
        _engines.pop(name, None)
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        tmp.unlink(missing_ok=True)


class URLUploadRequest(BaseModel):
    url: str


@app.post("/kb/{name}/upload-url")
async def upload_url(name: str, req: URLUploadRequest):
    """Import content from a URL (web page, YouTube, Wikipedia, etc.)."""
    from urllib.parse import urlparse
    from kb_studio.core.doc_processor.converter import DocumentConverter

    # Validate URL to prevent SSRF
    parsed = urlparse(req.url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid URL")
    # Block private/internal network ranges
    import ipaddress
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise HTTPException(status_code=400, detail="Private/internal URLs are not allowed")
    except ValueError:
        # hostname is a domain name, not an IP — allow it
        pass

    mgr = _get_manager()
    try:
        converter = DocumentConverter()
        doc = converter.convert_url(req.url)

        # Save as a temp file with unique name to avoid race conditions
        import uuid as _uuid
        tmp = Path("/tmp") / f"url_import_{_uuid.uuid4().hex[:8]}.md"
        tmp.write_text(doc.markdown, encoding="utf-8")
        try:
            result = mgr.add_document(name, str(tmp), embedding_client=_get_emb(), llm_client=_get_llm())
            _engines.pop(name, None)
            return {"status": "ok", **result, "source_url": req.url}
        finally:
            tmp.unlink(missing_ok=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"URL conversion failed: {str(e)}")


@app.get("/supported-formats")
async def get_supported_formats():
    """Return all supported file formats grouped by category."""
    from kb_studio.core.doc_processor.converter import DocumentConverter
    return DocumentConverter.get_supported_extensions()


@app.post("/kb/{name}/chat")
async def chat(name: str, req: ChatRequest):
    try:
        engine = _get_engine(name)
        mgr = _get_manager()
        memory_ctx = mgr.get_memory_context(name)

        # Always use conversations — resolve active if no id given
        conv_id = req.conversation_id
        if not conv_id:
            conv_id = mgr.get_active_conversation_id(name)
            if not conv_id:
                # Auto-create default conversation
                conv = mgr.create_conversation(name, "Default")
                conv_id = conv["id"]

        history = mgr.get_conversation_history(name, conv_id)
        history_msgs = [{"role": m["role"], "content": m["content"]} for m in history[-20:]]
        result = engine.chat(req.question, history_override=history_msgs, memory_context=memory_ctx)
        mgr.save_conversation_message(name, conv_id, {
            "role": "user", "content": req.question,
        })
        mgr.save_conversation_message(name, conv_id, {
            "role": "assistant", "content": result["answer"],
            "sources": result.get("sources", []),
        })
        result["conversation_id"] = conv_id

        # Auto-extract memory from conversation
        try:
            memories = engine.extract_memory(req.question, result["answer"])
            for mem in memories:
                mgr.add_memory_entry(name, mem["content"], mem.get("category", "general"),
                                     req.conversation_id, mem.get("importance", 0.5))
        except Exception:
            pass  # Don't fail chat if memory extraction fails

        # Extract user interests and sync to global memory
        try:
            interests = engine.extract_interests(req.question)
            gm = _get_global_memory()
            for topic in interests.get("topics", []):
                gm.add_interest(topic)
        except Exception:
            pass

        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{name}' not found")


@app.delete("/kb/{name}/history")
async def clear_history(name: str, conversation_id: str | None = None):
    """Clear conversation history. Clears active conversation if no id given."""
    mgr = _get_manager()
    conv_id = conversation_id or mgr.get_active_conversation_id(name)
    if conv_id:
        mgr.clear_conversation(name, conv_id)
    return {"status": "ok"}


# ── Document Management ──

@app.get("/kb/{name}/documents")
async def list_documents(name: str):
    mgr = _get_manager()
    try:
        docs = mgr.list_documents(name)
        # Add freshness info
        from datetime import datetime as _dt
        now = _dt.utcnow()
        for doc in docs:
            upload_time = doc.get("upload_time", "")
            if upload_time:
                try:
                    uploaded = _dt.fromisoformat(upload_time.replace("Z", "+00:00")).replace(tzinfo=None)
                    age_days = (now - uploaded).days
                    doc["age_days"] = age_days
                    doc["freshness"] = "stale" if age_days > 30 else "aging" if age_days > 7 else "fresh"
                except (ValueError, TypeError):
                    doc["age_days"] = -1
                    doc["freshness"] = "unknown"
            else:
                doc["age_days"] = -1
                doc["freshness"] = "unknown"
        return {"documents": docs}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/kb/{name}/documents/{filename}")
async def get_document_content(name: str, filename: str):
    mgr = _get_manager()
    try:
        content = mgr.get_document_content(name, filename)
        return {"filename": filename, "content": content}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/kb/{name}/documents/{filename}/chunks")
async def get_document_chunks(name: str, filename: str):
    mgr = _get_manager()
    return {"chunks": mgr.get_document_chunks(name, filename)}


@app.delete("/kb/{name}/documents/{filename}")
async def delete_document(name: str, filename: str):
    mgr = _get_manager()
    try:
        result = mgr.delete_document(name, filename)
        _engines.pop(name, None)
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/kb/{name}/documents/{filename}/rechunk")
async def rechunk_document(name: str, filename: str, req: RechunkRequest):
    mgr = _get_manager()
    try:
        result = mgr.rechunk_document(name, filename, req.strategy, req.max_chunk_size, req.overlap)
        _engines.pop(name, None)
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Search & Retrieval Config ──

@app.post("/kb/{name}/search")
async def search_kb(name: str, req: SearchRequest):
    try:
        engine = _get_engine(name)
        return engine.search(req.query, top_k=req.top_k, strategy=req.strategy,
                             vector_weight=req.vector_weight, bm25_weight=req.bm25_weight)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{name}' not found")


@app.get("/kb/{name}/config/retrieval")
async def get_retrieval_config(name: str):
    mgr = _get_manager()
    cfg = mgr.get_config(name)
    retrieval = cfg.get("retrieval", {
        "top_k": 5, "strategy": "hybrid",
        "vector_weight": 0.7, "bm25_weight": 0.3,
        "chunk_strategy": "semantic",
        "chunk_params": {"max_chunk_size": 512, "overlap": 128},
    })
    return retrieval


@app.put("/kb/{name}/config/retrieval")
async def update_retrieval_config(name: str, req: RetrievalConfigUpdate):
    mgr = _get_manager()
    cfg = mgr.get_config(name)
    retrieval = cfg.get("retrieval", {})
    for field in ["top_k", "strategy", "vector_weight", "bm25_weight", "chunk_strategy", "chunk_params"]:
        val = getattr(req, field, None)
        if val is not None:
            retrieval[field] = val
    mgr.update_config(name, {"retrieval": retrieval})
    _engines.pop(name, None)
    return {"status": "ok", "retrieval": retrieval}


# ── Conversations ──

@app.get("/kb/{name}/conversations")
async def list_conversations(name: str):
    mgr = _get_manager()
    convs = mgr.list_conversations(name)
    active_id = mgr.get_active_conversation_id(name)
    return {"conversations": convs, "active_conversation_id": active_id}


@app.post("/kb/{name}/conversations")
async def create_conversation(name: str, req: CreateConversationRequest):
    mgr = _get_manager()
    conv = mgr.create_conversation(name, req.name, req.system_prompt)
    return {"status": "ok", **conv}


@app.get("/kb/{name}/conversations/{conv_id}")
async def get_conversation(name: str, conv_id: str):
    mgr = _get_manager()
    messages = mgr.get_conversation_history(name, conv_id)
    return {"messages": messages}


@app.delete("/kb/{name}/conversations/{conv_id}")
async def delete_conversation(name: str, conv_id: str):
    mgr = _get_manager()
    mgr.delete_conversation(name, conv_id)
    return {"status": "ok"}


@app.put("/kb/{name}/conversations/{conv_id}")
async def rename_conversation(name: str, conv_id: str, req: RenameRequest):
    mgr = _get_manager()
    mgr.rename_conversation(name, conv_id, req.name)
    return {"status": "ok"}


@app.get("/kb/{name}/conversations/{conv_id}/export")
async def export_conversation(name: str, conv_id: str):
    mgr = _get_manager()
    md = mgr.export_conversation(name, conv_id)
    return {"content": md}


@app.post("/kb/{name}/conversations/{conv_id}/set-active")
async def set_active_conversation(name: str, conv_id: str):
    mgr = _get_manager()
    mgr.set_active_conversation(name, conv_id)
    return {"status": "ok"}


# ── Memory ──

class AddMemoryRequest(BaseModel):
    content: str
    category: str = "general"
    importance: float = 0.5

class UpdateSummaryRequest(BaseModel):
    summary: str


@app.get("/kb/{name}/memory")
async def get_memory(name: str):
    mgr = _get_manager()
    return mgr.get_memory(name)


@app.post("/kb/{name}/memory")
async def add_memory(name: str, req: AddMemoryRequest):
    mgr = _get_manager()
    entry = mgr.add_memory_entry(name, req.content, req.category, importance=req.importance)
    return {"status": "ok", **entry}


@app.delete("/kb/{name}/memory/{entry_id}")
async def delete_memory(name: str, entry_id: str):
    mgr = _get_manager()
    mgr.delete_memory_entry(name, entry_id)
    return {"status": "ok"}


@app.put("/kb/{name}/memory/summary")
async def update_memory_summary(name: str, req: UpdateSummaryRequest):
    mgr = _get_manager()
    mgr.update_memory_summary(name, req.summary)
    return {"status": "ok"}


# ── Knowledge Findings (contradiction / duplicate detection) ──

@app.get("/kb/{name}/findings")
async def get_findings(name: str, type: str | None = None, status: str | None = None):
    """Get knowledge quality findings (contradictions, duplicates, updates)."""
    mgr = _get_manager()
    return {"findings": mgr.get_findings(name, type_filter=type, status_filter=status)}


@app.get("/kb/{name}/findings/summary")
async def get_findings_summary(name: str):
    """Get summary of findings by type and status."""
    mgr = _get_manager()
    return mgr.get_findings_summary(name)


@app.post("/kb/{name}/findings/{finding_id}/resolve")
async def resolve_finding(name: str, finding_id: str):
    """Mark a finding as resolved."""
    mgr = _get_manager()
    try:
        mgr.update_finding_status(name, finding_id, "resolved")
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/kb/{name}/findings/{finding_id}/dismiss")
async def dismiss_finding(name: str, finding_id: str):
    """Dismiss a finding (ignore)."""
    mgr = _get_manager()
    try:
        mgr.update_finding_status(name, finding_id, "dismissed")
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/kb/{name}/analyze")
async def analyze_kb(name: str):
    """Trigger a full knowledge quality analysis on all existing chunks."""
    from kb_studio.knowledge_analyzer import KnowledgeAnalyzer

    mgr = _get_manager()
    chunks = mgr.get_chunks(name)
    if len(chunks) < 2:
        return {"status": "ok", "message": "Not enough chunks to analyze", "findings_count": 0}

    try:
        analyzer = KnowledgeAnalyzer()
        findings = analyzer.analyze_all_chunks(chunks, _get_emb(), _get_llm())
        if findings:
            kb_path = mgr.data_dir / name
            mgr._save_findings(kb_path, findings)
        return {
            "status": "ok",
            "findings_count": len(findings),
            "findings_summary": {
                "contradictions": sum(1 for f in findings if f["type"] == "contradiction"),
                "duplicates": sum(1 for f in findings if f["type"] == "duplicate"),
                "updates": sum(1 for f in findings if f["type"] == "update"),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


# ── Pipeline ──

class PipelineUpdate(BaseModel):
    enabled: bool = True
    steps: list[dict] = []

class PipelineChatRequest(BaseModel):
    question: str
    kb_names: list[str] | None = None
    conversation_id: str | None = None


@app.get("/kb/{name}/pipeline")
async def get_pipeline(name: str):
    mgr = _get_manager()
    return mgr.get_pipeline(name)


@app.put("/kb/{name}/pipeline")
async def update_pipeline(name: str, req: PipelineUpdate):
    mgr = _get_manager()
    mgr.update_pipeline(name, {"enabled": req.enabled, "steps": req.steps})
    return {"status": "ok"}


@app.post("/kb/{name}/pipeline/chat")
async def pipeline_chat(name: str, req: PipelineChatRequest):
    """Run a question through the agent pipeline."""
    from kb_studio.agent_pipeline import AgentPipeline

    mgr = _get_manager()
    pipeline_cfg = mgr.get_pipeline(name)

    # Resolve conversation_id
    conv_id = req.conversation_id
    if not conv_id:
        conv_id = mgr.get_active_conversation_id(name)
        if not conv_id:
            conv = mgr.create_conversation(name, "Default")
            conv_id = conv["id"]

    if not pipeline_cfg.get("enabled"):
        # Fall back to normal chat
        engine = _get_engine(name)
        memory_ctx = mgr.get_memory_context(name)
        history = mgr.get_conversation_history(name, conv_id)
        history_msgs = [{"role": m["role"], "content": m["content"]} for m in history[-20:]]
        result = engine.chat(req.question, history_override=history_msgs, memory_context=memory_ctx)
        mgr.save_conversation_message(name, conv_id, {"role": "user", "content": req.question})
        mgr.save_conversation_message(name, conv_id, {
            "role": "assistant", "content": result["answer"], "sources": result.get("sources", []),
        })
        result["conversation_id"] = conv_id
        return {"mode": "chat", **result}

    # Ensure all referenced engines are loaded
    steps = pipeline_cfg.get("steps", [])
    kb_names_in_steps = set()
    for step in steps:
        for kb in step.get("kb_names", []):
            kb_names_in_steps.add(kb)
    kb_names_in_steps.add(name)

    for kb_n in kb_names_in_steps:
        try:
            _get_engine(kb_n)
        except Exception:
            pass

    memory_ctx = mgr.get_memory_context(name)
    pipeline = AgentPipeline(_get_llm(), _engines)
    result = pipeline.run(req.question, steps, memory_ctx)

    # Save to conversation
    answer = result.get("answer", "")
    mgr.save_conversation_message(name, conv_id, {"role": "user", "content": req.question})
    mgr.save_conversation_message(name, conv_id, {
        "role": "assistant", "content": answer, "sources": result.get("sources", []),
    })
    result["conversation_id"] = conv_id

    # Auto-extract memory
    if answer:
        try:
            engine = _get_engine(name)
            memories = engine.extract_memory(req.question, answer)
            for mem in memories:
                mgr.add_memory_entry(name, mem["content"], mem.get("category", "general"),
                                     conv_id, mem.get("importance", 0.5))
        except Exception:
            pass

    return {"mode": "pipeline", **result}


# ── Agent Chat ──

class AgentChatRequest(BaseModel):
    question: str
    kb_name: str | None = None
    conversation_id: str | None = None
    max_iterations: int = 10


@app.post("/agent/chat")
async def agent_chat(req: AgentChatRequest):
    """Agent chat with tool calling — LLM decides which tools to use."""
    from kb_studio.agent_chat import AgentChatEngine

    registry = _get_tool_registry()
    mgr = _get_manager()
    llm = _get_llm()

    # Build system prompt with KB context if specified
    system_prompt = ""
    if req.kb_name:
        cfg = mgr.get_config(req.kb_name)
        system_prompt = cfg.get("system_prompt", "")

    agent = AgentChatEngine(llm, registry, system_prompt=system_prompt)

    # Resolve conversation
    conv_id = req.conversation_id
    if not conv_id:
        conv_id = mgr.get_active_conversation_id(req.kb_name or "") or ""
        if not conv_id and req.kb_name:
            conv = mgr.create_conversation(req.kb_name, "Agent Chat")
            conv_id = conv["id"]

    history = []
    if conv_id and req.kb_name:
        raw = mgr.get_conversation_history(req.kb_name, conv_id)
        history = [{"role": m["role"], "content": m["content"]} for m in raw[-20:]]

    memory_ctx = ""
    if req.kb_name:
        memory_ctx = mgr.get_memory_context(req.kb_name)

    result = agent.chat(
        req.question,
        history=history,
        memory_context=memory_ctx,
        max_iterations=req.max_iterations,
    )

    # Save to conversation
    if conv_id and req.kb_name:
        mgr.save_conversation_message(req.kb_name, conv_id, {
            "role": "user", "content": req.question,
        })
        mgr.save_conversation_message(req.kb_name, conv_id, {
            "role": "assistant", "content": result.get("content", ""),
            "sources": result.get("sources", []),
        })
        result["conversation_id"] = conv_id

    return result


# ── Tools ──

from kb_studio.tools.schema import (
    ToolCreateRequest, ToolUpdateRequest, ToolTestRequest,
    ToolGenerateRequest, ToolRefineRequest,
)

@app.get("/tools")
async def list_tools(source: str | None = None):
    """List all registered tools."""
    registry = _get_tool_registry()
    tools = registry.list_tools(source=source)
    return {"tools": [t.to_dict() for t in tools]}


@app.get("/tools/{name}")
async def get_tool(name: str):
    """Get tool details and implementation code."""
    registry = _get_tool_registry()
    definition = registry.get(name)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")

    result = {"tool": definition.to_dict()}
    # Include code for custom/generated tools
    if definition.source in ("custom", "generated"):
        from kb_studio.tools.storage import ToolStorage
        storage = ToolStorage()
        code = storage.get_code(name)
        if code:
            result["code"] = code
    return result


async def _create_tool_impl(req: ToolCreateRequest, source: str = "custom") -> dict:
    """Shared logic for creating a tool (custom or generated)."""
    from kb_studio.tools.storage import ToolStorage
    from kb_studio.tools.loader import ToolLoader
    from kb_studio.tools.registry import ToolDefinition

    registry = _get_tool_registry()
    if req.name in registry:
        raise HTTPException(status_code=409, detail=f"Tool '{req.name}' already exists")

    loader = ToolLoader()
    errors = loader.validate_code(req.code)
    if errors:
        raise HTTPException(status_code=400, detail={"message": "代码验证失败", "errors": errors})

    definition = ToolDefinition(
        name=req.name, description=req.description,
        parameters=req.parameters, source=source, enabled=True, tags=req.tags,
    )
    try:
        handler = loader.load_tool(definition, req.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    storage = ToolStorage()
    storage.save(definition, req.code)
    registry.register(definition, handler)
    return {"status": "ok", "tool": definition.to_dict()}


@app.post("/tools")
async def create_tool(req: ToolCreateRequest):
    """Create a new custom tool."""
    return await _create_tool_impl(req, source="custom")


# ── Tool Code Generation (must be before /tools/{name} routes) ──

@app.post("/tools/generate")
async def generate_tool(req: ToolGenerateRequest):
    """Generate a tool from natural language description. Returns preview, does NOT save."""
    from kb_studio.tools.codegen import ToolCodeGenerator

    try:
        gen = ToolCodeGenerator(_get_llm())
        tool = gen.generate(req.description, req.context)
        tool, warnings = gen.validate_and_fix(tool)
        return {"status": "ok", "tool": tool.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")


@app.post("/tools/generate/refine")
async def refine_generated_tool(req: ToolRefineRequest):
    """Refine a generated tool based on feedback."""
    from kb_studio.tools.codegen import ToolCodeGenerator

    try:
        gen = ToolCodeGenerator(_get_llm())
        tool = gen.refine(req.code, req.feedback)
        tool, warnings = gen.validate_and_fix(tool)
        return {"status": "ok", "tool": tool.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"优化失败: {e}")


@app.post("/tools/generate/save")
async def save_generated_tool(req: ToolCreateRequest):
    """Save a generated tool."""
    return await _create_tool_impl(req, source="generated")


@app.put("/tools/{name}")
async def update_tool(name: str, req: ToolUpdateRequest):
    """Update a custom tool."""
    from kb_studio.tools.storage import ToolStorage
    from kb_studio.tools.loader import ToolLoader

    registry = _get_tool_registry()
    definition = registry.get(name)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    if definition.source == "builtin":
        raise HTTPException(status_code=403, detail="Cannot modify built-in tools")

    storage = ToolStorage()
    existing = storage.load(name)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found on disk")

    old_def, old_code = existing

    # Update fields
    if req.description is not None:
        old_def.description = req.description
    if req.parameters is not None:
        old_def.parameters = req.parameters
    if req.enabled is not None:
        old_def.enabled = req.enabled
    if req.tags is not None:
        old_def.tags = req.tags

    code = req.code if req.code is not None else old_code

    if req.code is not None:
        loader = ToolLoader()
        errors = loader.validate_code(code)
        if errors:
            raise HTTPException(status_code=400, detail={"message": "代码验证失败", "errors": errors})
        try:
            handler = loader.load_tool(old_def, code)
            registry.unregister(name)
            registry.register(old_def, handler)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # Just update metadata, re-register with same handler
        registry.unregister(name)
        loader = ToolLoader()
        try:
            handler = loader.load_tool(old_def, code)
            registry.register(old_def, handler)
        except Exception:
            pass

    storage.save(old_def, code)
    return {"status": "ok", "tool": old_def.to_dict()}


@app.delete("/tools/{name}")
async def delete_tool(name: str):
    """Delete a custom tool."""
    from kb_studio.tools.storage import ToolStorage

    registry = _get_tool_registry()
    definition = registry.get(name)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    if definition.source == "builtin":
        raise HTTPException(status_code=403, detail="Cannot delete built-in tools")

    storage = ToolStorage()
    storage.delete(name)
    registry.unregister(name)
    return {"status": "ok"}


@app.post("/tools/{name}/test")
async def test_tool(name: str, req: ToolTestRequest):
    """Test a tool with sample input."""
    registry = _get_tool_registry()
    if name not in registry:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")

    import time
    start = time.time()
    result = registry.execute(name, req.args, context={})
    elapsed_ms = round((time.time() - start) * 1000, 1)

    return {
        "result": result.result,
        "error": result.error,
        "duration_ms": elapsed_ms,
    }


@app.post("/tools/{name}/enable")
async def enable_tool(name: str):
    """Enable a tool."""
    from kb_studio.tools.storage import ToolStorage

    registry = _get_tool_registry()
    definition = registry.get(name)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    definition.enabled = True
    # Persist if custom
    if definition.source in ("custom", "generated"):
        storage = ToolStorage()
        code = storage.get_code(name) or ""
        storage.save(definition, code)
    return {"status": "ok", "enabled": True}


@app.post("/tools/{name}/disable")
async def disable_tool(name: str):
    """Disable a tool."""
    from kb_studio.tools.storage import ToolStorage

    registry = _get_tool_registry()
    definition = registry.get(name)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    definition.enabled = False
    if definition.source in ("custom", "generated"):
        storage = ToolStorage()
        code = storage.get_code(name) or ""
        storage.save(definition, code)
    return {"status": "ok", "enabled": False}


# ── MCP Server ──

_mcp_server = None


def _get_mcp_server():
    global _mcp_server
    if _mcp_server is None:
        try:
            from kb_studio.mcp.server import KBStudioMCPServer
            _mcp_server = KBStudioMCPServer(
                _get_tool_registry(),
                get_llm=_get_llm,
                get_manager=_get_manager,
            )
        except ImportError:
            return None
    return _mcp_server


@app.get("/mcp/status")
async def mcp_status():
    """Get MCP server status."""
    mcp = _get_mcp_server()
    if mcp is None:
        return {"running": False, "error": "mcp package not installed. Run: pip install mcp"}
    return mcp.get_status()


@app.get("/mcp/config")
async def mcp_config(host: str = "localhost", port: int = 8000):
    """Get MCP client configuration for Claude Desktop, Cursor, etc."""
    mcp = _get_mcp_server()
    if mcp is None:
        raise HTTPException(status_code=503, detail="mcp package not installed")
    return mcp.get_client_config(host=host, port=port)


# Mount MCP SSE transport if mcp package is available
try:
    _mcp = _get_mcp_server()
    if _mcp is not None:
        _mcp_app = _mcp.get_sse_app(mount_path="/mcp/sse")
        app.mount("/mcp", _mcp_app)
except Exception as _mcp_err:
    import sys
    print(f"[KB-Studio] MCP mount failed (optional): {_mcp_err}", file=sys.stderr)


# ── WebSocket ──

from fastapi import WebSocket as WS, WebSocketDisconnect

@app.websocket("/ws")
async def websocket_endpoint(ws: WS):
    await _ws_broadcaster.connect(ws)
    try:
        while True:
            # Keep connection alive, receive pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await _ws_broadcaster.disconnect(ws)


# ── Scheduler / Notifications / Source Monitor / Export ──

_scheduler = None
_notifications = None
_source_monitor = None
_exporter = None


def _get_scheduler():
    global _scheduler
    if _scheduler is None:
        from kb_studio.scheduler import TaskScheduler, TaskType
        from kb_studio.scheduler.handlers import (
            create_source_monitor_handler,
            create_kb_analyze_handler,
            create_digest_handler,
            create_memory_sync_handler,
            create_suggestions_handler,
        )
        _scheduler = TaskScheduler()
        _scheduler.register_handler(TaskType.SOURCE_MONITOR, create_source_monitor_handler(
            _get_source_monitor(), _get_manager(), _get_notifications(),
            get_emb_fn=_get_emb, get_llm_fn=_get_llm,
            clear_engine_fn=lambda name: _engines.pop(name, None),
        ))
        _scheduler.register_handler(TaskType.KB_ANALYZE, create_kb_analyze_handler(
            _get_manager(), get_emb_fn=_get_emb, get_llm_fn=_get_llm
        ))
        _scheduler.register_handler(TaskType.DIGEST, create_digest_handler(
            _get_manager(), _get_notifications()
        ))
        _scheduler.register_handler(TaskType.MEMORY_SYNC, create_memory_sync_handler(
            _get_global_memory(), _get_manager()
        ))
        _scheduler.register_handler(TaskType.SUGGESTIONS, create_suggestions_handler(
            _get_suggestions(), _get_manager(), _get_global_memory(), _get_notifications()
        ))
        # Wire notification callback (persist + broadcast via WS)
        async def _notify(title, body, level, details):
            _get_notifications().add(title=title, body=body, level=level, source="scheduler", details=details)
            await _ws_broadcaster.notify(title, body, level, "scheduler")
        _scheduler.set_notification_callback(_notify)
    return _scheduler


def _get_notifications():
    global _notifications
    if _notifications is None:
        from kb_studio.notifications import NotificationStore
        _notifications = NotificationStore()
    return _notifications


def _get_source_monitor():
    global _source_monitor
    if _source_monitor is None:
        from kb_studio.notifications.source_monitor import SourceMonitor
        _source_monitor = SourceMonitor()
    return _source_monitor


def _get_exporter():
    global _exporter
    if _exporter is None:
        from kb_studio.export import KBExporter
        _exporter = KBExporter()
    return _exporter


def _get_kb_analyzer():
    from kb_studio.knowledge_analyzer import KnowledgeAnalyzer
    return KnowledgeAnalyzer


# ── Scheduler API ──

class CreateTaskRequest(BaseModel):
    name: str
    task_type: str  # source_monitor, kb_analyze, digest, custom
    interval: str   # 5m, 15m, 30m, 1h, 6h, 12h, 1d, 1w
    config: dict = {}
    description: str = ""


@app.get("/scheduler/status")
async def scheduler_status():
    scheduler = _get_scheduler()
    return scheduler.get_status()


@app.get("/scheduler/tasks")
async def list_scheduled_tasks(task_type: str = None):
    scheduler = _get_scheduler()
    tasks = scheduler.list_tasks(task_type)
    return {"tasks": [t.to_summary() for t in tasks]}


@app.post("/scheduler/tasks")
async def create_scheduled_task(req: CreateTaskRequest):
    from kb_studio.scheduler import TaskType, Interval
    scheduler = _get_scheduler()
    try:
        task = scheduler.create_task(
            name=req.name,
            task_type=TaskType(req.task_type),
            interval=Interval(req.interval),
            config=req.config,
            description=req.description,
        )
        return {"status": "ok", "task": task.to_dict()}
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/scheduler/tasks/{task_id}")
async def get_scheduled_task(task_id: str):
    scheduler = _get_scheduler()
    task = scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task.to_dict()}


@app.put("/scheduler/tasks/{task_id}")
async def update_scheduled_task(task_id: str, updates: dict):
    scheduler = _get_scheduler()
    task = scheduler.update_task(task_id, **updates)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "task": task.to_dict()}


@app.delete("/scheduler/tasks/{task_id}")
async def delete_scheduled_task(task_id: str):
    scheduler = _get_scheduler()
    if not scheduler.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


@app.post("/scheduler/tasks/{task_id}/run")
async def run_task_now(task_id: str):
    scheduler = _get_scheduler()
    run = await scheduler.run_task_now(task_id)
    if not run:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "run": run.to_dict()}


@app.post("/scheduler/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    scheduler = _get_scheduler()
    task = scheduler.pause_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "task": task.to_summary()}


@app.post("/scheduler/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    scheduler = _get_scheduler()
    task = scheduler.resume_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "task": task.to_summary()}


# ── Notifications API ──

@app.get("/notifications")
async def list_notifications(limit: int = 50, unread_only: bool = False):
    store = _get_notifications()
    notifs = store.list_all(limit=limit, unread_only=unread_only)
    return {
        "notifications": [n.to_dict() for n in notifs],
        "unread_count": store.unread_count(),
    }


@app.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    store = _get_notifications()
    if not store.mark_read(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok"}


@app.post("/notifications/read-all")
async def mark_all_notifications_read():
    store = _get_notifications()
    count = store.mark_all_read()
    return {"status": "ok", "count": count}


@app.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: str):
    store = _get_notifications()
    if not store.delete(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok"}


@app.delete("/notifications")
async def clear_notifications():
    store = _get_notifications()
    count = store.clear_all()
    return {"status": "ok", "count": count}


# ── Source Monitor API ──

class AddWatchRequest(BaseModel):
    url: str
    kb_name: str
    name: str = ""
    watch_type: str = "url"
    interval: str = "1d"


@app.get("/sources")
async def list_source_watches(kb_name: str = None):
    monitor = _get_source_monitor()
    watches = monitor.list_watches(kb_name)
    return {"watches": [w.to_dict() for w in watches]}


@app.post("/sources")
async def add_source_watch(req: AddWatchRequest):
    monitor = _get_source_monitor()
    watch = monitor.add_watch(
        url=req.url,
        kb_name=req.kb_name,
        name=req.name,
        watch_type=req.watch_type,
        interval=req.interval,
    )
    return {"status": "ok", "watch": watch.to_dict()}


@app.delete("/sources/{watch_id}")
async def delete_source_watch(watch_id: str):
    monitor = _get_source_monitor()
    if not monitor.delete_watch(watch_id):
        raise HTTPException(status_code=404, detail="Watch not found")
    return {"status": "ok"}


@app.post("/sources/{watch_id}/toggle")
async def toggle_source_watch(watch_id: str):
    monitor = _get_source_monitor()
    watch = monitor.toggle_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    return {"status": "ok", "watch": watch.to_dict()}


@app.post("/sources/{watch_id}/check")
async def check_source_now(watch_id: str):
    monitor = _get_source_monitor()
    result = await monitor.check_and_update(
        watch_id, None, _get_manager(), _get_notifications(),
        embedding_client=_get_emb(), llm_client=_get_llm(),
        clear_engine_fn=lambda name: _engines.pop(name, None),
    )
    return result


# ── Suggestions ──

_suggestion_engine = None

def _get_suggestions():
    global _suggestion_engine
    if _suggestion_engine is None:
        from kb_studio.suggestions import SuggestionEngine
        _suggestion_engine = SuggestionEngine()
    return _suggestion_engine


@app.get("/suggestions")
async def list_suggestions(include_dismissed: bool = False):
    engine = _get_suggestions()
    return {"suggestions": engine.list_suggestions(include_dismissed)}


@app.post("/suggestions/generate")
async def generate_suggestions():
    engine = _get_suggestions()
    new = engine.generate(_get_manager(), _get_global_memory(), _get_notifications())
    return {"status": "ok", "new_count": len(new), "new_suggestions": new}


@app.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(suggestion_id: str):
    engine = _get_suggestions()
    if not engine.dismiss(suggestion_id):
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return {"status": "ok"}


# ── Global Memory ──

_global_memory = None

def _get_global_memory():
    global _global_memory
    if _global_memory is None:
        from kb_studio.global_memory import GlobalMemory
        _global_memory = GlobalMemory()
    return _global_memory


@app.get("/memory/global")
async def get_global_memory():
    gm = _get_global_memory()
    return {"entries": gm.get_unified_entries(), "profile": gm.get_profile()}


@app.get("/memory/global/summary")
async def get_global_memory_summary():
    gm = _get_global_memory()
    return gm.get_summary()


@app.post("/memory/global/sync")
async def sync_global_memory():
    gm = _get_global_memory()
    result = gm.sync_from_kbs(_get_manager())
    return {"status": "ok", **result}


@app.post("/memory/global/interest")
async def add_interest(req: dict):
    gm = _get_global_memory()
    interest = req.get("interest", "")
    if interest:
        gm.add_interest(interest)
    return {"status": "ok"}


@app.post("/memory/global/preference")
async def add_preference(req: dict):
    gm = _get_global_memory()
    pref = req.get("preference", "")
    if pref:
        gm.add_preference(pref)
    return {"status": "ok"}


# ── Staleness Overview ──

@app.get("/staleness")
async def staleness_overview():
    """Get freshness status of all documents across all KBs."""
    mgr = _get_manager()
    from datetime import datetime as _dt
    now = _dt.utcnow()
    result = {"total_docs": 0, "fresh": 0, "aging": 0, "stale": 0, "stale_docs": []}
    for kb in mgr.list():
        docs = mgr.list_documents(kb.name)
        for doc in docs:
            result["total_docs"] += 1
            upload_time = doc.get("upload_time", "")
            if upload_time:
                try:
                    uploaded = _dt.fromisoformat(upload_time.replace("Z", "+00:00")).replace(tzinfo=None)
                    age_days = (now - uploaded).days
                    if age_days > 30:
                        result["stale"] += 1
                        result["stale_docs"].append({"kb": kb.name, "doc": doc.get("filename", ""), "age_days": age_days})
                    elif age_days > 7:
                        result["aging"] += 1
                    else:
                        result["fresh"] += 1
                except (ValueError, TypeError):
                    pass
    return result


# ── Export API ──

from fastapi.responses import Response


@app.get("/export/kb/{kb_name}/zip")
async def export_kb_zip(kb_name: str):
    exporter = _get_exporter()
    try:
        data = exporter.export_kb_zip(kb_name)
        return Response(
            content=data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{kb_name}.zip"'},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Knowledge base not found")


@app.get("/export/kb/{kb_name}/markdown")
async def export_kb_markdown(kb_name: str):
    exporter = _get_exporter()
    try:
        content = exporter.export_kb_markdown(kb_name)
        return Response(
            content=content.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{kb_name}.md"'},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Knowledge base not found")


@app.get("/export/kb/{kb_name}/report")
async def export_kb_report(kb_name: str):
    exporter = _get_exporter()
    content = exporter.export_findings_report(kb_name)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{kb_name}-report.md"'},
    )


@app.get("/export/all/zip")
async def export_all_zip():
    exporter = _get_exporter()
    data = exporter.export_all_zip()
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="kb-studio-backup.zip"'},
    )


@app.post("/import/kb")
async def import_kb_zip(file: UploadFile = File(...), name: str = Form("")):
    """Import a knowledge base from a ZIP package."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 ZIP 文件")
    data = await file.read()
    exporter = _get_exporter()
    try:
        result = exporter.import_kb_zip(data, rename_to=name or None)
        # Clear engine cache so the new KB is accessible
        _engines.pop(result["kb_name"], None)
        return {"status": "ok", **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"导入失败: {e}")


# ── Frontend ──
DIST_DIR = Path(__file__).parent.parent / "web" / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/_next", StaticFiles(directory=str(DIST_DIR / "_next")), name="next-static")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = DIST_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(DIST_DIR / "index.html"))
