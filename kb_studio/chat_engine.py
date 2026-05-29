"""Chat engine — retrieval + LLM + conversation memory."""

from __future__ import annotations

import json

from kb_studio.core.llm.client import LLMClient
from kb_studio.core.retrieval.hybrid_search import HybridRetriever
from kb_studio.core.vector_store.memory_store import MemoryVectorStore


class ChatEngine:
    """RAG chat engine for a specific knowledge base."""

    def __init__(self, llm_client: LLMClient, embedding_client, chunks: list[dict],
                 system_prompt: str = "", retrieval_config: dict | None = None):
        self.llm = llm_client
        self.system_prompt = system_prompt or "根据知识库中的文档回答用户问题。"
        self.history: list[dict] = []
        self.retrieval_config = retrieval_config or {}

        # Build retrieval index with configurable params
        self.store = MemoryVectorStore()
        self.retriever = HybridRetriever(
            vector_store=self.store,
            embed_fn=embedding_client.embed,
            top_k=self.retrieval_config.get("top_k", 5),
            vector_weight=self.retrieval_config.get("vector_weight", 0.7),
            bm25_weight=self.retrieval_config.get("bm25_weight", 0.3),
            rerank=self.retrieval_config.get("strategy", "") == "hybrid_rerank",
        )

        if chunks:
            embeddings = embedding_client.embed_batch([c["content"] for c in chunks])
            self.store.insert_chunks(chunks, embeddings)
            self.retriever.build_bm25_index(chunks)

    def chat(self, question: str, history_override: list[dict] | None = None,
             memory_context: str = "") -> dict:
        """Ask a question and get an answer with sources."""
        strategy = self.retrieval_config.get("strategy", "hybrid")
        result = self.retriever.retrieve(question, strategy=strategy)

        contexts = [c.content for c in result.chunks]
        sources = list({c.source for c in result.chunks})
        context_block = "\n\n---\n\n".join(contexts) if contexts else ""

        user_msg = f"参考文档：\n{context_block}\n\n问题：{question}" if context_block else question

        # Inject memory into system prompt
        system = self.system_prompt
        if memory_context:
            system = f"{system}\n\n知识库记忆：\n{memory_context}"

        history = history_override if history_override is not None else self.history
        messages = [{"role": "system", "content": system}]
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_msg})

        answer = self.llm.chat_text(messages=messages)

        # Only save to internal history if no override (legacy mode)
        if history_override is None:
            self.history.append({"role": "user", "content": question})
            self.history.append({"role": "assistant", "content": answer})

        return {
            "answer": answer,
            "sources": sources,
            "chunks_used": len(contexts),
            "latency": round(result.latency, 3),
            "retrieval_results": [
                {
                    "chunk_id": c.chunk_id,
                    "content": c.content,
                    "score": round(c.score, 4),
                    "source": c.source,
                    "heading_path": c.heading_path,
                }
                for c in result.chunks
            ],
        }

    def search(self, query: str, top_k: int | None = None,
               strategy: str | None = None,
               vector_weight: float | None = None,
               bm25_weight: float | None = None) -> dict:
        """Standalone search without LLM call."""
        s = strategy or self.retrieval_config.get("strategy", "hybrid")

        # Temporarily override retriever params if specified
        orig_top_k = self.retriever.top_k
        orig_vw = self.retriever.vector_weight
        orig_bw = self.retriever.bm25_weight
        try:
            if top_k is not None:
                self.retriever.top_k = top_k
            if vector_weight is not None:
                self.retriever.vector_weight = vector_weight
            if bm25_weight is not None:
                self.retriever.bm25_weight = bm25_weight

            result = self.retriever.retrieve(query, strategy=s)
        finally:
            # Always restore, even if retrieve() throws
            self.retriever.top_k = orig_top_k
            self.retriever.vector_weight = orig_vw
            self.retriever.bm25_weight = orig_bw

        return {
            "query": query,
            "strategy": s,
            "latency": round(result.latency, 3),
            "total_chunks": self.store.get_collection_stats().get("row_count", 0),
            "results": [
                {
                    "chunk_id": c.chunk_id,
                    "content": c.content,
                    "score": round(c.score, 4),
                    "source": c.source,
                    "heading_path": c.heading_path,
                }
                for c in result.chunks
            ],
        }

    def clear_history(self):
        """Clear in-memory history. Conversation persistence is handled by KBManager."""
        self.history.clear()

    def extract_memory(self, question: str, answer: str) -> list[dict]:
        """Use LLM to extract key information from a Q&A pair for memory."""
        try:
            messages = [
                {"role": "system", "content": (
                    "从以下对话中提取值得长期记住的关键信息。包括：用户偏好、重要结论、领域知识、关键数据点。"
                    "输出 JSON 数组，每项格式：{\"content\": \"...\", \"category\": \"user_preference|conclusion|domain_knowledge|data_point\", \"importance\": 0.0-1.0}。"
                    "如果没有值得记住的信息，输出空数组 []。只输出 JSON，不要其他文字。"
                )},
                {"role": "user", "content": f"用户问：{question}\n助手答：{answer}"},
            ]
            raw = self.llm.chat_text(messages=messages, max_tokens=500, temperature=0.3)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            items = json.loads(raw)
            if isinstance(items, list):
                return [i for i in items if isinstance(i, dict) and "content" in i]
        except Exception:
            pass
        return []

    def extract_interests(self, question: str) -> dict:
        """Extract user interests and query intent from a question.
        Returns: {"topics": [...], "intent": "...", "complexity": "..."}
        """
        try:
            messages = [
                {"role": "system", "content": (
                    "分析用户的问题，提取：\n"
                    "1. topics: 用户关注的话题标签（2-5个，简短中文，如\"数据合规\"\"产品定价\"）\n"
                    "2. intent: 查询意图（factual|analytical|creative|procedural）\n"
                    "3. complexity: 问题复杂度（simple|moderate|complex）\n"
                    "输出 JSON: {\"topics\": [...], \"intent\": \"...\", \"complexity\": \"...\"}。只输出 JSON。"
                )},
                {"role": "user", "content": question},
            ]
            raw = self.llm.chat_text(messages=messages, max_tokens=200, temperature=0.1)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception:
            return {"topics": [], "intent": "unknown", "complexity": "unknown"}
