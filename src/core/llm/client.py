"""Unified LLM client with multi-provider support and tool calling."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from src.core.llm.providers import PROVIDER_TEMPLATES, get_provider_template


@dataclass
class LLMResponse:
    content: str
    role: str = "assistant"
    tool_calls: list[dict] | None = None
    usage: dict | None = None
    model: str = ""


@dataclass
class ToolCallStep:
    """One iteration of tool calling in the agent loop."""
    tool_calls: list[dict]  # tool calls the LLM requested
    tool_results: list[dict]  # results from executing those tools
    llm_content: str = ""  # any text the LLM produced alongside tool calls

    def to_dict(self) -> dict:
        calls = []
        for tc, result in zip(self.tool_calls, self.tool_results):
            fn = tc.get("function", {})
            calls.append({
                "tool_name": fn.get("name", "unknown"),
                "arguments": fn.get("arguments", "{}"),
                "result": result.get("content", ""),
                "error": result.get("error", ""),
            })
        return {"tool_calls": calls, "content": self.llm_content}


@dataclass
class AgentResponse:
    """Final response from the agent loop."""
    content: str
    steps: list[ToolCallStep] = field(default_factory=list)
    iterations: int = 0
    total_tool_calls: int = 0
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "steps": [s.to_dict() for s in self.steps],
            "iterations": self.iterations,
            "total_tool_calls": self.total_tool_calls,
            "sources": self.sources,
        }


class LLMClient:
    """Unified interface for calling various LLM providers.

    Most providers expose OpenAI-compatible APIs, so only Claude needs special handling.
    """

    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get("provider", "custom")

        template = get_provider_template(self.provider)
        self.base_url = config.get("base_url") or template.get("base_url", "")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", template.get("models", [""])[0] if template.get("models") else "")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 4096)

        if self.provider == "claude":
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
            self._call_fn = self._call_claude
        else:
            api_key = self.api_key if self.api_key else "ollama"
            self._client = OpenAI(base_url=self.base_url, api_key=api_key)
            self._call_fn = self._call_openai_compat

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return self._call_fn(
            messages=messages,
            tools=tools,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
        )

    def chat_text(self, messages: list[dict], **kwargs) -> str:
        resp = self.chat(messages, **kwargs)
        return resp.content

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_registry,
        max_iterations: int = 10,
    ) -> AgentResponse:
        """Run the tool-calling loop: LLM calls tools, we execute them, repeat.

        Args:
            messages: Initial message array (will be mutated with tool results).
            tools: Tool definitions in OpenAI/Anthropic format.
            tool_registry: ToolRegistry instance for executing tools.
            max_iterations: Max tool-calling rounds before forced stop.

        Returns:
            AgentResponse with final answer, intermediate steps, and metadata.
        """
        if not tools:
            # No tools — just do a single call
            resp = self.chat(messages=messages)
            return AgentResponse(content=resp.content, iterations=1)

        steps: list[ToolCallStep] = []
        total_calls = 0
        sources: set[str] = set()

        for iteration in range(max_iterations):
            resp = self.chat(messages=messages, tools=tools)

            if not resp.tool_calls:
                # LLM gave a final text answer
                return AgentResponse(
                    content=resp.content,
                    steps=steps,
                    iterations=iteration + 1,
                    total_tool_calls=total_calls,
                    sources=list(sources),
                )

            # LLM wants to call tools
            # First append the assistant message with tool_calls
            assistant_msg = {"role": "assistant", "content": resp.content or ""}
            if self.provider == "claude":
                # Claude uses a different message format for tool calls
                assistant_msg["content"] = self._build_claude_content_blocks(resp)
            else:
                assistant_msg["tool_calls"] = resp.tool_calls
            messages.append(assistant_msg)

            # Execute each tool call
            tool_results = []
            for tc in resp.tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_str = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}

                record = tool_registry.execute(name, args)
                total_calls += 1

                # Collect sources from document retrieval
                if name == "document_retrieval" and record.result and not record.error:
                    for line in record.result.split("\n"):
                        if line.startswith("(来源:"):
                            sources.add(line.strip("()").replace("来源: ", ""))

                result_content = record.result if not record.error else f"[错误] {record.error}"
                tool_results.append({"content": result_content, "error": record.error})

                # Append tool result message
                if self.provider == "claude":
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tc.get("id", ""),
                            "content": result_content,
                        }],
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result_content,
                    })

            steps.append(ToolCallStep(
                tool_calls=resp.tool_calls,
                tool_results=tool_results,
                llm_content=resp.content or "",
            ))

        # Max iterations reached — return what we have
        final_resp = self.chat(messages=messages)
        return AgentResponse(
            content=final_resp.content,
            steps=steps,
            iterations=max_iterations,
            total_tool_calls=total_calls,
            sources=list(sources),
        )

    def _build_claude_content_blocks(self, resp: LLMResponse) -> list:
        """Build Claude-format content blocks from an LLMResponse."""
        blocks = []
        if resp.content:
            blocks.append({"type": "text", "text": resp.content})
        for tc in (resp.tool_calls or []):
            fn = tc.get("function", {})
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            blocks.append({
                "type": "tool_use",
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "input": args,
            })
        return blocks

    def _call_openai_compat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        usage = {}
        if resp.usage:
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
            }
        return LLMResponse(
            content=choice.message.content or "",
            role=choice.message.role,
            tool_calls=[tc.model_dump() for tc in choice.message.tool_calls] if choice.message.tool_calls else None,
            usage=usage,
            model=resp.model,
        )

    def _call_claude(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        system_msg = ""
        chat_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                chat_msgs.append(m)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": chat_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            kwargs["tools"] = tools

        resp = self._client.messages.create(**kwargs)
        content = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input),
                    },
                })

        return LLMResponse(
            content=content,
            role="assistant",
            tool_calls=tool_calls or None,
            usage={
                "prompt_tokens": resp.usage.input_tokens,
                "completion_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
            },
            model=resp.model,
        )


class EmbeddingClient:
    """Embedding client, OpenAI-compatible for all providers."""

    def __init__(self, config: dict):
        self.config = config
        self.model = config.get("model", "BAAI/bge-large-zh-v1.5")
        self.dimension = config.get("dimension", 1024)
        self.base_url = config.get("base_url", "https://api.siliconflow.cn/v1")
        self.api_key = config.get("api_key", "")
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("Embedding API Key 未配置，请在配置页面填写 Embedding 的 API Key")
            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        return self._client

    def embed(self, text: str) -> list[float]:
        client = self._ensure_client()
        resp = client.embeddings.create(model=self.model, input=text)
        return resp.data[0].embedding

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        client = self._ensure_client()
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            resp = client.embeddings.create(model=self.model, input=batch)
            all_embeddings.extend([d.embedding for d in resp.data])
        return all_embeddings
