"""Vector store abstractions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchResult:
    chunk_id: str
    content: str
    score: float
    source: str
    heading_path: list[str]
    metadata: dict
