"""Built-in tools that wrap KB-Studio core functionality."""

from __future__ import annotations

from kb_studio.tools.registry import ToolDefinition


def register_builtin_tools(registry, get_manager, get_engine, get_engines):
    """Register all built-in tools.

    Args:
        registry: ToolRegistry instance.
        get_manager: Callable returning KBManager.
        get_engine: Callable(kb_name) returning ChatEngine.
        get_engines: Callable returning engines dict.
    """

    # ── document_retrieval ──

    registry.register(
        ToolDefinition(
            name="document_retrieval",
            description=(
                "从指定知识库中检索相关文档片段。"
                "当用户提问需要查找知识库中的信息时使用此工具。"
                "返回最相关的文档片段及其来源。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询文本",
                    },
                    "kb_name": {
                        "type": "string",
                        "description": "知识库名称。如果不指定，将搜索所有知识库。",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认 5",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
            source="builtin",
            tags=["retrieval", "knowledge-base"],
        ),
        lambda args, ctx: _document_retrieval(args, get_manager, get_engine, get_engines),
    )

    # ── list_knowledge_bases ──

    registry.register(
        ToolDefinition(
            name="list_knowledge_bases",
            description="列出所有可用的知识库及其描述。当用户询问有哪些知识库可用时使用。",
            parameters={
                "type": "object",
                "properties": {},
            },
            source="builtin",
            tags=["knowledge-base"],
        ),
        lambda args, ctx: _list_knowledge_bases(get_manager),
    )

    # ── search_all_kbs ──

    registry.register(
        ToolDefinition(
            name="search_all_kbs",
            description="跨所有知识库搜索相关文档。当不确定哪个知识库有答案时使用。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询文本",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "每个知识库返回的结果数，默认 3",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
            source="builtin",
            tags=["retrieval", "knowledge-base"],
        ),
        lambda args, ctx: _search_all_kbs(args, get_manager, get_engine),
    )


def _document_retrieval(args, get_manager, get_engine, get_engines) -> str:
    query = args.get("query", "")
    kb_name = args.get("kb_name")
    top_k = args.get("top_k", 5)

    if not query:
        return "错误：query 参数不能为空"

    mgr = get_manager()

    # If no KB specified, search all
    if not kb_name:
        return _search_all_kbs({"query": query, "top_k": top_k}, get_manager, get_engine)

    # Validate KB exists
    kbs = [kb.name for kb in mgr.list()]
    if kb_name not in kbs:
        return f"错误：知识库 '{kb_name}' 不存在。可用的知识库：{', '.join(kbs)}"

    try:
        engine = get_engine(kb_name)
        result = engine.search(query, top_k=top_k)
    except Exception as e:
        return f"检索失败：{e}"

    if not result.get("results"):
        return f"在知识库 '{kb_name}' 中没有找到与 '{query}' 相关的内容。"

    lines = [f"在知识库 '{kb_name}' 中找到 {len(result['results'])} 条相关结果：\n"]
    for i, r in enumerate(result["results"], 1):
        score_pct = round(r["score"] * 100, 1)
        lines.append(f"--- 结果 {i} (相关度: {score_pct}%) ---")
        lines.append(f"来源: {r['source']}")
        if r.get("heading_path"):
            lines.append(f"章节: {' > '.join(r['heading_path'])}")
        lines.append(f"内容: {r['content']}")
        lines.append("")

    return "\n".join(lines)


def _list_knowledge_bases(get_manager) -> str:
    mgr = get_manager()
    kbs = mgr.list()
    if not kbs:
        return "当前没有任何知识库。"

    lines = ["可用的知识库：\n"]
    for kb in kbs:
        desc = f" — {kb.description}" if kb.description else ""
        lines.append(f"- {kb.name}{desc} ({kb.doc_count} 篇文档, {kb.chunk_count} 个分块)")
    return "\n".join(lines)


def _search_all_kbs(args, get_manager, get_engine) -> str:
    query = args.get("query", "")
    top_k = args.get("top_k", 3)

    if not query:
        return "错误：query 参数不能为空"

    mgr = get_manager()
    kbs = mgr.list()
    if not kbs:
        return "当前没有任何知识库。"

    all_results = []
    for kb in kbs:
        try:
            engine = get_engine(kb.name)
            result = engine.search(query, top_k=top_k)
            for r in result.get("results", []):
                r["kb_name"] = kb.name
                all_results.append(r)
        except Exception:
            continue

    if not all_results:
        return f"在所有知识库中都没有找到与 '{query}' 相关的内容。"

    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    all_results = all_results[:top_k * 2]

    lines = [f"跨所有知识库搜索 '{query}'，找到 {len(all_results)} 条结果：\n"]
    for i, r in enumerate(all_results, 1):
        score_pct = round(r["score"] * 100, 1)
        lines.append(f"--- 结果 {i} (相关度: {score_pct}%) ---")
        lines.append(f"知识库: {r.get('kb_name', '未知')}")
        lines.append(f"来源: {r['source']}")
        if r.get("heading_path"):
            lines.append(f"章节: {' > '.join(r['heading_path'])}")
        lines.append(f"内容: {r['content']}")
        lines.append("")

    return "\n".join(lines)
