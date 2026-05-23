"""Chat engine — retrieval + LLM + conversation memory."""

from __future__ import annotations

import json
from pathlib import Path

from src.core.llm.client import LLMClient
from src.core.llm.local_embedder import LocalEmbedder
from src.core.retrieval.hybrid_search import HybridRetriever
from src.core.vector_store.memory_store import MemoryVectorStore


class ChatEngine:
    """RAG chat engine for a specific knowledge base."""

    def __init__(self, llm_client: LLMClient, embedding_client, chunks: list[dict],
                 system_prompt: str = "", history_file: str | None = None):
        self.llm = llm_client
        self.system_prompt = system_prompt or "根据知识库中的文档回答用户问题。"
        self.history: list[dict] = []
        self.history_file = history_file

        # Build retrieval index
        self.store = MemoryVectorStore()
        self.retriever = HybridRetriever(vector_store=self.store, embed_fn=embedding_client.embed)

        if chunks:
            embeddings = embedding_client.embed_batch([c["content"] for c in chunks])
            self.store.insert_chunks(chunks, embeddings)
            self.retriever.build_bm25_index(chunks)

        # Load history
        if history_file and Path(history_file).exists():
            try:
                self.history = json.loads(Path(history_file).read_text())[-20:]
            except Exception:
                pass

    def chat(self, question: str) -> dict:
        """Ask a question and get an answer with sources."""
        result = self.retriever.retrieve(question, strategy="hybrid")
        contexts = [c.content for c in result.chunks]
        sources = list({c.source for c in result.chunks})
        context_block = "\n\n---\n\n".join(contexts) if contexts else ""

        user_msg = f"参考文档：\n{context_block}\n\n问题：{question}" if context_block else question

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history[-10:])
        messages.append({"role": "user", "content": user_msg})

        answer = self.llm.chat_text(messages=messages)

        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": answer})
        self._save_history()

        return {
            "answer": answer,
            "sources": sources,
            "chunks_used": len(contexts),
            "latency": round(result.latency, 3),
        }

    def clear_history(self):
        self.history.clear()
        if self.history_file and Path(self.history_file).exists():
            Path(self.history_file).unlink()

    def _save_history(self):
        if self.history_file:
            Path(self.history_file).write_text(
                json.dumps(self.history[-20:], ensure_ascii=False, indent=2)
            )
