"""Tool registry — manages tool definitions and execution."""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolResult:
    """Result from executing a tool. Duck-types what LLMClient.chat_with_tools expects."""

    result: str
    error: str | None = None


@dataclass
class ToolDefinition:
    """A tool's metadata and parameter schema."""

    name: str
    description: str
    parameters: dict  # JSON Schema for the tool's input
    source: str = "builtin"  # "builtin" | "custom" | "generated"
    enabled: bool = True
    tags: list[str] = field(default_factory=list)

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "source": self.source,
            "enabled": self.enabled,
            "tags": self.tags,
        }


class ToolRegistry:
    """Central registry for tools. Provides the interface that LLMClient.chat_with_tools expects."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable] = {}
        self._on_change_callbacks: list[Callable] = []

    def register(self, definition: ToolDefinition, handler: Callable):
        """Register a tool with its definition and handler function.

        Args:
            definition: Tool metadata and parameter schema.
            handler: Callable with signature (args: dict, context: dict = None) -> str.
        """
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler
        self._notify_change()

    def unregister(self, name: str):
        """Remove a tool by name."""
        self._tools.pop(name, None)
        self._handlers.pop(name, None)
        self._notify_change()

    def load_from_storage(self, storage, loader):
        """Load custom tools from ToolStorage using ToolLoader.

        Args:
            storage: ToolStorage instance.
            loader: ToolLoader instance.
        """
        for definition, code in storage.load_all():
            try:
                handler = loader.load_tool(definition, code)
                self.register(definition, handler)
            except Exception:
                pass  # Skip tools that fail to load

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool definition by name."""
        return self._tools.get(name)

    def list_tools(self, source: str | None = None) -> list[ToolDefinition]:
        """List all registered tools, optionally filtered by source."""
        tools = list(self._tools.values())
        if source:
            tools = [t for t in tools if t.source == source]
        return tools

    def get_openai_tools(self, enabled_only: bool = True) -> list[dict]:
        """Return tool definitions in OpenAI function-calling format."""
        tools = self._tools.values()
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return [t.to_openai_tool() for t in tools]

    def execute(self, name: str, args: dict, context: dict | None = None) -> ToolResult:
        """Execute a tool by name. This is the interface chat_with_tools expects.

        Args:
            name: Tool name.
            args: Tool input arguments.
            context: Optional context dict with access to KB-Studio internals.

        Returns:
            ToolResult with .result (str) and .error (str | None).
        """
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(result="", error=f"Tool '{name}' not found")

        definition = self._tools.get(name)
        if definition and not definition.enabled:
            return ToolResult(result="", error=f"Tool '{name}' is disabled")

        start = time.time()
        try:
            result = handler(args, context or {})
            elapsed = round(time.time() - start, 3)
            return ToolResult(result=str(result))
        except Exception as e:
            elapsed = round(time.time() - start, 3)
            return ToolResult(
                result="",
                error=f"{type(e).__name__}: {e}",
            )

    def on_change(self, callback: Callable):
        """Register a callback for when tools change."""
        self._on_change_callbacks.append(callback)

    def _notify_change(self):
        for cb in self._on_change_callbacks:
            try:
                cb()
            except Exception:
                pass

    def __len__(self):
        return len(self._tools)

    def __contains__(self, name: str):
        return name in self._tools
