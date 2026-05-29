"""Agent chat engine — uses tool-calling loop instead of plain text generation."""

from __future__ import annotations

from kb_studio.core.llm.client import LLMClient
from kb_studio.tools.registry import ToolRegistry


class AgentChatEngine:
    """Chat engine that uses LLMClient.chat_with_tools for agentic tool calling.

    Unlike ChatEngine which does a fixed retrieve-then-generate flow,
    this engine lets the LLM decide which tools to call and when.
    """

    def __init__(self, llm_client: LLMClient, tool_registry: ToolRegistry,
                 system_prompt: str = ""):
        self.llm = llm_client
        self.registry = tool_registry
        self.system_prompt = system_prompt or (
            "你是 KB-Studio 的智能助手。你可以使用提供的工具来搜索知识库、"
            "列出可用知识库等。根据用户的问题，自主决定是否需要调用工具来获取信息，"
            "然后基于获取到的信息生成准确的回答。如果工具返回了文档来源，请在回答中引用。"
        )

    def chat(self, question: str, history: list[dict] | None = None,
             memory_context: str = "", max_iterations: int = 10) -> dict:
        """Run agent chat with tool calling.

        Args:
            question: User's question.
            history: Conversation history (list of {role, content} dicts).
            memory_context: Injected memory context from KB memory system.
            max_iterations: Max tool-calling rounds.

        Returns:
            Dict with content, steps, iterations, total_tool_calls, sources.
        """
        system = self.system_prompt
        if memory_context:
            system = f"{system}\n\n知识库记忆：\n{memory_context}"

        messages = [{"role": "system", "content": system}]
        messages.extend((history or [])[-20:])
        messages.append({"role": "user", "content": question})

        tools = self.registry.get_openai_tools()
        response = self.llm.chat_with_tools(
            messages=messages,
            tools=tools,
            tool_registry=self.registry,
            max_iterations=max_iterations,
        )

        return response.to_dict()
