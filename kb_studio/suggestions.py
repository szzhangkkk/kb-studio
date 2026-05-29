"""Proactive suggestion engine.

Analyzes memory, staleness, and query patterns to generate actionable suggestions.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Suggestion:
    def __init__(self, suggestion_id: str, title: str, body: str, action: str,
                 category: str, priority: str = "normal", details: dict | None = None):
        self.id = suggestion_id
        self.title = title
        self.body = body
        self.action = action  # suggested action: "create_kb", "update_docs", "merge_kbs", etc.
        self.category = category  # "staleness", "interest", "pattern", "quality"
        self.priority = priority  # "low", "normal", "high"
        self.details = details or {}
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.dismissed = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "action": self.action,
            "category": self.category,
            "priority": self.priority,
            "details": self.details,
            "created_at": self.created_at,
            "dismissed": self.dismissed,
        }


class SuggestionEngine:
    """Generates proactive suggestions based on system state."""

    def __init__(self, data_dir: str = "./data"):
        self._data_dir = Path(data_dir)
        self._file = self._data_dir / "suggestions.json"
        self._suggestions: list[dict] = []
        self._load()

    def _load(self):
        if self._file.exists():
            try:
                self._suggestions = json.loads(self._file.read_text())
            except Exception:
                self._suggestions = []

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(self._suggestions, ensure_ascii=False, indent=2))

    def generate(self, kb_manager, global_memory, notification_store) -> list[dict]:
        """Run all suggestion generators and return new suggestions."""
        new_suggestions = []

        # 1. Staleness suggestions
        new_suggestions.extend(self._check_staleness(kb_manager))

        # 2. Interest-based suggestions
        new_suggestions.extend(self._check_interests(global_memory, kb_manager))

        # 3. Quality suggestions
        new_suggestions.extend(self._check_quality(kb_manager))

        # 4. Memory insights
        new_suggestions.extend(self._check_memory_insights(global_memory))

        # Filter out duplicates (same action + category)
        existing_keys = {(s["action"], s["category"]) for s in self._suggestions if not s.get("dismissed")}
        truly_new = []
        for s in new_suggestions:
            key = (s["action"], s["category"])
            if key not in existing_keys:
                self._suggestions.append(s)
                truly_new.append(s)
                existing_keys.add(key)

        if truly_new:
            self._save()
            # Send notification for high-priority suggestions
            for s in truly_new:
                if s.get("priority") == "high":
                    notification_store.add(
                        title=f"建议: {s['title']}",
                        body=s["body"],
                        level="warning",
                        source="suggestion_engine",
                        details=s.get("details", {}),
                    )

        return truly_new

    def list_suggestions(self, include_dismissed: bool = False) -> list[dict]:
        if include_dismissed:
            return self._suggestions
        return [s for s in self._suggestions if not s.get("dismissed")]

    def dismiss(self, suggestion_id: str) -> bool:
        for s in self._suggestions:
            if s["id"] == suggestion_id:
                s["dismissed"] = True
                self._save()
                return True
        return False

    def clear_dismissed(self) -> int:
        before = len(self._suggestions)
        self._suggestions = [s for s in self._suggestions if not s.get("dismissed")]
        self._save()
        return before - len(self._suggestions)

    # ── Generators ──

    def _check_staleness(self, kb_manager) -> list[dict]:
        """Suggest updates for stale documents."""
        from datetime import datetime as _dt
        now = _dt.utcnow()
        suggestions = []
        stale_docs = []

        for kb in kb_manager.list():
            docs = kb_manager.list_documents(kb.name)
            for doc in docs:
                upload_time = doc.get("upload_time", "")
                if upload_time:
                    try:
                        uploaded = _dt.fromisoformat(upload_time.replace("Z", "+00:00")).replace(tzinfo=None)
                        age_days = (now - uploaded).days
                        if age_days > 30:
                            stale_docs.append({"kb": kb.name, "doc": doc.get("filename", ""), "age_days": age_days})
                    except (ValueError, TypeError):
                        pass

        if stale_docs:
            suggestions.append(Suggestion(
                suggestion_id=str(uuid.uuid4())[:8],
                title=f"{len(stale_docs)} 篇文档已过期",
                body=f"有 {len(stale_docs)} 篇文档超过 30 天未更新，建议检查内容是否仍然准确",
                action="update_docs",
                category="staleness",
                priority="high" if len(stale_docs) > 3 else "normal",
                details={"stale_docs": stale_docs[:5]},
            ).to_dict())

        return suggestions

    def _check_interests(self, global_memory, kb_manager) -> list[dict]:
        """Suggest creating KBs for frequent interests that don't have a dedicated KB."""
        summary = global_memory.get_summary()
        interests = summary.get("interests", [])
        existing_kbs = {kb.name for kb in kb_manager.list()}

        if len(interests) >= 3:
            # Check if there's a suggestion for creating a KB from interests
            top_interests = interests[-5:]
            suggestions = []
            suggestions.append(Suggestion(
                suggestion_id=str(uuid.uuid4())[:8],
                title="发现你的关注领域",
                body=f"你最近频繁关注：{', '.join(top_interests)}。要不要创建一个专题知识库？",
                action="create_kb",
                category="interest",
                priority="normal",
                details={"interests": top_interests},
            ).to_dict())
            return suggestions

        return []

    def _check_quality(self, kb_manager) -> list[dict]:
        """Suggest quality checks for KBs that haven't been analyzed."""
        suggestions = []
        for kb in kb_manager.list():
            findings_file = self._data_dir / kb.name / "findings.json"
            if not findings_file.exists():
                suggestions.append(Suggestion(
                    suggestion_id=str(uuid.uuid4())[:8],
                    title=f"知识库 \"{kb.name}\" 未做质量检查",
                    body=f"建议运行质量检查，发现潜在的矛盾和重复内容",
                    action="analyze_kb",
                    category="quality",
                    priority="low",
                    details={"kb_name": kb.name},
                ).to_dict())
            else:
                try:
                    findings = json.loads(findings_file.read_text())
                    open_count = sum(1 for f in findings if f.get("status") == "open")
                    if open_count > 5:
                        suggestions.append(Suggestion(
                            suggestion_id=str(uuid.uuid4())[:8],
                            title=f"知识库 \"{kb.name}\" 有 {open_count} 个待处理问题",
                            body="建议查看并处理这些质量问题",
                            action="review_findings",
                            category="quality",
                            priority="normal",
                            details={"kb_name": kb.name, "open_count": open_count},
                        ).to_dict())
                except Exception:
                    pass

        return suggestions

    def _check_memory_insights(self, global_memory) -> list[dict]:
        """Generate suggestions based on memory patterns."""
        summary = global_memory.get_summary()
        suggestions = []

        # If many entries from one KB, suggest it's the primary KB
        by_kb = summary.get("by_kb", {})
        if len(by_kb) > 1:
            sorted_kbs = sorted(by_kb.items(), key=lambda x: x[1], reverse=True)
            top_kb, top_count = sorted_kbs[0]
            total = sum(by_kb.values())
            if top_count > total * 0.7 and total > 5:
                suggestions.append(Suggestion(
                    suggestion_id=str(uuid.uuid4())[:8],
                    title=f"\"{top_kb}\" 是你的主要知识库",
                    body=f"你 {top_count}/{total} 条记忆来自这个知识库。建议将其作为默认知识库。",
                    action="set_default_kb",
                    category="pattern",
                    priority="low",
                    details={"kb_name": top_kb, "memory_count": top_count},
                ).to_dict())

        return suggestions
