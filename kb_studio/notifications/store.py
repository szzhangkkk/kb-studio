"""Persistent notification store."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Notification:
    id: str
    title: str
    body: str
    level: str  # "info", "warning", "error", "success"
    source: str  # "scheduler", "source_monitor", "analyzer", "user"
    details: dict[str, Any]
    read: bool = False
    created_at: str = ""
    task_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class NotificationStore:
    """File-backed notification store."""

    def __init__(self, storage_dir: str = "./data"):
        self._file = Path(storage_dir) / "notifications.json"
        self._notifications: list[Notification] = []
        self._load()

    def add(
        self,
        title: str,
        body: str,
        level: str = "info",
        source: str = "system",
        details: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> Notification:
        n = Notification(
            id=str(uuid.uuid4())[:8],
            title=title,
            body=body,
            level=level,
            source=source,
            details=details or {},
            created_at=datetime.utcnow().isoformat() + "Z",
            task_id=task_id,
        )
        self._notifications.insert(0, n)
        # Keep max 500 notifications
        if len(self._notifications) > 500:
            self._notifications = self._notifications[:500]
        self._save()
        return n

    def list_all(self, limit: int = 50, unread_only: bool = False) -> list[Notification]:
        items = self._notifications
        if unread_only:
            items = [n for n in items if not n.read]
        return items[:limit]

    def get(self, notification_id: str) -> Notification | None:
        for n in self._notifications:
            if n.id == notification_id:
                return n
        return None

    def mark_read(self, notification_id: str) -> bool:
        n = self.get(notification_id)
        if n:
            n.read = True
            self._save()
            return True
        return False

    def mark_all_read(self) -> int:
        count = 0
        for n in self._notifications:
            if not n.read:
                n.read = True
                count += 1
        if count:
            self._save()
        return count

    def delete(self, notification_id: str) -> bool:
        before = len(self._notifications)
        self._notifications = [n for n in self._notifications if n.id != notification_id]
        if len(self._notifications) < before:
            self._save()
            return True
        return False

    def clear_all(self) -> int:
        count = len(self._notifications)
        self._notifications = []
        self._save()
        return count

    def unread_count(self) -> int:
        return sum(1 for n in self._notifications if not n.read)

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = [n.to_dict() for n in self._notifications]
        self._file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _load(self):
        if not self._file.exists():
            return
        try:
            data = json.loads(self._file.read_text())
            self._notifications = [Notification(**d) for d in data]
        except Exception:
            self._notifications = []
