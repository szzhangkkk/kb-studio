"""Source monitoring - watches URLs/RSS for changes and auto-updates knowledge bases."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("kb-studio.source_monitor")


@dataclass
class SourceWatch:
    watch_id: str
    url: str
    kb_name: str
    name: str
    watch_type: str  # "url", "rss"
    interval: str
    enabled: bool = True
    last_fetched_at: str | None = None
    last_content_hash: str | None = None
    last_change_at: str | None = None
    fetch_count: int = 0
    change_count: int = 0
    created_at: str = ""
    last_error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class SourceMonitor:
    """Manages URL/RSS source watches for knowledge bases."""

    def __init__(self, storage_dir: str = "./data"):
        self._storage_dir = Path(storage_dir)
        self._file = self._storage_dir / "source_watches.json"
        self._watches: dict[str, SourceWatch] = {}
        self._load()

    def add_watch(
        self,
        url: str,
        kb_name: str,
        name: str = "",
        watch_type: str = "url",
        interval: str = "1d",
    ) -> SourceWatch:
        import uuid
        watch_id = str(uuid.uuid4())[:8]
        if not name:
            name = url[:60]
        watch = SourceWatch(
            watch_id=watch_id,
            url=url,
            kb_name=kb_name,
            name=name,
            watch_type=watch_type,
            interval=interval,
            created_at=datetime.utcnow().isoformat() + "Z",
        )
        self._watches[watch_id] = watch
        self._save()
        logger.info(f"Added source watch {watch_id}: {url} -> {kb_name}")
        return watch

    def get_watch(self, watch_id: str) -> SourceWatch | None:
        return self._watches.get(watch_id)

    def list_watches(self, kb_name: str | None = None) -> list[SourceWatch]:
        watches = list(self._watches.values())
        if kb_name:
            watches = [w for w in watches if w.kb_name == kb_name]
        return sorted(watches, key=lambda w: w.created_at, reverse=True)

    def delete_watch(self, watch_id: str) -> bool:
        if watch_id in self._watches:
            del self._watches[watch_id]
            self._save()
            return True
        return False

    def toggle_watch(self, watch_id: str) -> SourceWatch | None:
        watch = self._watches.get(watch_id)
        if watch:
            watch.enabled = not watch.enabled
            self._save()
        return watch

    def update_watch_result(
        self,
        watch_id: str,
        content_hash: str,
        changed: bool,
        error: str | None = None,
    ):
        watch = self._watches.get(watch_id)
        if not watch:
            return
        now = datetime.utcnow().isoformat() + "Z"
        watch.last_fetched_at = now
        watch.fetch_count += 1
        if error:
            watch.last_error = error
        else:
            watch.last_error = None
            watch.last_content_hash = content_hash
            if changed:
                watch.last_change_at = now
                watch.change_count += 1
        self._save()

    async def check_url(self, url: str) -> tuple[str, str]:
        """Fetch URL and return (content_markdown, content_hash)."""
        import httpx
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.text
            content_hash = hashlib.md5(content.encode()).hexdigest()
            return content, content_hash

    async def check_and_update(
        self,
        watch_id: str,
        converters: Any,
        kb_manager: Any,
        notification_store: Any,
        embedding_client: Any = None,
        llm_client: Any = None,
        clear_engine_fn: Any = None,
    ) -> dict[str, Any]:
        """Check a source for changes. If changed, re-fetch and update KB.
        Follows the same pattern as server.py upload_url endpoint.
        """
        import uuid as _uuid
        from pathlib import Path as _Path
        from ..core.doc_processor.converter import DocumentConverter

        watch = self._watches.get(watch_id)
        if not watch or not watch.enabled:
            return {"status": "skipped", "reason": "watch not found or disabled"}

        try:
            _, content_hash = await self.check_url(watch.url)

            changed = watch.last_content_hash is None or content_hash != watch.last_content_hash

            if not changed:
                self.update_watch_result(watch_id, content_hash, changed=False)
                return {"status": "no_change", "hash": content_hash}

            # Content changed - fetch and convert
            converter = DocumentConverter()
            doc = converter.convert_url(watch.url)

            if not doc.markdown:
                self.update_watch_result(watch_id, content_hash, changed=False, error="Empty content")
                return {"status": "error", "reason": "empty content"}

            # Save to temp file and use add_document (same pattern as server.py)
            tmp = _Path("/tmp") / f"source_update_{_uuid.uuid4().hex[:8]}.md"
            tmp.write_text(doc.markdown, encoding="utf-8")
            try:
                result = kb_manager.add_document(
                    watch.kb_name, str(tmp),
                    embedding_client=embedding_client,
                    llm_client=llm_client,
                )
                # Clear engine cache so it gets recreated with new chunks
                if clear_engine_fn:
                    clear_engine_fn(watch.kb_name)

                chunk_count = result.get("chunk_count", 0)
            finally:
                tmp.unlink(missing_ok=True)

            self.update_watch_result(watch_id, content_hash, changed=True)

            # Notify
            notification_store.add(
                title=f"源更新: {watch.name}",
                body=f"检测到 {watch.url} 的内容变化，已自动更新知识库 {watch.kb_name}（{chunk_count} 个分块）",
                level="info",
                source="source_monitor",
                details={
                    "watch_id": watch_id,
                    "url": watch.url,
                    "kb_name": watch.kb_name,
                    "chunks": chunk_count,
                },
            )

            return {
                "status": "updated",
                "title": doc.metadata.get("title", watch.name),
                "chunks": chunk_count,
                "hash": content_hash,
            }

        except Exception as e:
            self.update_watch_result(watch_id, "", changed=False, error=str(e))
            logger.error(f"Source check failed for {watch.url}: {e}")
            return {"status": "error", "reason": str(e)}

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = [w.to_dict() for w in self._watches.values()]
        self._file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _load(self):
        if not self._file.exists():
            return
        try:
            data = json.loads(self._file.read_text())
            self._watches = {d["watch_id"]: SourceWatch(**d) for d in data}
        except Exception:
            self._watches = {}
