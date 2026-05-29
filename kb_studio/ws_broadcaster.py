"""WebSocket broadcaster for real-time notifications."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("kb-studio.ws")


class WSBroadcaster:
    """Manages WebSocket connections and broadcasts messages."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        logger.info(f"WS client connected ({len(self._connections)} total)")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
        logger.info(f"WS client disconnected ({len(self._connections)} total)")

    async def broadcast(self, message: dict[str, Any]):
        """Send a message to all connected clients."""
        if not self._connections:
            return
        data = json.dumps(message, ensure_ascii=False)
        dead = []
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.remove(ws)

    async def notify(self, title: str, body: str, level: str = "info", source: str = "system"):
        """Broadcast a notification to all clients."""
        await self.broadcast({
            "type": "notification",
            "data": {"title": title, "body": body, "level": level, "source": source},
        })

    async def notify_update(self, update_type: str, data: dict[str, Any] | None = None):
        """Broadcast a state update (task completed, suggestion generated, etc.)."""
        await self.broadcast({
            "type": "update",
            "update_type": update_type,
            "data": data or {},
        })

    @property
    def connection_count(self) -> int:
        return len(self._connections)
