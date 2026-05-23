"""Hybrid retrieval: vector search + BM25 + reranking."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from src.core.vector_store.milvus_store import MilvusStore, SearchResult


@dataclass
class RetrievalResult:
    chunks: list[SearchResult]
    query: str
    strategy: str
    latency: float = 0.0


class BM25Index:
    """In-memory BM25 index over document chunks."""

    def __init__(self):
        self._docs: list[dict] = []  # {chunk_id, content, source, heading_path, metadata}
        self._bm25: BM25Okapi | None = None
        self._tokenized: list[list[str]] = []

    def build(self, chunks: list[dict]):
        self._docs = chunks
        self._tokenized = [list(jieba.cut(doc["content"])) for doc in self._docs]
        self._bm25 = BM25Okapi(self._tokenized)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        if self._bm25 is None or not self._docs:
            return []
        tokenized_query = list(jieba.cut(query))
        scores = self._bm25.get_scores(tokenized_query)

        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] <= 0:
                break
            doc = self._docs[idx]
            results.append(SearchResult(
                chunk_id=doc["chunk_id"],
                content=doc["content"],
                score=float(scores[idx]),
                source=doc["source"],
                heading_path=doc.get("heading_path", []),
                metadata=doc.get("metadata", {}),
            ))
        return results


class HybridRetriever:
    """Combines vector search, BM25, and optional reranking."""

    def __init__(
        self,
        vector_store,
        embed_fn,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        top_k: int = 5,
        rerank: bool = False,
        rerank_top_k: int = 5,
    ):
        self.vector_store = vector_store
        self.embed_fn = embed_fn
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.top_k = top_k
        self.rerank = rerank
        self.rerank_top_k = rerank_top_k
        self.bm25_index = BM25Index()

    def build_bm25_index(self, chunks: list[dict]):
        self.bm25_index.build(chunks)

    def retrieve(self, query: str, strategy: str = "hybrid") -> RetrievalResult:
        import time
        start = time.time()

        if strategy == "vector":
            results = self._vector_search(query)
        elif strategy == "bm25":
            results = self._bm25_search(query)
        elif strategy == "hybrid":
            results = self._hybrid_search(query)
        elif strategy == "hybrid_rerank":
            results = self._hybrid_rerank_search(query)
        else:
            raise ValueError(f"Unknown retrieval strategy: {strategy}")

        latency = time.time() - start
        return RetrievalResult(
            chunks=results,
            query=query,
            strategy=strategy,
            latency=latency,
        )

    def _vector_search(self, query: str) -> list[SearchResult]:
        query_emb = self.embed_fn(query)
        return self.vector_store.search(query_emb, top_k=self.top_k)

    def _bm25_search(self, query: str) -> list[SearchResult]:
        return self.bm25_index.search(query, top_k=self.top_k)

    def _hybrid_search(self, query: str) -> list[SearchResult]:
        k = max(self.top_k * 3, 20)
        query_emb = self.embed_fn(query)
        vector_results = self.vector_store.search(query_emb, top_k=k)
        bm25_results = self.bm25_index.search(query, top_k=k)
        return self._merge_results(vector_results, bm25_results)[: self.top_k]

    def _hybrid_rerank_search(self, query: str) -> list[SearchResult]:
        k = max(self.top_k * 4, 30)
        query_emb = self.embed_fn(query)
        vector_results = self.vector_store.search(query_emb, top_k=k)
        bm25_results = self.bm25_index.search(query, top_k=k)
        merged = self._merge_results(vector_results, bm25_results)
        return self._simple_rerank(query, merged)[: self.rerank_top_k]

    def _merge_results(
        self, vector_results: list[SearchResult], bm25_results: list[SearchResult]
    ) -> list[SearchResult]:
        vec_scores = {}
        for r in vector_results:
            vec_scores[r.chunk_id] = r.score
        bm25_scores = {}
        for r in bm25_results:
            bm25_scores[r.chunk_id] = r.score

        vec_max = max(vec_scores.values(), default=1.0) or 1.0
        bm25_max = max(bm25_scores.values(), default=1.0) or 1.0

        all_ids = set(vec_scores) | set(bm25_scores)
        content_map: dict[str, SearchResult] = {}
        for r in vector_results + bm25_results:
            if r.chunk_id not in content_map:
                content_map[r.chunk_id] = r

        scored = []
        for cid in all_ids:
            v = (vec_scores.get(cid, 0) / vec_max) * self.vector_weight
            b = (bm25_scores.get(cid, 0) / bm25_max) * self.bm25_weight
            scored.append((cid, v + b))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for cid, score in scored:
            r = content_map[cid]
            results.append(SearchResult(
                chunk_id=r.chunk_id,
                content=r.content,
                score=score,
                source=r.source,
                heading_path=r.heading_path,
                metadata=r.metadata,
            ))
        return results

    def _simple_rerank(self, query: str, candidates: list[SearchResult]) -> list[SearchResult]:
        """Simple keyword-overlap reranker (no external model dependency)."""
        query_tokens = set(jieba.cut(query))
        scored = []
        for r in candidates:
            doc_tokens = set(jieba.cut(r.content))
            overlap = len(query_tokens & doc_tokens)
            boosted_score = r.score + overlap * 0.05
            scored.append((r, boosted_score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored]
