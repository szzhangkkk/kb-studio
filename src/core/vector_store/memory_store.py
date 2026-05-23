"""Lightweight in-memory vector store using numpy. No external dependencies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.core.doc_processor.chunker import Chunk
from src.core.vector_store.milvus_store import SearchResult


class MemoryVectorStore:
    """Simple in-memory vector store with cosine similarity search.

    Persists to disk as a JSON + numpy file. Suitable for development,
    testing, and small-to-medium datasets (up to ~100k chunks).
    """

    def __init__(self, collection_name: str = "agent_docs", dimension: int = 1024, persist_path: str = ""):
        self.collection_name = collection_name
        self.dimension = dimension
        self.persist_path = persist_path
        self._chunks: list[dict] = []
        self._embeddings: np.ndarray = np.empty((0, dimension), dtype=np.float32)
        if persist_path:
            self.load()

    def create_collection(self):
        self._chunks = []
        self._embeddings = np.empty((0, self.dimension), dtype=np.float32)

    def insert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]):
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        for chunk, emb in zip(chunks, embeddings):
            self._chunks.append({
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "source": chunk.source,
                "heading_path": chunk.heading_path,
                "metadata": chunk.metadata,
            })

        new_embs = np.array(embeddings, dtype=np.float32)
        if self._embeddings.size == 0:
            self._embeddings = new_embs
        else:
            self._embeddings = np.vstack([self._embeddings, new_embs])

        if self.persist_path:
            self._save()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        output_fields: list[str] | None = None,
    ) -> list[SearchResult]:
        if self._embeddings.size == 0:
            return []

        query = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return []

        # Cosine similarity
        norms = np.linalg.norm(self._embeddings, axis=1)
        norms[norms == 0] = 1e-10
        similarities = (self._embeddings @ query) / (norms * query_norm)

        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_indices:
            chunk = self._chunks[idx]
            results.append(SearchResult(
                chunk_id=chunk["chunk_id"],
                content=chunk["content"],
                score=float(similarities[idx]),
                source=chunk["source"],
                heading_path=chunk["heading_path"],
                metadata=chunk["metadata"],
            ))
        return results

    def delete_by_source(self, source: str):
        keep = [i for i, c in enumerate(self._chunks) if c["source"] != source]
        self._chunks = [self._chunks[i] for i in keep]
        self._embeddings = self._embeddings[keep] if keep else np.empty((0, self.dimension), dtype=np.float32)
        if self.persist_path:
            self._save()

    def get_collection_stats(self) -> dict:
        return {"row_count": len(self._chunks)}

    def _save(self):
        path = Path(self.persist_path)
        path.mkdir(parents=True, exist_ok=True)
        (path / "chunks.json").write_text(json.dumps(self._chunks, ensure_ascii=False))
        np.save(str(path / "embeddings.npy"), self._embeddings)

    def load(self):
        path = Path(self.persist_path)
        chunks_file = path / "chunks.json"
        embs_file = path / "embeddings.npy"
        if chunks_file.exists() and embs_file.exists():
            self._chunks = json.loads(chunks_file.read_text())
            self._embeddings = np.load(str(embs_file))
