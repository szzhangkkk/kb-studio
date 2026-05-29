"""Built-in task handlers for the scheduler."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from .models import ScheduledTask, TaskType
from .engine import TaskHandler

logger = logging.getLogger("kb-studio.scheduler.handlers")


def create_source_monitor_handler(source_monitor, kb_manager, notification_store,
                                  get_emb_fn=None, get_llm_fn=None, clear_engine_fn=None) -> TaskHandler:
    """Handler for source monitoring tasks - checks all enabled watches."""

    async def handler(task: ScheduledTask, config: dict[str, Any]) -> dict[str, Any]:
        watches = source_monitor.list_watches()
        enabled = [w for w in watches if w.enabled]

        if not enabled:
            return {"summary": "没有启用的源监控", "details": {"checked": 0}}

        updated = 0
        errors = 0
        no_change = 0

        for watch in enabled:
            result = await source_monitor.check_and_update(
                watch.watch_id, None, kb_manager, notification_store,
                embedding_client=get_emb_fn() if get_emb_fn else None,
                llm_client=get_llm_fn() if get_llm_fn else None,
                clear_engine_fn=clear_engine_fn,
            )
            status = result.get("status")
            if status == "updated":
                updated += 1
            elif status == "error":
                errors += 1
            else:
                no_change += 1

        summary = f"检查了 {len(enabled)} 个源: {updated} 个更新, {no_change} 个无变化"
        if errors:
            summary += f", {errors} 个错误"

        return {
            "summary": summary,
            "details": {
                "checked": len(enabled),
                "updated": updated,
                "no_change": no_change,
                "errors": errors,
            },
        }

    return handler


def create_kb_analyze_handler(kb_manager, get_emb_fn=None, get_llm_fn=None) -> TaskHandler:
    """Handler for scheduled knowledge base analysis.
    get_emb_fn/get_llm_fn: callables that return the server's singleton clients.
    """

    async def handler(task: ScheduledTask, config: dict[str, Any]) -> dict[str, Any]:
        from kb_studio.knowledge_analyzer import KnowledgeAnalyzer

        kb_name = config.get("kb_name")
        if kb_name:
            kb_names = [kb_name]
        else:
            kbs = kb_manager.list()
            kb_names = [kb.name for kb in kbs]

        if not kb_names:
            return {"summary": "没有知识库", "details": {"analyzed": 0}}

        emb = get_emb_fn() if get_emb_fn else None
        llm = get_llm_fn() if get_llm_fn else None

        total_findings = 0
        analyzed = 0

        for name in kb_names:
            try:
                chunks = kb_manager.get_chunks(name)
                if not chunks:
                    continue
                analyzer = KnowledgeAnalyzer()
                findings = analyzer.analyze_all_chunks(chunks, emb, llm)
                total_findings += len(findings)
                analyzed += 1
            except Exception as e:
                logger.error(f"Analysis failed for {name}: {e}")

        summary = f"分析了 {analyzed} 个知识库，发现 {total_findings} 个问题"
        return {
            "summary": summary,
            "details": {"analyzed": analyzed, "findings": total_findings},
        }

    return handler


def create_digest_handler(kb_manager, notification_store) -> TaskHandler:
    """Handler for generating knowledge digest notifications."""

    async def handler(task: ScheduledTask, config: dict[str, Any]) -> dict[str, Any]:
        kbs = kb_manager.list()

        if not kbs:
            return {"summary": "没有知识库", "details": {}}

        total_docs = sum(kb.doc_count for kb in kbs)
        total_chunks = sum(kb.chunk_count for kb in kbs)

        notification_store.add(
            title="知识库日报",
            body=f"共 {len(kbs)} 个知识库，{total_docs} 篇文档，{total_chunks} 个分块",
            level="info",
            source="scheduler",
            details={"kb_count": len(kbs), "doc_count": total_docs, "chunk_count": total_chunks},
        )

        return {
            "summary": f"已生成摘要: {len(kbs)} 个知识库，{total_docs} 篇文档",
            "details": {"kb_count": len(kbs), "doc_count": total_docs},
        }

    return handler


def create_memory_sync_handler(global_memory, kb_manager) -> TaskHandler:
    """Handler for syncing all KB memories into the global memory."""

    async def handler(task: ScheduledTask, config: dict[str, Any]) -> dict[str, Any]:
        result = global_memory.sync_from_kbs(kb_manager)
        summary = global_memory.get_summary()

        return {
            "summary": f"同步了 {result['new_entries']} 条新记忆，共 {result['total']} 条",
            "details": {
                "new_entries": result["new_entries"],
                "total": result["total"],
                "interests": len(summary.get("interests", [])),
                "preferences": len(summary.get("preferences", [])),
            },
        }

    return handler


def create_suggestions_handler(suggestion_engine, kb_manager, global_memory, notification_store) -> TaskHandler:
    """Handler for generating proactive suggestions."""

    async def handler(task: ScheduledTask, config: dict[str, Any]) -> dict[str, Any]:
        new = suggestion_engine.generate(kb_manager, global_memory, notification_store)
        total = len(suggestion_engine.list_suggestions())
        return {
            "summary": f"生成了 {len(new)} 条新建议，共 {total} 条",
            "details": {"new": len(new), "total": total},
        }

    return handler
