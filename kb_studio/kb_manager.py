"""Knowledge Base manager — create, list, delete, index knowledge bases."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from kb_studio.core.doc_processor.converter import DocumentConverter
from kb_studio.core.doc_processor.chunker import get_chunker


@dataclass
class KnowledgeBase:
    name: str
    path: Path
    description: str = ""
    system_prompt: str = "根据知识库中的文档回答用户问题。如果文档中没有相关信息，请如实说明。"
    doc_count: int = 0
    chunk_count: int = 0


class KBManager:
    """Manages knowledge bases: create, delete, list, add documents."""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ── KB CRUD ──

    def list(self) -> list[KnowledgeBase]:
        kbs = []
        for d in sorted(self.data_dir.iterdir()):
            if d.is_dir() and (d / "config.yaml").exists():
                cfg = yaml.safe_load((d / "config.yaml").read_text())
                chunks_file = d / "chunks.json"
                chunk_count = len(json.loads(chunks_file.read_text())) if chunks_file.exists() else 0

                # Use documents.json as authoritative doc count when available
                docs_json = d / "documents.json"
                if docs_json.exists():
                    doc_count = len(json.loads(docs_json.read_text()))
                else:
                    docs_dir = d / "docs"
                    if docs_dir.exists():
                        doc_count = sum(1 for f in docs_dir.iterdir() if f.is_file() and not f.name.endswith(".md"))
                    else:
                        doc_count = 0
                kbs.append(KnowledgeBase(
                    name=d.name, path=d,
                    description=cfg.get("description", ""),
                    system_prompt=cfg.get("system_prompt", ""),
                    doc_count=doc_count, chunk_count=chunk_count,
                ))
        return kbs

    def create(self, name: str, description: str = "", system_prompt: str = "") -> KnowledgeBase:
        kb_path = self.data_dir / name
        if kb_path.exists():
            raise ValueError(f"Knowledge base '{name}' already exists")

        kb_path.mkdir(parents=True)
        (kb_path / "docs").mkdir()

        cfg = {
            "name": name,
            "description": description,
            "system_prompt": system_prompt or "根据知识库中的文档回答用户问题。如果文档中没有相关信息，请如实说明。",
        }
        (kb_path / "config.yaml").write_text(yaml.dump(cfg, allow_unicode=True))
        (kb_path / "chunks.json").write_text("[]")
        (kb_path / "documents.json").write_text("[]")

        return KnowledgeBase(name=name, path=kb_path, description=description,
                            system_prompt=cfg["system_prompt"])

    def delete(self, name: str):
        kb_path = self.data_dir / name
        if not kb_path.exists():
            raise ValueError(f"Knowledge base '{name}' not found")
        shutil.rmtree(kb_path)

    def get_chunks(self, name: str) -> list[dict]:
        kb_path = self.data_dir / name
        chunks_file = kb_path / "chunks.json"
        if not chunks_file.exists():
            return []
        return json.loads(chunks_file.read_text())

    def get_config(self, name: str) -> dict:
        kb_path = self.data_dir / name
        cfg_file = kb_path / "config.yaml"
        if not cfg_file.exists():
            return {}
        return yaml.safe_load(cfg_file.read_text())

    def update_config(self, name: str, updates: dict):
        kb_path = self.data_dir / name
        cfg_file = kb_path / "config.yaml"
        cfg = yaml.safe_load(cfg_file.read_text()) if cfg_file.exists() else {}
        cfg.update(updates)
        cfg_file.write_text(yaml.dump(cfg, allow_unicode=True))

    # ── Document Management ──

    def add_document(self, name: str, file_path: str, embedding_client=None,
                     llm_client=None, strategy: str = "semantic",
                     max_chunk_size: int = 512, overlap: int = 128) -> dict:
        """Add a document to a knowledge base, chunk and index it."""
        kb_path = self.data_dir / name
        if not kb_path.exists():
            raise ValueError(f"Knowledge base '{name}' not found")

        src = Path(file_path)
        dest = kb_path / "docs" / src.name
        dest.write_bytes(src.read_bytes())

        converter = DocumentConverter()
        doc = converter.convert_file(file_path)

        # Save converted markdown for preview/re-chunk
        md_path = kb_path / "docs" / f"{src.name}.md"
        md_path.write_text(doc.markdown, encoding="utf-8")

        chunker = get_chunker(strategy, max_chunk_size=max_chunk_size, overlap=overlap)
        new_chunks = chunker.chunk(doc.markdown, metadata=doc.metadata)

        chunks_file = kb_path / "chunks.json"
        existing = json.loads(chunks_file.read_text()) if chunks_file.exists() else []
        chunk_dicts = [
            {"chunk_id": c.chunk_id, "content": c.content, "source": c.source,
             "heading_path": c.heading_path, "metadata": c.metadata}
            for c in new_chunks
        ]
        # Remove old chunks from the same document before appending (avoids duplicates on re-upload)
        existing = [c for c in existing if c.get("source") != src.name]
        existing_chunks_before = list(existing)
        existing.extend(chunk_dicts)
        chunks_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

        # Update documents.json
        self._update_documents_json(kb_path, {
            "filename": src.name,
            "size_bytes": src.stat().st_size,
            "chunk_count": len(new_chunks),
            "upload_time": datetime.now(timezone.utc).isoformat(),
            "chunk_strategy": strategy,
            "chunk_params": {"max_chunk_size": max_chunk_size, "overlap": overlap},
        })

        result = {"file": src.name, "chunks_added": len(new_chunks), "total_chunks": len(existing)}

        # Knowledge quality analysis (contradiction / duplicate detection)
        if existing_chunks_before and embedding_client and llm_client:
            try:
                from kb_studio.knowledge_analyzer import KnowledgeAnalyzer
                analyzer = KnowledgeAnalyzer()
                findings = analyzer.analyze_new_chunks(
                    chunk_dicts, existing_chunks_before, embedding_client, llm_client,
                )
                if findings:
                    self._save_findings(kb_path, findings)
                    result["findings_count"] = len(findings)
                    result["findings_summary"] = {
                        "contradictions": sum(1 for f in findings if f["type"] == "contradiction"),
                        "duplicates": sum(1 for f in findings if f["type"] == "duplicate"),
                        "updates": sum(1 for f in findings if f["type"] == "update"),
                    }
            except Exception as e:
                result["analysis_error"] = str(e)

        return result

    def list_documents(self, name: str) -> list[dict]:
        """List all documents in a KB with metadata."""
        kb_path = self.data_dir / name
        docs_json = kb_path / "documents.json"

        if docs_json.exists():
            return json.loads(docs_json.read_text())

        # Backward compat: derive from docs/ and chunks.json
        return self._derive_documents(kb_path)

    def get_document_content(self, name: str, filename: str) -> str:
        """Get the converted markdown content of a document."""
        kb_path = self.data_dir / name
        md_path = kb_path / "docs" / f"{filename}.md"
        if md_path.exists():
            return md_path.read_text(encoding="utf-8")
        raise ValueError(f"Document content not found for '{filename}'")

    def get_document_chunks(self, name: str, filename: str) -> list[dict]:
        """Get all chunks belonging to a specific document."""
        all_chunks = self.get_chunks(name)
        return [c for c in all_chunks if c.get("source") == filename]

    def delete_document(self, name: str, filename: str) -> dict:
        """Delete a document and its chunks from a KB."""
        kb_path = self.data_dir / name
        if not kb_path.exists():
            raise ValueError(f"Knowledge base '{name}' not found")

        # Remove files
        for suffix in ("", ".md"):
            f = kb_path / "docs" / f"{filename}{suffix}"
            if f.exists():
                f.unlink()

        # Remove chunks
        chunks_file = kb_path / "chunks.json"
        existing = json.loads(chunks_file.read_text()) if chunks_file.exists() else []
        new_chunks = [c for c in existing if c.get("source") != filename]
        removed = len(existing) - len(new_chunks)
        chunks_file.write_text(json.dumps(new_chunks, ensure_ascii=False, indent=2))

        # Update documents.json
        self._remove_from_documents_json(kb_path, filename)

        return {"filename": filename, "chunks_removed": removed}

    def rechunk_document(self, name: str, filename: str, strategy: str = "semantic",
                         max_chunk_size: int = 512, overlap: int = 128) -> dict:
        """Re-chunk a document with a new strategy."""
        kb_path = self.data_dir / name
        md_path = kb_path / "docs" / f"{filename}.md"
        if not md_path.exists():
            raise ValueError(f"Document content not found for '{filename}'. Re-upload the document.")

        markdown = md_path.read_text(encoding="utf-8")

        # Get original file metadata
        orig_file = kb_path / "docs" / filename
        size_bytes = orig_file.stat().st_size if orig_file.exists() else 0

        chunker = get_chunker(strategy, max_chunk_size=max_chunk_size, overlap=overlap)
        new_chunks = chunker.chunk(markdown, metadata={"filename": filename, "size_bytes": size_bytes})

        # Replace old chunks for this document
        chunks_file = kb_path / "chunks.json"
        existing = json.loads(chunks_file.read_text()) if chunks_file.exists() else []
        other_chunks = [c for c in existing if c.get("source") != filename]
        old_count = len(existing) - len(other_chunks)

        chunk_dicts = [
            {"chunk_id": c.chunk_id, "content": c.content, "source": c.source,
             "heading_path": c.heading_path, "metadata": c.metadata}
            for c in new_chunks
        ]
        other_chunks.extend(chunk_dicts)
        chunks_file.write_text(json.dumps(other_chunks, ensure_ascii=False, indent=2))

        # Update documents.json
        self._update_documents_json(kb_path, {
            "filename": filename,
            "size_bytes": size_bytes,
            "chunk_count": len(new_chunks),
            "upload_time": datetime.now(timezone.utc).isoformat(),
            "chunk_strategy": strategy,
            "chunk_params": {"max_chunk_size": max_chunk_size, "overlap": overlap},
        })

        return {"filename": filename, "old_chunk_count": old_count, "new_chunk_count": len(new_chunks)}

    # ── Internal helpers ──

    def _update_documents_json(self, kb_path: Path, doc_info: dict):
        """Add or update a document entry in documents.json."""
        docs_json = kb_path / "documents.json"
        docs = json.loads(docs_json.read_text()) if docs_json.exists() else []
        # Replace existing entry for same filename, or append
        docs = [d for d in docs if d.get("filename") != doc_info["filename"]]
        docs.append(doc_info)
        docs_json.write_text(json.dumps(docs, ensure_ascii=False, indent=2))

    def _remove_from_documents_json(self, kb_path: Path, filename: str):
        """Remove a document entry from documents.json."""
        docs_json = kb_path / "documents.json"
        if not docs_json.exists():
            return
        docs = json.loads(docs_json.read_text())
        docs = [d for d in docs if d.get("filename") != filename]
        docs_json.write_text(json.dumps(docs, ensure_ascii=False, indent=2))

    def _derive_documents(self, kb_path: Path) -> list[dict]:
        """Derive document list from docs/ dir and chunks.json (backward compat)."""
        docs_dir = kb_path / "docs"
        if not docs_dir.exists():
            return []

        all_chunks = self.get_chunks(kb_path.name) if (kb_path / "chunks.json").exists() else []
        chunk_counts: dict[str, int] = {}
        for c in all_chunks:
            src = c.get("source", "")
            chunk_counts[src] = chunk_counts.get(src, 0) + 1

        result = []
        for f in sorted(docs_dir.iterdir()):
            if f.is_file() and not f.name.endswith(".md"):
                result.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "chunk_count": chunk_counts.get(f.name, 0),
                    "upload_time": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
                    "chunk_strategy": "unknown",
                    "chunk_params": {},
                })
        return result

    # ── Conversation Management ──

    def list_conversations(self, name: str) -> list[dict]:
        """List all conversations for a KB. Migrates from chat_history.json if needed."""
        kb_path = self.data_dir / name
        conv_dir = kb_path / "conversations"
        conv_index = conv_dir / "conversations.json"

        # Migrate from legacy chat_history.json
        if not conv_dir.exists():
            self._migrate_history_to_conversations(kb_path)

        if not conv_index.exists():
            return []

        data = json.loads(conv_index.read_text())
        return data.get("conversations", [])

    def create_conversation(self, name: str, conv_name: str = "New Chat",
                            system_prompt: str | None = None) -> dict:
        """Create a new conversation."""
        kb_path = self.data_dir / name
        conv_dir = kb_path / "conversations"
        conv_dir.mkdir(exist_ok=True)

        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        conv = {
            "id": conv_id, "name": conv_name,
            "created_at": now, "updated_at": now,
            "message_count": 0, "preview": "",
            "system_prompt": system_prompt,
        }

        # Save conversation file
        (conv_dir / f"{conv_id}.json").write_text(json.dumps({
            "id": conv_id, "name": conv_name, "system_prompt": system_prompt, "messages": [],
        }, ensure_ascii=False, indent=2))

        # Update index
        self._update_conversation_index(kb_path, conv, set_active=True)
        return conv

    def get_conversation(self, name: str, conv_id: str) -> dict | None:
        """Get conversation metadata."""
        convs = self.list_conversations(name)
        for c in convs:
            if c["id"] == conv_id:
                return c
        return None

    def get_conversation_history(self, name: str, conv_id: str) -> list[dict]:
        """Get messages for a conversation."""
        kb_path = self.data_dir / name
        conv_file = kb_path / "conversations" / f"{conv_id}.json"
        if not conv_file.exists():
            return []
        data = json.loads(conv_file.read_text())
        return data.get("messages", [])

    def save_conversation_message(self, name: str, conv_id: str, message: dict):
        """Append a message to a conversation."""
        kb_path = self.data_dir / name
        conv_file = kb_path / "conversations" / f"{conv_id}.json"
        if not conv_file.exists():
            return

        data = json.loads(conv_file.read_text())
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        data["messages"].append(message)
        conv_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

        # Update index
        self._update_conversation_meta(kb_path, conv_id, len(data["messages"]),
                                        message.get("content", "")[:100])

    def delete_conversation(self, name: str, conv_id: str):
        """Delete a conversation."""
        kb_path = self.data_dir / name
        conv_file = kb_path / "conversations" / f"{conv_id}.json"
        if conv_file.exists():
            conv_file.unlink()

        # Update index
        index_file = kb_path / "conversations" / "conversations.json"
        if index_file.exists():
            data = json.loads(index_file.read_text())
            data["conversations"] = [c for c in data["conversations"] if c["id"] != conv_id]
            if data.get("active_conversation_id") == conv_id:
                data["active_conversation_id"] = data["conversations"][0]["id"] if data["conversations"] else None
            index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def rename_conversation(self, name: str, conv_id: str, new_name: str):
        """Rename a conversation."""
        kb_path = self.data_dir / name
        index_file = kb_path / "conversations" / "conversations.json"
        if not index_file.exists():
            return
        data = json.loads(index_file.read_text())
        for c in data["conversations"]:
            if c["id"] == conv_id:
                c["name"] = new_name
                break
        index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

        conv_file = kb_path / "conversations" / f"{conv_id}.json"
        if conv_file.exists():
            d = json.loads(conv_file.read_text())
            d["name"] = new_name
            conv_file.write_text(json.dumps(d, ensure_ascii=False, indent=2))

    def export_conversation(self, name: str, conv_id: str) -> str:
        """Export conversation as markdown."""
        conv = self.get_conversation(name, conv_id)
        messages = self.get_conversation_history(name, conv_id)
        if not conv:
            return ""

        lines = [f"# {conv['name']}", f"Created: {conv.get('created_at', '')[:10]}", ""]
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"## {role}")
            lines.append(msg.get("content", ""))
            if msg.get("sources"):
                lines.append(f"\n> Sources: {', '.join(msg['sources'])}")
            lines.append("\n---\n")
        return "\n".join(lines)

    def clear_conversation(self, name: str, conv_id: str):
        """Clear all messages in a conversation."""
        kb_path = self.data_dir / name
        conv_file = kb_path / "conversations" / f"{conv_id}.json"
        if conv_file.exists():
            data = json.loads(conv_file.read_text())
            data["messages"] = []
            conv_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        self._update_conversation_meta(kb_path, conv_id, 0, "")

    def set_active_conversation(self, name: str, conv_id: str):
        """Set the active conversation."""
        kb_path = self.data_dir / name
        index_file = kb_path / "conversations" / "conversations.json"
        if not index_file.exists():
            return
        data = json.loads(index_file.read_text())
        data["active_conversation_id"] = conv_id
        index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def get_active_conversation_id(self, name: str) -> str | None:
        """Get the active conversation ID."""
        kb_path = self.data_dir / name
        index_file = kb_path / "conversations" / "conversations.json"
        if not index_file.exists():
            return None
        data = json.loads(index_file.read_text())
        return data.get("active_conversation_id")

    # ── Conversation helpers ──

    def _migrate_history_to_conversations(self, kb_path: Path):
        """Migrate legacy chat_history.json to conversations/ directory."""
        history_file = kb_path / "chat_history.json"
        conv_dir = kb_path / "conversations"
        conv_dir.mkdir(exist_ok=True)

        messages = []
        if history_file.exists():
            try:
                messages = json.loads(history_file.read_text())
                history_file.rename(history_file.with_suffix(".json.bak"))
            except Exception:
                pass

        conv_id = "conv_default"
        now = datetime.now(timezone.utc).isoformat()

        (conv_dir / f"{conv_id}.json").write_text(json.dumps({
            "id": conv_id, "name": "Default", "system_prompt": None, "messages": messages,
        }, ensure_ascii=False, indent=2))

        index_data = {
            "active_conversation_id": conv_id,
            "conversations": [{
                "id": conv_id, "name": "Default",
                "created_at": now, "updated_at": now,
                "message_count": len(messages),
                "preview": messages[-1]["content"][:100] if messages else "",
                "system_prompt": None,
            }],
        }
        (conv_dir / "conversations.json").write_text(json.dumps(index_data, ensure_ascii=False, indent=2))

    def _update_conversation_index(self, kb_path: Path, conv: dict, set_active: bool = False):
        """Add a conversation to the index."""
        index_file = kb_path / "conversations" / "conversations.json"
        if index_file.exists():
            data = json.loads(index_file.read_text())
        else:
            data = {"active_conversation_id": None, "conversations": []}

        data["conversations"].append(conv)
        if set_active:
            data["active_conversation_id"] = conv["id"]
        index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _update_conversation_meta(self, kb_path: Path, conv_id: str, count: int, preview: str):
        """Update message count and preview in the index."""
        index_file = kb_path / "conversations" / "conversations.json"
        if not index_file.exists():
            return
        data = json.loads(index_file.read_text())
        for c in data["conversations"]:
            if c["id"] == conv_id:
                c["message_count"] = count
                c["preview"] = preview
                c["updated_at"] = datetime.now(timezone.utc).isoformat()
                break
        index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # ── Memory Management ──

    def get_memory(self, name: str) -> dict:
        """Get the memory for a KB."""
        kb_path = self.data_dir / name
        memory_file = kb_path / "memory.json"
        if memory_file.exists():
            return json.loads(memory_file.read_text())
        return {"entries": [], "summary": ""}

    def add_memory_entry(self, name: str, content: str, category: str = "general",
                         source_conversation: str | None = None, importance: float = 0.5) -> dict:
        """Add a memory entry."""
        kb_path = self.data_dir / name
        memory = self.get_memory(name)
        entry_id = f"mem_{uuid.uuid4().hex[:12]}"
        entry = {
            "id": entry_id, "content": content, "category": category,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_conversation": source_conversation, "importance": importance,
        }
        memory["entries"].append(entry)
        (kb_path / "memory.json").write_text(json.dumps(memory, ensure_ascii=False, indent=2))
        return entry

    def delete_memory_entry(self, name: str, entry_id: str):
        """Delete a memory entry."""
        kb_path = self.data_dir / name
        memory = self.get_memory(name)
        memory["entries"] = [e for e in memory["entries"] if e["id"] != entry_id]
        (kb_path / "memory.json").write_text(json.dumps(memory, ensure_ascii=False, indent=2))

    def update_memory_summary(self, name: str, summary: str):
        """Update the memory summary."""
        kb_path = self.data_dir / name
        memory = self.get_memory(name)
        memory["summary"] = summary
        (kb_path / "memory.json").write_text(json.dumps(memory, ensure_ascii=False, indent=2))

    def get_memory_context(self, name: str) -> str:
        """Build memory context string for injection into prompts."""
        memory = self.get_memory(name)
        parts = []
        if memory.get("summary"):
            parts.append(f"摘要：{memory['summary']}")
        for entry in memory.get("entries", []):
            parts.append(f"- [{entry['category']}] {entry['content']}")
        return "\n".join(parts) if parts else ""

    # ── Knowledge Findings (contradiction / duplicate detection) ──

    def _save_findings(self, kb_path: Path, findings: list[dict]):
        """Append findings to findings.json."""
        findings_file = kb_path / "findings.json"
        existing = []
        if findings_file.exists():
            existing = json.loads(findings_file.read_text())
        existing.extend(findings)
        findings_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    def get_findings(self, name: str, type_filter: str | None = None,
                     status_filter: str | None = None) -> list[dict]:
        """Get findings for a KB, optionally filtered."""
        kb_path = self.data_dir / name
        findings_file = kb_path / "findings.json"
        if not findings_file.exists():
            return []
        findings = json.loads(findings_file.read_text())
        if type_filter:
            findings = [f for f in findings if f.get("type") == type_filter]
        if status_filter:
            findings = [f for f in findings if f.get("status") == status_filter]
        return findings

    def update_finding_status(self, name: str, finding_id: str, status: str):
        """Update a finding's status (resolved / dismissed)."""
        kb_path = self.data_dir / name
        findings_file = kb_path / "findings.json"
        if not findings_file.exists():
            raise ValueError(f"Finding '{finding_id}' not found")
        findings = json.loads(findings_file.read_text())
        for f in findings:
            if f["id"] == finding_id:
                f["status"] = status
                findings_file.write_text(json.dumps(findings, ensure_ascii=False, indent=2))
                return
        raise ValueError(f"Finding '{finding_id}' not found")

    def get_findings_summary(self, name: str) -> dict:
        """Get a summary of findings by type and status."""
        findings = self.get_findings(name)
        summary = {"total": len(findings), "by_type": {}, "by_status": {}}
        for f in findings:
            t = f.get("type", "unknown")
            s = f.get("status", "unknown")
            summary["by_type"][t] = summary["by_type"].get(t, 0) + 1
            summary["by_status"][s] = summary["by_status"].get(s, 0) + 1
        return summary

    # ── Pipeline Config ──

    def get_pipeline(self, name: str) -> dict:
        """Get pipeline config for a KB."""
        cfg = self.get_config(name)
        return cfg.get("pipeline", {"enabled": False, "steps": self._default_pipeline_steps(name)})

    def update_pipeline(self, name: str, pipeline: dict):
        """Update pipeline config."""
        self.update_config(name, {"pipeline": pipeline})

    @staticmethod
    def _default_pipeline_steps(kb_name: str) -> list[dict]:
        return [
            {"name": "retriever", "role_prompt": "你是文档检索专家，负责从知识库中找到最相关的内容。",
             "kb_names": [kb_name], "top_k": 5, "enabled": True},
            {"name": "generator", "role_prompt": "你是回答生成专家，基于检索结果生成准确、有条理的回答。回答要引用具体来源。",
             "kb_names": [], "top_k": 5, "enabled": True},
        ]
