"""Cross-KB unified memory system.

Aggregates memories from all knowledge bases into a unified user profile.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class GlobalMemory:
    """Unified memory across all knowledge bases."""

    def __init__(self, data_dir: str = "./data"):
        self._data_dir = Path(data_dir)
        self._file = self._data_dir / "global_memory.json"
        self._data = self._load()

    def _load(self) -> dict:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text())
            except Exception:
                pass
        return {
            "user_profile": {
                "interests": [],
                "preferences": [],
                "frequent_topics": [],
            },
            "unified_entries": [],
            "last_sync": None,
        }

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(self._data, ensure_ascii=False, indent=2))

    # ── Sync from KB memories ──

    def sync_from_kbs(self, kb_manager) -> dict:
        """Sync all KB memories into the unified store."""
        existing_ids = {e.get("source_id") for e in self._data["unified_entries"]}
        new_count = 0

        for kb in kb_manager.list():
            memory = kb_manager.get_memory(kb.name)
            for entry in memory.get("entries", []):
                source_id = f"{kb.name}:{entry['id']}"
                if source_id in existing_ids:
                    continue
                self._data["unified_entries"].append({
                    "id": f"global_{uuid.uuid4().hex[:8]}",
                    "content": entry.get("content", ""),
                    "category": entry.get("category", "general"),
                    "importance": entry.get("importance", 0.5),
                    "source_kb": kb.name,
                    "source_id": source_id,
                    "created_at": entry.get("created_at", datetime.now(timezone.utc).isoformat()),
                })
                existing_ids.add(source_id)
                new_count += 1

        # Sort by importance descending
        self._data["unified_entries"].sort(key=lambda e: e.get("importance", 0), reverse=True)

        # Keep max 500 entries
        if len(self._data["unified_entries"]) > 500:
            self._data["unified_entries"] = self._data["unified_entries"][:500]

        self._data["last_sync"] = datetime.now(timezone.utc).isoformat()
        self._save()

        return {"new_entries": new_count, "total": len(self._data["unified_entries"])}

    # ── User profile ──

    def get_profile(self) -> dict:
        return self._data.get("user_profile", {})

    def update_profile(self, profile: dict):
        self._data["user_profile"] = {**self._data.get("user_profile", {}), **profile}
        self._save()

    def add_interest(self, interest: str):
        interests = self._data.setdefault("user_profile", {}).setdefault("interests", [])
        if interest not in interests:
            interests.append(interest)
            # Keep top 20
            self._data["user_profile"]["interests"] = interests[-20:]
            self._save()

    def add_preference(self, preference: str):
        prefs = self._data.setdefault("user_profile", {}).setdefault("preferences", [])
        if preference not in prefs:
            prefs.append(preference)
            self._data["user_profile"]["preferences"] = prefs[-20:]
            self._save()

    # ── Query ──

    def get_unified_entries(self, category: str | None = None, limit: int = 50) -> list[dict]:
        entries = self._data.get("unified_entries", [])
        if category:
            entries = [e for e in entries if e.get("category") == category]
        return entries[:limit]

    def get_context_string(self, limit: int = 20) -> str:
        """Build a context string from top memories for prompt injection."""
        entries = self._data.get("unified_entries", [])[:limit]
        profile = self._data.get("user_profile", {})

        parts = []
        interests = profile.get("interests", [])
        if interests:
            parts.append(f"用户关注领域: {', '.join(interests[-10:])}")

        prefs = profile.get("preferences", [])
        if prefs:
            parts.append(f"用户偏好: {', '.join(prefs[-5:])}")

        if entries:
            parts.append("相关记忆:")
            for e in entries:
                parts.append(f"  [{e.get('category', '?')}] {e['content']}")

        return "\n".join(parts)

    def get_summary(self) -> dict:
        """Get a summary of the global memory state."""
        entries = self._data.get("unified_entries", [])
        by_category = {}
        by_kb = {}
        for e in entries:
            cat = e.get("category", "general")
            by_category[cat] = by_category.get(cat, 0) + 1
            kb = e.get("source_kb", "?")
            by_kb[kb] = by_kb.get(kb, 0) + 1

        return {
            "total_entries": len(entries),
            "by_category": by_category,
            "by_kb": by_kb,
            "interests": self._data.get("user_profile", {}).get("interests", []),
            "preferences": self._data.get("user_profile", {}).get("preferences", []),
            "last_sync": self._data.get("last_sync"),
        }
