"""Knowledge quality analyzer — detects contradictions, duplicates, and updates across chunks."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from kb_studio.core.vector_store.memory_store import MemoryVectorStore

# Similarity threshold: chunks below this are considered unrelated
SIMILARITY_THRESHOLD = 0.75
# Max candidates per new chunk to send to LLM
MAX_CANDIDATES = 3


class KnowledgeAnalyzer:
    """Compare new document chunks against existing chunks to find issues."""

    def analyze_new_chunks(
        self,
        new_chunks: list[dict],
        existing_chunks: list[dict],
        embedding_client,
        llm_client,
    ) -> list[dict]:
        """Analyze new chunks against existing ones.

        Returns a list of finding dicts ready to be persisted.
        """
        if not new_chunks or not existing_chunks:
            return []

        # Step 1: Build a temporary vector store from existing chunks
        store = MemoryVectorStore()
        existing_embeddings = embedding_client.embed_batch(
            [c["content"] for c in existing_chunks],
        )
        store.insert_chunks(existing_chunks, existing_embeddings)

        # Step 2: Embed new chunks and find similar existing ones
        new_embeddings = embedding_client.embed_batch(
            [c["content"] for c in new_chunks],
        )

        candidate_pairs: list[tuple[dict, list[dict]]] = []
        for i, new_chunk in enumerate(new_chunks):
            results = store.search(new_embeddings[i], top_k=MAX_CANDIDATES * 2)
            # Filter by threshold, exclude self-references
            candidates = [
                r for r in results
                if r.score >= SIMILARITY_THRESHOLD
                and r.chunk_id != new_chunk["chunk_id"]
            ][:MAX_CANDIDATES]
            if candidates:
                candidate_pairs.append((new_chunk, candidates))

        if not candidate_pairs:
            return []

        # Step 3: LLM comparison for each (new_chunk, candidates) pair
        all_findings: list[dict] = []
        for new_chunk, candidates in candidate_pairs:
            findings = self._compare_with_llm(new_chunk, candidates, llm_client)
            all_findings.extend(findings)

        return all_findings

    def analyze_all_chunks(
        self,
        all_chunks: list[dict],
        embedding_client,
        llm_client,
    ) -> list[dict]:
        """Full scan: compare all chunks against each other.

        For use with the /analyze endpoint on existing KBs.
        """
        if len(all_chunks) < 2:
            return []

        store = MemoryVectorStore()
        embeddings = embedding_client.embed_batch([c["content"] for c in all_chunks])
        store.insert_chunks(all_chunks, embeddings)

        all_findings: list[dict] = []
        seen_pairs: set[tuple[str, str]] = set()

        for i, chunk in enumerate(all_chunks):
            results = store.search(embeddings[i], top_k=MAX_CANDIDATES + 1)
            candidates = [
                r for r in results
                if r.score >= SIMILARITY_THRESHOLD
                and r.chunk_id != chunk["chunk_id"]
            ][:MAX_CANDIDATES]
            if not candidates:
                continue

            # Deduplicate pairs (A,B) == (B,A)
            filtered = []
            for c in candidates:
                pair = tuple(sorted([chunk["chunk_id"], c.chunk_id]))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    filtered.append(c)

            if not filtered:
                continue

            # Convert SearchResult objects to dicts
            candidate_dicts = [
                {
                    "chunk_id": c.chunk_id,
                    "content": c.content,
                    "source": c.source,
                    "heading_path": c.heading_path,
                }
                for c in filtered
            ]
            findings = self._compare_with_llm(chunk, candidate_dicts, llm_client)
            all_findings.extend(findings)

        return all_findings

    def _compare_with_llm(
        self,
        new_chunk: dict,
        candidates: list,
        llm_client,
    ) -> list[dict]:
        """Send a new chunk + candidates to LLM for relationship classification."""
        # Build candidate text blocks
        candidate_blocks = []
        for i, c in enumerate(candidates):
            chunk_id = c.chunk_id if hasattr(c, "chunk_id") else c.get("chunk_id", "")
            content = c.content if hasattr(c, "content") else c.get("content", "")
            source = c.source if hasattr(c, "source") else c.get("source", "")
            candidate_blocks.append(
                f"[片段{i + 1}] (来源: {source}, ID: {chunk_id})\n{content}",
            )

        candidates_text = "\n\n".join(candidate_blocks)

        messages = [
            {"role": "system", "content": (
                "你是知识库质量检查专家。请比较新文档片段和已有文档片段的关系。\n"
                "判断标准：\n"
                "- contradiction: 包含互相矛盾的事实、数据或结论\n"
                "- duplicate: 内容高度重复，没有新增信息价值\n"
                "- update: 同一话题的新版本，信息有实质性更新\n"
                "- unrelated: 不相关或仅主题相近但无矛盾/重复\n\n"
                "输出 JSON 数组，每项格式：\n"
                '{"existing_chunk_id": "片段ID", "type": "contradiction|duplicate|update", "explanation": "简要说明"}\n'
                "只输出 unrelated 的不要包含。只输出 JSON，不要其他文字。"
            )},
            {"role": "user", "content": (
                f"新文档片段：\n{new_chunk['content']}\n\n"
                f"已有文档片段：\n{candidates_text}"
            )},
        ]

        try:
            raw = llm_client.chat_text(messages=messages, max_tokens=500, temperature=0.1)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            items = json.loads(raw)
        except Exception:
            return []

        if not isinstance(items, list):
            return []

        # Map candidate chunk_id -> full dict for fast lookup
        candidate_map = {}
        for c in candidates:
            cid = c.chunk_id if hasattr(c, "chunk_id") else c.get("chunk_id", "")
            candidate_map[cid] = {
                "chunk_id": cid,
                "content": (c.content if hasattr(c, "content") else c.get("content", ""))[:500],
                "source": c.source if hasattr(c, "source") else c.get("source", ""),
            }

        severity_map = {"contradiction": "high", "duplicate": "medium", "update": "low"}

        findings = []
        for item in items:
            etype = item.get("type", "")
            if etype not in ("contradiction", "duplicate", "update"):
                continue
            existing_id = item.get("existing_chunk_id", "")
            existing_info = candidate_map.get(existing_id, {"chunk_id": existing_id, "content": "", "source": ""})
            findings.append({
                "id": uuid.uuid4().hex[:12],
                "type": etype,
                "severity": severity_map.get(etype, "medium"),
                "new_chunk": {
                    "chunk_id": new_chunk["chunk_id"],
                    "content": new_chunk["content"][:500],
                    "source": new_chunk.get("source", ""),
                },
                "existing_chunk": existing_info,
                "explanation": item.get("explanation", ""),
                "status": "open",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        return findings
