"""Knowledge Base manager — create, list, delete, index knowledge bases."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.core.doc_processor.converter import DocumentConverter
from src.core.doc_processor.chunker import get_chunker, Chunk


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

    def list(self) -> list[KnowledgeBase]:
        kbs = []
        for d in sorted(self.data_dir.iterdir()):
            if d.is_dir() and (d / "config.yaml").exists():
                cfg = yaml.safe_load((d / "config.yaml").read_text())
                chunks_file = d / "chunks.json"
                chunk_count = len(json.loads(chunks_file.read_text())) if chunks_file.exists() else 0
                docs_dir = d / "docs"
                doc_count = len(list(docs_dir.iterdir())) if docs_dir.exists() else 0
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

        return KnowledgeBase(name=name, path=kb_path, description=description,
                            system_prompt=cfg["system_prompt"])

    def delete(self, name: str):
        import shutil
        kb_path = self.data_dir / name
        if not kb_path.exists():
            raise ValueError(f"Knowledge base '{name}' not found")
        shutil.rmtree(kb_path)

    def add_document(self, name: str, file_path: str, embedding_client=None) -> dict:
        """Add a document to a knowledge base, chunk and index it."""
        kb_path = self.data_dir / name
        if not kb_path.exists():
            raise ValueError(f"Knowledge base '{name}' not found")

        # Copy file to docs dir
        src = Path(file_path)
        dest = kb_path / "docs" / src.name
        dest.write_bytes(src.read_bytes())

        # Convert and chunk
        converter = DocumentConverter()
        doc = converter.convert_file(file_path)

        cfg = yaml.safe_load((kb_path / "config.yaml").read_text())
        chunker = get_chunker("semantic", max_chunk_size=512, overlap=128)
        new_chunks = chunker.chunk(doc.markdown, metadata=doc.metadata)

        # Append to existing chunks
        chunks_file = kb_path / "chunks.json"
        existing = json.loads(chunks_file.read_text()) if chunks_file.exists() else []
        chunk_dicts = [
            {"chunk_id": c.chunk_id, "content": c.content, "source": c.source,
             "heading_path": c.heading_path, "metadata": c.metadata}
            for c in new_chunks
        ]
        existing.extend(chunk_dicts)
        chunks_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

        return {"file": src.name, "chunks_added": len(new_chunks), "total_chunks": len(existing)}

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
