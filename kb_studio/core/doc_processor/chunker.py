"""Multiple chunking strategies for Markdown documents."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Chunk:
    content: str
    metadata: dict = field(default_factory=dict)
    chunk_id: str = ""
    source: str = ""
    heading_path: list[str] = field(default_factory=list)
    start_char: int = 0
    end_char: int = 0

    @property
    def token_estimate(self) -> int:
        return len(self.content) // 2


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, text: str, metadata: dict | None = None) -> list[Chunk]:
        ...


class HeadingChunker(BaseChunker):
    """Split by Markdown headings, preserving heading hierarchy."""

    def __init__(self, max_chunk_size: int = 2048, overlap: int = 0):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk(self, text: str, metadata: dict | None = None) -> list[Chunk]:
        metadata = metadata or {}
        source = metadata.get("filename", "unknown")
        lines = text.split("\n")

        sections: list[dict] = []
        current_heading: list[str] = []
        current_lines: list[str] = []
        current_level = 0

        for line in lines:
            heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
            if heading_match:
                if current_lines:
                    sections.append({
                        "heading_path": list(current_heading),
                        "content": "\n".join(current_lines).strip(),
                    })
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                current_heading = current_heading[: level - 1]
                current_heading.append(title)
                current_lines = [line]
                current_level = level
            else:
                current_lines.append(line)

        if current_lines:
            sections.append({
                "heading_path": list(current_heading),
                "content": "\n".join(current_lines).strip(),
            })

        chunks: list[Chunk] = []
        for i, sec in enumerate(sections):
            content = sec["content"]
            if not content:
                continue
            if len(content) > self.max_chunk_size:
                sub_chunks = self._split_large_chunk(content)
                for j, sub in enumerate(sub_chunks):
                    chunks.append(Chunk(
                        content=sub,
                        metadata=metadata,
                        chunk_id=f"{source}_sec{i}_{j}",
                        source=source,
                        heading_path=sec["heading_path"],
                    ))
            else:
                chunks.append(Chunk(
                    content=content,
                    metadata=metadata,
                    chunk_id=f"{source}_sec{i}",
                    source=source,
                    heading_path=sec["heading_path"],
                ))
        return chunks

    def _split_large_chunk(self, text: str) -> list[str]:
        paragraphs = re.split(r"\n\s*\n", text)
        result, current = [], ""
        for para in paragraphs:
            if len(current) + len(para) + 2 > self.max_chunk_size and current:
                result.append(current.strip())
                current = para
            else:
                current = current + "\n\n" + para if current else para
        if current.strip():
            result.append(current.strip())
        return result


class SlidingWindowChunker(BaseChunker):
    """Fixed-size sliding window chunking with optional overlap."""

    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, metadata: dict | None = None) -> list[Chunk]:
        metadata = metadata or {}
        source = metadata.get("filename", "unknown")
        chunks: list[Chunk] = []
        start = 0
        idx = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]

            if not chunk_text.strip():
                break

            chunks.append(Chunk(
                content=chunk_text.strip(),
                metadata=metadata,
                chunk_id=f"{source}_win{idx}",
                source=source,
                start_char=start,
                end_char=min(end, len(text)),
            ))
            start = end - self.overlap
            idx += 1

        return chunks


class SemanticChunker(BaseChunker):
    """Semantic-aware chunking that respects document structure.

    Combines heading awareness with paragraph-level splitting,
    merges small adjacent sections, and splits oversized ones.
    """

    def __init__(self, max_chunk_size: int = 1024, overlap: int = 128, min_chunk_size: int = 100):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size

    def chunk(self, text: str, metadata: dict | None = None) -> list[Chunk]:
        metadata = metadata or {}
        source = metadata.get("filename", "unknown")

        raw_sections = self._extract_sections(text)
        merged = self._merge_small_sections(raw_sections)
        final_chunks = self._split_oversized(merged)

        chunks: list[Chunk] = []
        for i, sec in enumerate(final_chunks):
            chunks.append(Chunk(
                content=sec["content"].strip(),
                metadata=metadata,
                chunk_id=f"{source}_sem{i}",
                source=source,
                heading_path=sec.get("heading_path", []),
            ))
        return chunks

    def _extract_sections(self, text: str) -> list[dict]:
        sections: list[dict] = []
        heading_stack: list[str] = []
        current_lines: list[str] = []

        for line in text.split("\n"):
            heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
            if heading_match:
                if current_lines:
                    sections.append({
                        "heading_path": list(heading_stack),
                        "content": "\n".join(current_lines),
                    })
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                heading_stack = heading_stack[: level - 1]
                heading_stack.append(title)
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            sections.append({
                "heading_path": list(heading_stack),
                "content": "\n".join(current_lines),
            })
        return sections

    def _merge_small_sections(self, sections: list[dict]) -> list[dict]:
        if not sections:
            return sections
        merged: list[dict] = []
        buffer = sections[0]

        for sec in sections[1:]:
            if len(buffer["content"]) < self.min_chunk_size:
                buffer = {
                    "heading_path": buffer["heading_path"],
                    "content": buffer["content"] + "\n\n" + sec["content"],
                }
            else:
                merged.append(buffer)
                buffer = sec
        merged.append(buffer)
        return merged

    def _split_oversized(self, sections: list[dict]) -> list[dict]:
        result: list[dict] = []
        for sec in sections:
            if len(sec["content"]) <= self.max_chunk_size:
                result.append(sec)
            else:
                paragraphs = re.split(r"\n\s*\n", sec["content"])
                current = ""
                for para in paragraphs:
                    if len(current) + len(para) + 2 > self.max_chunk_size and current:
                        result.append({
                            "heading_path": sec["heading_path"],
                            "content": current.strip(),
                        })
                        current = para
                    else:
                        current = current + "\n\n" + para if current else para
                if current.strip():
                    result.append({
                        "heading_path": sec["heading_path"],
                        "content": current.strip(),
                    })
        return result


CHUNKER_REGISTRY: dict[str, type[BaseChunker]] = {
    "heading": HeadingChunker,
    "sliding_window": SlidingWindowChunker,
    "semantic": SemanticChunker,
}


def get_chunker(strategy: str, **kwargs) -> BaseChunker:
    cls = CHUNKER_REGISTRY.get(strategy)
    if cls is None:
        raise ValueError(f"Unknown chunking strategy: {strategy}. Choose from {list(CHUNKER_REGISTRY)}")
    return cls(**kwargs)
