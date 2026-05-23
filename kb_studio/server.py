"""KB-Studio API server."""

import json
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from kb_studio.kb_manager import KBManager
from kb_studio.chat_engine import ChatEngine
from kb_studio.core.llm.client import LLMClient
from kb_studio.core.llm.local_embedder import LocalEmbedder

app = FastAPI(title="KB-Studio", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CONFIG_PATH = "config/active.yaml"

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
        history_file = str(mgr.data_dir / kb_name / "chat_history.json")
        _engines[kb_name] = ChatEngine(
            llm_client=_get_llm(), embedding_client=_get_emb(),
            chunks=chunks, system_prompt=cfg.get("system_prompt", ""),
            history_file=history_file,
        )
    return _engines[kb_name]


# ── Models ──

class CreateKBRequest(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""


class ChatRequest(BaseModel):
    question: str


class ConfigUpdate(BaseModel):
    llm: dict | None = None
    embedding: dict | None = None


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
    # Save temp file
    tmp = Path("/tmp") / file.filename
    tmp.write_bytes(await file.read())
    try:
        result = mgr.add_document(name, str(tmp))
        _engines.pop(name, None)  # Reset engine to reload chunks
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        tmp.unlink(missing_ok=True)


@app.post("/kb/{name}/chat")
async def chat(name: str, req: ChatRequest):
    try:
        engine = _get_engine(name)
        return engine.chat(req.question)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{name}' not found")


@app.delete("/kb/{name}/history")
async def clear_history(name: str):
    if name in _engines:
        _engines[name].clear_history()
    return {"status": "ok"}


# ── Frontend ──
DIST_DIR = Path(__file__).parent.parent / "web" / "frontend" / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = DIST_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(DIST_DIR / "index.html"))
