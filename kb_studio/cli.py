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
