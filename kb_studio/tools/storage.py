"""Tool persistence — stores tool definitions and implementations on disk."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from kb_studio.tools.registry import ToolDefinition


class ToolStorage:
    """Persists tools as directories under data/tools/{name}/.

    Each tool directory contains:
      - definition.yaml  — metadata (name, description, parameters, tags, source, enabled, timestamps)
      - implementation.py — Python code with a run(args, context) function
    """

    def __init__(self, data_dir: str = "./data/tools"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save(self, definition: ToolDefinition, code: str):
        """Persist a tool definition and code to disk."""
        tool_dir = self.data_dir / definition.name
        tool_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        meta = {
            "name": definition.name,
            "description": definition.description,
            "parameters": definition.parameters,
            "source": definition.source,
            "enabled": definition.enabled,
            "tags": definition.tags,
            "updated_at": now,
        }

        # Preserve created_at if updating
        def_file = tool_dir / "definition.yaml"
        if def_file.exists():
            existing = yaml.safe_load(def_file.read_text())
            meta["created_at"] = existing.get("created_at", now)
        else:
            meta["created_at"] = now

        def_file.write_text(yaml.dump(meta, allow_unicode=True, default_flow_style=False))
        (tool_dir / "implementation.py").write_text(code, encoding="utf-8")

    def load(self, name: str) -> tuple[ToolDefinition, str] | None:
        """Load a tool definition and code from disk. Returns None if not found."""
        tool_dir = self.data_dir / name
        def_file = tool_dir / "definition.yaml"
        code_file = tool_dir / "implementation.py"

        if not def_file.exists() or not code_file.exists():
            return None

        meta = yaml.safe_load(def_file.read_text())
        code = code_file.read_text(encoding="utf-8")

        definition = ToolDefinition(
            name=meta.get("name", name),
            description=meta.get("description", ""),
            parameters=meta.get("parameters", {"type": "object", "properties": {}}),
            source=meta.get("source", "custom"),
            enabled=meta.get("enabled", True),
            tags=meta.get("tags", []),
        )
        return definition, code

    def load_all(self) -> list[tuple[ToolDefinition, str]]:
        """Load all stored tools."""
        tools = []
        if not self.data_dir.exists():
            return tools
        for tool_dir in sorted(self.data_dir.iterdir()):
            if tool_dir.is_dir():
                result = self.load(tool_dir.name)
                if result:
                    tools.append(result)
        return tools

    def delete(self, name: str) -> bool:
        """Delete a tool. Returns True if deleted, False if not found."""
        tool_dir = self.data_dir / name
        if tool_dir.exists():
            shutil.rmtree(tool_dir)
            return True
        return False

    def exists(self, name: str) -> bool:
        """Check if a stored tool exists."""
        return (self.data_dir / name / "definition.yaml").exists()

    def get_code(self, name: str) -> str | None:
        """Get just the implementation code for a tool."""
        code_file = self.data_dir / name / "implementation.py"
        if code_file.exists():
            return code_file.read_text(encoding="utf-8")
        return None
