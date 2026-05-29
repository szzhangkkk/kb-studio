"""MCP transport helpers."""

from __future__ import annotations

import asyncio


def run_sse_server(mcp_server, host: str = "0.0.0.0", port: int = 8001):
    """Run MCP server with SSE transport (blocking)."""
    print(f"[KB-Studio MCP] Starting SSE server on {host}:{port}")
    print(f"[KB-Studio MCP] Tools: {mcp_server.registry.list_tools().__len__()}")
    print(f"[KB-Studio MCP] Connect via: http://{host}:{port}/mcp/sse")
    asyncio.run(mcp_server.run_sse(host=host, port=port))


def run_stdio_server(mcp_server):
    """Run MCP server with stdio transport (blocking)."""
    print(f"[KB-Studio MCP] Starting stdio server", file=__import__('sys').stderr)
    print(f"[KB-Studio MCP] Tools: {len(mcp_server.registry.list_tools())}", file=__import__('sys').stderr)
    asyncio.run(mcp_server.run_stdio())
