"""KB-Studio CLI."""

import click
import yaml
from pathlib import Path


@click.group()
def main():
    """KB-Studio: Self-deployable knowledge base Q&A platform."""
    pass


@main.command()
@click.option("--port", default=8000, help="Server port")
def serve(port):
    """Start the KB-Studio server."""
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import uvicorn
    uvicorn.run("kb_studio.server:app", host="0.0.0.0", port=port)


@main.command()
@click.option("--config", default="", help="Config file path")
def test_connection(config):
    """Test LLM and Embedding connection."""
    from kb_studio.core.llm.client import LLMClient
    cfg = _load_config(config)
    llm = LLMClient(cfg.get("llm", {}))
    click.echo("Testing LLM...")
    try:
        resp = llm.chat_text(messages=[{"role": "user", "content": "Say OK"}], max_tokens=10)
        click.echo(f"  LLM: OK ({resp.strip()})")
    except Exception as e:
        click.echo(f"  LLM: FAILED ({e})")


@main.command()
@click.argument("name")
@click.option("--description", default="", help="Knowledge base description")
def create_kb(name, description):
    """Create a new knowledge base."""
    from kb_studio.kb_manager import KBManager
    mgr = KBManager()
    kb = mgr.create(name, description)
    click.echo(f"Created knowledge base: {kb.name}")


@main.command()
def list_kb():
    """List all knowledge bases."""
    from kb_studio.kb_manager import KBManager
    mgr = KBManager()
    kbs = mgr.list()
    if not kbs:
        click.echo("No knowledge bases found.")
        return
    for kb in kbs:
        click.echo(f"  {kb.name} — {kb.doc_count} docs, {kb.chunk_count} chunks")


def _load_config(path: str) -> dict:
    if not path:
        for p in [Path("config/active.yaml"), Path("config/default.yaml")]:
            if p.exists():
                path = str(p)
                break
    if path and Path(path).exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


@main.command()
@click.option("--transport", default="sse", type=click.Choice(["stdio", "sse"]),
              help="Transport mode: sse (HTTP) or stdio (for Claude Desktop local)")
@click.option("--port", default=8001, help="Port for SSE transport")
def mcp(transport, port):
    """Start the MCP server for external AI tool integration."""
    from kb_studio.tools.registry import ToolRegistry
    from kb_studio.tools.builtin import register_builtin_tools
    from kb_studio.tools.storage import ToolStorage
    from kb_studio.tools.loader import ToolLoader
    from kb_studio.kb_manager import KBManager
    from kb_studio.core.llm.client import LLMClient

    # Set up registry
    registry = ToolRegistry()
    mgr = KBManager()

    def _get_engine(name):
        return None  # MCP mode doesn't need full engine

    register_builtin_tools(registry, get_manager=lambda: mgr, get_engine=_get_engine, get_engines=lambda: {})

    # Load custom tools
    storage = ToolStorage()
    loader = ToolLoader()
    registry.load_from_storage(storage, loader)

    # Create MCP server
    from kb_studio.mcp.server import KBStudioMCPServer
    cfg = _load_config("")
    llm = LLMClient(cfg.get("llm", {})) if cfg.get("llm", {}).get("api_key") else None
    mcp_server = KBStudioMCPServer(registry, get_llm=lambda: llm, get_manager=lambda: mgr)

    click.echo(f"KB-Studio MCP Server")
    click.echo(f"  Transport: {transport}")
    click.echo(f"  Tools: {len(registry)}")
    for t in registry.list_tools():
        click.echo(f"    - {t.name} [{t.source}]")

    if transport == "stdio":
        from kb_studio.mcp.transport import run_stdio_server
        run_stdio_server(mcp_server)
    else:
        from kb_studio.mcp.transport import run_sse_server
        run_sse_server(mcp_server, port=port)
