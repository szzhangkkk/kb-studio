"""MCP server that exposes KB-Studio tools via Model Context Protocol."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from kb_studio.tools.registry import ToolRegistry


class KBStudioMCPServer:
    """Wraps ToolRegistry as an MCP server.

    All registered tools (builtin + custom + generated) are exposed as MCP tools.
    Any MCP-compatible client (Claude Desktop, Cursor, etc.) can connect.
    """

    def __init__(self, tool_registry: ToolRegistry, get_llm=None, get_manager=None):
        self.registry = tool_registry
        self.get_llm = get_llm
        self.get_manager = get_manager
        self._mcp = FastMCP(
            name="kb-studio",
            instructions=(
                "KB-Studio 知识库问答平台 MCP Server。"
                "提供知识库搜索、文档检索等工具。"
            ),
        )
        self._synced_names: set[str] = set()
        self._setup_tools()

        # Auto-sync when registry changes
        self.registry.on_change(self.sync_tools)

    def _setup_tools(self):
        """Register all tools from the registry as MCP tools."""
        for definition in self.registry.list_tools():
            self._add_mcp_tool(definition.name)

    def _add_mcp_tool(self, name: str):
        """Add a single tool to the MCP server."""
        if name in self._synced_names:
            return

        definition = self.registry.get(name)
        if not definition or not definition.enabled:
            return

        # Create a wrapper function that MCP can call
        def make_wrapper(tool_name: str):
            def wrapper(**kwargs: Any) -> str:
                result = self.registry.execute(tool_name, kwargs, context={})
                if result.error:
                    return f"[错误] {result.error}"
                return result.result
            wrapper.__name__ = tool_name
            wrapper.__doc__ = definition.description
            return wrapper

        fn = make_wrapper(name)
        self._mcp.add_tool(fn, name=name, description=definition.description)
        self._synced_names.add(name)

    def sync_tools(self):
        """Re-sync tools after registry changes."""
        current = {t.name for t in self.registry.list_tools()}

        # Add new tools
        for name in current:
            if name not in self._synced_names:
                self._add_mcp_tool(name)

        # Remove deleted tools
        for name in list(self._synced_names):
            if name not in current:
                try:
                    self._mcp.remove_tool(name)
                except Exception:
                    pass
                self._synced_names.discard(name)

    def get_sse_app(self, mount_path: str = "/mcp"):
        """Get ASGI app for SSE transport (mountable on FastAPI)."""
        return self._mcp.sse_app(mount_path=mount_path)

    def get_streamable_http_app(self):
        """Get ASGI app for streamable HTTP transport."""
        return self._mcp.streamable_http_app()

    async def run_sse(self, host: str = "0.0.0.0", port: int = 8001):
        """Run standalone SSE server."""
        await self._mcp.run_sse_async(host=host, port=port)

    async def run_stdio(self):
        """Run stdio transport (for Claude Desktop local mode)."""
        await self._mcp.run_stdio_async()

    def get_status(self) -> dict:
        """Get MCP server status."""
        tools = self.registry.list_tools()
        return {
            "running": True,
            "tool_count": len(tools),
            "tools": [t.to_dict() for t in tools],
            "synced_count": len(self._synced_names),
        }

    def get_client_config(self, host: str = "localhost", port: int = 8000) -> dict:
        """Generate MCP client configuration for various clients."""
        return {
            "claude_desktop": {
                "mcpServers": {
                    "kb-studio": {
                        "url": f"http://{host}:{port}/mcp/sse"
                    }
                }
            },
            "cursor": {
                "mcpServers": {
                    "kb-studio": {
                        "url": f"http://{host}:{port}/mcp/sse"
                    }
                }
            },
            "claude_code": {
                "mcpServers": {
                    "kb-studio": {
                        "type": "sse",
                        "url": f"http://{host}:{port}/mcp/sse"
                    }
                }
            },
            "stdio": {
                "command": "kb-studio",
                "args": ["mcp", "--transport", "stdio"]
            },
        }
