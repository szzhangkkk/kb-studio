"""Butler tools - expose butler capabilities as MCP-compatible tools."""

from __future__ import annotations

import json
from kb_studio.tools.registry import ToolDefinition


def register_butler_tools(registry, get_scheduler, get_notifications, get_suggestions,
                          get_global_memory, get_manager, get_source_monitor):
    """Register butler tools for MCP exposure."""

    # ── butler_status ──
    registry.register(
        ToolDefinition(
            name="butler_status",
            description="查看管家状态：调度器运行状态、定时任务数量、源监控数量、未读通知数。当用户问管家状态、系统状态、有什么通知时使用。",
            parameters={"type": "object", "properties": {}},
            source="builtin",
            tags=["butler", "status"],
        ),
        lambda args, ctx: _butler_status(get_scheduler, get_notifications, get_source_monitor),
    )

    # ── butler_list_tasks ──
    registry.register(
        ToolDefinition(
            name="butler_list_tasks",
            description="列出所有定时任务及其状态、上次执行结果。",
            parameters={"type": "object", "properties": {}},
            source="builtin",
            tags=["butler", "scheduler"],
        ),
        lambda args, ctx: _list_tasks(get_scheduler),
    )

    # ── butler_run_task ──
    registry.register(
        ToolDefinition(
            name="butler_run_task",
            description="立即执行一个定时任务。用于手动触发巡检、分析、摘要等。",
            parameters={
                "type": "object",
                "properties": {
                    "task_name": {
                        "type": "string",
                        "description": "任务名称（模糊匹配）",
                    },
                },
                "required": ["task_name"],
            },
            source="builtin",
            tags=["butler", "scheduler"],
        ),
        lambda args, ctx: _run_task(args, get_scheduler),
    )

    # ── butler_notifications ──
    registry.register(
        ToolDefinition(
            name="butler_notifications",
            description="查看最近的通知消息。可指定只看未读通知。",
            parameters={
                "type": "object",
                "properties": {
                    "unread_only": {
                        "type": "boolean",
                        "description": "是否只看未读通知",
                        "default": False,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量，默认 10",
                        "default": 10,
                    },
                },
            },
            source="builtin",
            tags=["butler", "notifications"],
        ),
        lambda args, ctx: _get_notifications(args, get_notifications),
    )

    # ── butler_suggestions ──
    registry.register(
        ToolDefinition(
            name="butler_suggestions",
            description="查看管家的主动建议：过期文档提醒、兴趣分析、质量建议等。",
            parameters={"type": "object", "properties": {}},
            source="builtin",
            tags=["butler", "suggestions"],
        ),
        lambda args, ctx: _get_suggestions(get_suggestions),
    )

    # ── butler_generate_suggestions ──
    registry.register(
        ToolDefinition(
            name="butler_generate_suggestions",
            description="让管家重新分析并生成新的建议。会检查文档过期、质量、用户兴趣等。",
            parameters={"type": "object", "properties": {}},
            source="builtin",
            tags=["butler", "suggestions"],
        ),
        lambda args, ctx: _generate_suggestions(get_suggestions, get_manager, get_global_memory, get_notifications),
    )

    # ── butler_memory ──
    registry.register(
        ToolDefinition(
            name="butler_memory",
            description="查看管家的全局记忆：用户关注领域、偏好、记忆统计。",
            parameters={"type": "object", "properties": {}},
            source="builtin",
            tags=["butler", "memory"],
        ),
        lambda args, ctx: _get_memory(get_global_memory),
    )

    # ── butler_staleness ──
    registry.register(
        ToolDefinition(
            name="butler_staleness",
            description="检查所有知识库文档的新鲜度：多少篇新鲜、老化、过期。",
            parameters={"type": "object", "properties": {}},
            source="builtin",
            tags=["butler", "staleness"],
        ),
        lambda args, ctx: _check_staleness(get_manager),
    )

    # ── butler_source_watches ──
    registry.register(
        ToolDefinition(
            name="butler_source_watches",
            description="查看源监控列表：正在监控哪些 URL，最近是否有变化。",
            parameters={"type": "object", "properties": {}},
            source="builtin",
            tags=["butler", "sources"],
        ),
        lambda args, ctx: _list_source_watches(get_source_monitor),
    )


# ── Handler implementations ──

def _butler_status(get_scheduler, get_notifications, get_source_monitor):
    try:
        scheduler = get_scheduler()
        status = scheduler.get_status()
        notif_store = get_notifications()
        source_monitor = get_source_monitor()
        watches = source_monitor.list_watches()
        enabled_watches = [w for w in watches if w.enabled]

        return json.dumps({
            "调度器": "运行中" if status["running"] else "已停止",
            "定时任务": f"{status['active_tasks']} 活跃 / {status['total_tasks']} 总计",
            "源监控": f"{len(enabled_watches)} 个启用",
            "未读通知": notif_store.unread_count(),
            "已注册处理器": status["registered_handlers"],
        }, ensure_ascii=False)
    except Exception as e:
        return f"获取状态失败: {e}"


def _list_tasks(get_scheduler):
    try:
        scheduler = get_scheduler()
        tasks = scheduler.list_tasks()
        if not tasks:
            return "暂无定时任务"

        lines = []
        for t in tasks:
            status = "启用" if t.enabled else "暂停"
            last = t.last_result or "尚未执行"
            lines.append(f"- {t.name} [{t.task_type}] {status} | 间隔: {t.interval} | 上次: {last}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取任务失败: {e}"


def _run_task(args, get_scheduler):
    try:
        task_name = args.get("task_name", "")
        scheduler = get_scheduler()
        tasks = scheduler.list_tasks()

        # Fuzzy match
        matched = None
        for t in tasks:
            if task_name.lower() in t.name.lower() or task_name.lower() in t.task_type.lower():
                matched = t
                break

        if not matched:
            return f"未找到匹配的任务: {task_name}"

        import asyncio
        loop = asyncio.get_event_loop()
        run = loop.run_until_complete(scheduler.run_task_now(matched.task_id))
        if run:
            return f"任务 {matched.name} 执行完成: {run.status} - {run.result_summary}"
        return "任务执行失败"
    except Exception as e:
        return f"执行任务失败: {e}"


def _get_notifications(args, get_notifications):
    try:
        store = get_notifications()
        unread_only = args.get("unread_only", False)
        limit = args.get("limit", 10)
        notifs = store.list_all(limit=limit, unread_only=unread_only)

        if not notifs:
            return "暂无通知"

        lines = [f"未读: {store.unread_count()} 条"]
        for n in notifs:
            read_mark = "已读" if n.read else "未读"
            lines.append(f"- [{read_mark}] [{n.level}] {n.title}: {n.body[:80]}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取通知失败: {e}"


def _get_suggestions(get_suggestions):
    try:
        engine = get_suggestions()
        suggestions = engine.list_suggestions()
        if not suggestions:
            return "暂无建议。运行 butler_generate_suggestions 生成新建议。"

        lines = []
        for s in suggestions:
            prio = {"high": "重要", "normal": "一般", "low": "低"}.get(s.get("priority", ""), "?")
            lines.append(f"- [{prio}] {s['title']}: {s['body'][:80]}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取建议失败: {e}"


def _generate_suggestions(get_suggestions, get_manager, get_global_memory, get_notifications):
    try:
        engine = get_suggestions()
        new = engine.generate(get_manager(), get_global_memory(), get_notifications())
        total = len(engine.list_suggestions())
        if new:
            titles = [s["title"] for s in new]
            return f"生成了 {len(new)} 条新建议（共 {total} 条）:\n" + "\n".join(f"- {t}" for t in titles)
        return f"没有新建议（共 {total} 条现有建议）"
    except Exception as e:
        return f"生成建议失败: {e}"


def _get_memory(get_global_memory):
    try:
        gm = get_global_memory()
        summary = gm.get_summary()
        lines = [f"全局记忆: {summary['total_entries']} 条"]

        interests = summary.get("interests", [])
        if interests:
            lines.append(f"关注领域: {', '.join(interests[-10:])}")

        prefs = summary.get("preferences", [])
        if prefs:
            lines.append(f"偏好: {', '.join(prefs[-5:])}")

        by_kb = summary.get("by_kb", {})
        if by_kb:
            lines.append("按知识库分布:")
            for kb, count in sorted(by_kb.items(), key=lambda x: -x[1]):
                lines.append(f"  - {kb}: {count} 条")

        return "\n".join(lines)
    except Exception as e:
        return f"获取记忆失败: {e}"


def _check_staleness(get_manager):
    try:
        from datetime import datetime as _dt
        mgr = get_manager()
        now = _dt.utcnow()
        fresh = aging = stale = 0
        stale_list = []

        for kb in mgr.list():
            docs = mgr.list_documents(kb.name)
            for doc in docs:
                upload_time = doc.get("upload_time", "")
                if upload_time:
                    try:
                        uploaded = _dt.fromisoformat(upload_time.replace("Z", "+00:00")).replace(tzinfo=None)
                        age = (now - uploaded).days
                        if age > 30:
                            stale += 1
                            stale_list.append(f"{kb.name}/{doc.get('filename', '')} ({age}天)")
                        elif age > 7:
                            aging += 1
                        else:
                            fresh += 1
                    except (ValueError, TypeError):
                        pass

        lines = [f"文档新鲜度: {fresh} 新鲜, {aging} 老化, {stale} 过期"]
        if stale_list:
            lines.append("过期文档:")
            for s in stale_list[:5]:
                lines.append(f"  - {s}")
        return "\n".join(lines)
    except Exception as e:
        return f"检查新鲜度失败: {e}"


def _list_source_watches(get_source_monitor):
    try:
        monitor = get_source_monitor()
        watches = monitor.list_watches()
        if not watches:
            return "暂无源监控。可在管家面板添加 URL 监控。"

        lines = []
        for w in watches:
            status = "启用" if w.enabled else "暂停"
            changes = f"{w.change_count}次变化" if w.change_count > 0 else "无变化"
            lines.append(f"- [{status}] {w.name or w.url} → {w.kb_name} | 已抓取{w.fetch_count}次, {changes}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取源监控失败: {e}"
