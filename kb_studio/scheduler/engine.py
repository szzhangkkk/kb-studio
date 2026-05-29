"""Asyncio-based task scheduler engine.

Runs as a background asyncio task. No external dependencies.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Awaitable

from .models import (
    ScheduledTask,
    TaskRun,
    TaskType,
    TaskStatus,
    RunStatus,
    Interval,
    INTERVAL_SECONDS,
)

logger = logging.getLogger("kb-studio.scheduler")

TaskHandler = Callable[[ScheduledTask, dict[str, Any]], Awaitable[dict[str, Any]]]


class TaskScheduler:
    """Lightweight asyncio task scheduler with disk persistence."""

    def __init__(self, storage_dir: str = "./data/scheduler"):
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._tasks_file = self._storage_dir / "tasks.json"
        self._tasks: dict[str, ScheduledTask] = {}
        self._handlers: dict[str, TaskHandler] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._notification_callback: Callable[[str, str, str, dict], Awaitable[None]] | None = None
        self._load()

    def register_handler(self, task_type: TaskType, handler: TaskHandler):
        """Register a handler function for a task type."""
        self._handlers[task_type.value] = handler

    def set_notification_callback(self, cb: Callable[[str, str, str, dict], Awaitable[None]]):
        """Set callback for sending notifications: (title, body, level, details)"""
        self._notification_callback = cb

    # ── Task CRUD ──

    def create_task(
        self,
        name: str,
        task_type: TaskType,
        interval: Interval,
        config: dict[str, Any] | None = None,
        description: str = "",
    ) -> ScheduledTask:
        task = ScheduledTask.create(name, task_type, interval, config, description)
        task.next_run_at = self._calc_next_run(interval)
        self._tasks[task.task_id] = task
        self._save()
        logger.info(f"Created task {task.task_id}: {task.name} ({task.task_type}, {task.interval})")
        return task

    def get_task(self, task_id: str) -> ScheduledTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, task_type: str | None = None) -> list[ScheduledTask]:
        tasks = list(self._tasks.values())
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    def update_task(self, task_id: str, **kwargs) -> ScheduledTask | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        for key in ("name", "description", "config", "enabled", "interval"):
            if key in kwargs:
                setattr(task, key, kwargs[key])
        if "interval" in kwargs:
            task.next_run_at = self._calc_next_run(Interval(kwargs["interval"]))
        if "enabled" in kwargs:
            task.status = TaskStatus.ACTIVE.value if kwargs["enabled"] else TaskStatus.PAUSED.value
        self._save()
        return task

    def delete_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save()
            return True
        return False

    def pause_task(self, task_id: str) -> ScheduledTask | None:
        return self.update_task(task_id, enabled=False)

    def resume_task(self, task_id: str) -> ScheduledTask | None:
        return self.update_task(task_id, enabled=True)

    # ── Scheduler lifecycle ──

    async def start(self):
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Scheduler started with {len(self._tasks)} tasks")

    async def stop(self):
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler stopped")

    async def run_task_now(self, task_id: str) -> TaskRun | None:
        """Manually trigger a task immediately."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return await self._execute(task)

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        active = sum(1 for t in self._tasks.values() if t.enabled)
        return {
            "running": self._running,
            "total_tasks": len(self._tasks),
            "active_tasks": active,
            "paused_tasks": len(self._tasks) - active,
            "registered_handlers": list(self._handlers.keys()),
        }

    # ── Internal loop ──

    async def _loop(self):
        """Main scheduler loop - checks every 30 seconds."""
        while self._running:
            try:
                now = datetime.utcnow()
                for task in list(self._tasks.values()):
                    if not task.enabled:
                        continue
                    if task.status == TaskStatus.RUNNING.value:
                        continue
                    if task.next_run_at and self._should_run(task, now):
                        await self._execute(task)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            await asyncio.sleep(30)

    def _should_run(self, task: ScheduledTask, now: datetime) -> bool:
        if not task.next_run_at:
            return True
        try:
            next_run = datetime.fromisoformat(task.next_run_at.replace("Z", "+00:00")).replace(tzinfo=None)
            return now >= next_run
        except (ValueError, TypeError):
            return True

    async def _execute(self, task: ScheduledTask) -> TaskRun:
        """Execute a task and record the result."""
        handler = self._handlers.get(task.task_type)
        now_iso = datetime.utcnow().isoformat() + "Z"

        run = TaskRun(run_id=f"{task.task_id}-{task.run_count + 1}", started_at=now_iso)
        task.status = TaskStatus.RUNNING.value
        self._save()

        try:
            if not handler:
                raise ValueError(f"No handler registered for task type: {task.task_type}")

            result = await asyncio.wait_for(handler(task, task.config), timeout=300)

            run.status = RunStatus.SUCCESS.value
            run.result_summary = result.get("summary", "")
            run.details = result.get("details", {})
            task.last_result = run.result_summary

            logger.info(f"Task {task.task_id} ({task.name}) completed: {run.result_summary}")

        except asyncio.TimeoutError:
            run.status = RunStatus.FAILED.value
            run.error = "Task timed out after 300 seconds"
            task.last_result = "timeout"
            logger.error(f"Task {task.task_id} ({task.name}) timed out")

        except Exception as e:
            run.status = RunStatus.FAILED.value
            run.error = str(e)
            run.details = {"traceback": traceback.format_exc()}
            task.last_result = f"error: {e}"
            logger.error(f"Task {task.task_id} ({task.name}) failed: {e}")

        finally:
            run.finished_at = datetime.utcnow().isoformat() + "Z"
            task.status = TaskStatus.ACTIVE.value if task.enabled else TaskStatus.PAUSED.value
            task.last_run_at = run.started_at
            task.run_count += 1
            task.runs.append(run)
            # Keep only last 50 runs
            if len(task.runs) > 50:
                task.runs = task.runs[-50:]
            task.next_run_at = self._calc_next_run(Interval(task.interval))
            self._save()

        # Send notification on failure or important results
        if run.status == RunStatus.FAILED.value:
            await self._notify(
                f"任务失败: {task.name}",
                run.error or "Unknown error",
                "error",
                {"task_id": task.task_id, "run_id": run.run_id},
            )
        elif run.result_summary and run.status == RunStatus.SUCCESS.value:
            await self._notify(
                f"任务完成: {task.name}",
                run.result_summary,
                "info",
                {"task_id": task.task_id, "run_id": run.run_id, "details": run.details},
            )

        return run

    async def _notify(self, title: str, body: str, level: str, details: dict):
        if self._notification_callback:
            try:
                await self._notification_callback(title, body, level, details)
            except Exception as e:
                logger.error(f"Notification failed: {e}")

    # ── Helpers ──

    @staticmethod
    def _calc_next_run(interval: Interval) -> str:
        seconds = INTERVAL_SECONDS.get(interval, 3600)
        next_run = datetime.utcnow() + timedelta(seconds=seconds)
        return next_run.isoformat() + "Z"

    # ── Persistence ──

    def _save(self):
        data = []
        for task in self._tasks.values():
            d = task.to_dict()
            # Convert runs to serializable format
            d["runs"] = [r.to_dict() for r in task.runs[-50:]]
            data.append(d)
        self._tasks_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _load(self):
        if not self._tasks_file.exists():
            return
        try:
            data = json.loads(self._tasks_file.read_text())
            for d in data:
                runs = [TaskRun(**r) for r in d.pop("runs", [])]
                task = ScheduledTask(**d)
                task.runs = runs
                self._tasks[task.task_id] = task
            logger.info(f"Loaded {len(self._tasks)} scheduled tasks")
        except Exception as e:
            logger.error(f"Failed to load scheduled tasks: {e}")
