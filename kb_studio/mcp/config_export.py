"""Generate MCP client configuration snippets."""

from __future__ import annotations

import json


def generate_claude_desktop_config(host: str = "localhost", port: int = 8000) -> str:
    """Generate claude_desktop_config.json snippet."""
    config = {
        "mcpServers": {
            "kb-studio": {
                "url": f"http://{host}:{port}/mcp/sse"
            }
        }
    }
    return json.dumps(config, indent=2)


def generate_cursor_config(host: str = "localhost", port: int = 8000) -> str:
    """Generate Cursor MCP config snippet."""
    config = {
        "mcpServers": {
            "kb-studio": {
                "url": f"http://{host}:{port}/mcp/sse"
            }
        }
    }
    return json.dumps(config, indent=2)


def generate_claude_code_config(host: str = "localhost", port: int = 8000) -> str:
    """Generate Claude Code MCP config snippet."""
    config = {
        "mcpServers": {
            "kb-studio": {
                "type": "sse",
                "url": f"http://{host}:{port}/mcp/sse"
            }
        }
    }
    return json.dumps(config, indent=2)


def generate_all_configs(host: str = "localhost", port: int = 8000) -> dict:
    """Generate all client configs at once."""
    return {
        "claude_desktop": json.loads(generate_claude_desktop_config(host, port)),
        "cursor": json.loads(generate_cursor_config(host, port)),
        "claude_code": json.loads(generate_claude_code_config(host, port)),
        "stdio": {
            "command": "kb-studio",
            "args": ["mcp", "--transport", "stdio"],
        },
    }
