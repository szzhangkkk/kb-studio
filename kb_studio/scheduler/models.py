"""Data models for the scheduled task system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    SOURCE_MONITOR = "source_monitor"
    KB_ANALYZE = "kb_analyze"
    DIGEST = "digest"
    MEMORY_SYNC = "memory_sync"
    SUGGESTIONS = "suggestions"
    CUSTOM = "custom"


class TaskStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class Interval(str, Enum):
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    TWELVE_HOURS = "12h"
    DAILY = "1d"
    WEEKLY = "1w"


INTERVAL_SECONDS = {
    Interval.FIVE_MINUTES: 300,
    Interval.FIFTEEN_MINUTES: 900,
    Interval.THIRTY_MINUTES: 1800,
    Interval.ONE_HOUR: 3600,
    Interval.SIX_HOURS: 21600,
    Interval.TWELVE_HOURS: 43200,
    Interval.DAILY: 86400,
    Interval.WEEKLY: 604800,
}


@dataclass
class TaskRun:
    run_id: str
    started_at: str
    finished_at: str | None = None
    status: str = RunStatus.SUCCESS.value
    result_summary: str = ""
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScheduledTask:
    task_id: str
    name: str
    task_type: str
    interval: str
    config: dict[str, Any] = field(default_factory=dict)
    status: str = TaskStatus.ACTIVE.value
    enabled: bool = True
    created_at: str = ""
    last_run_at: str | None = None
    next_run_at: str | None = None
    run_count: int = 0
    last_result: str | None = None
    description: str = ""
    runs: list[TaskRun] = field(default_factory=list)

    @staticmethod
    def create(
        name: str,
        task_type: TaskType,
        interval: Interval,
        config: dict[str, Any] | None = None,
        description: str = "",
    ) -> ScheduledTask:
        now = datetime.utcnow().isoformat() + "Z"
        return ScheduledTask(
            task_id=str(uuid.uuid4())[:8],
            name=name,
            task_type=task_type.value,
            interval=interval.value,
            config=config or {},
            description=description,
            created_at=now,
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        # Only include last 10 runs in API response
        d["runs"] = [r.to_dict() for r in self.runs[-10:]]
        return d

    def to_summary(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type,
            "interval": self.interval,
            "status": self.status,
            "enabled": self.enabled,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "run_count": self.run_count,
            "last_result": self.last_result,
            "description": self.description,
        }
