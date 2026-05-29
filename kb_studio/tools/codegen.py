"""LLM-powered tool code generation."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field

from kb_studio.core.llm.client import LLMClient
from kb_studio.tools.sandbox import check_code_safety


@dataclass
class GeneratedTool:
    name: str
    description: str
    parameters: dict
    code: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "code": self.code,
            "warnings": self.warnings,
        }


GENERATION_SYSTEM_PROMPT = """你是 KB-Studio 的工具代码生成器。根据用户的自然语言描述，生成一个 Python 工具。

## 输出格式
严格输出一个 JSON 对象，不要输出其他任何文字、不要用 markdown 代码块：
{
  "name": "tool_name_snake_case",
  "description": "工具的简短描述（用于 LLM 判断何时调用此工具）",
  "parameters": {
    "type": "object",
    "properties": {
      "param1": {"type": "string", "description": "参数说明"}
    },
    "required": ["param1"]
  },
  "code": "import json\\n\\ndef run(args, context=None):\\n    ..."
}

## 代码要求
- 必须定义 `run(args, context=None) -> str` 函数
- `args` 是一个 dict，包含用户定义的参数
- `context` 是一个 dict，提供以下可用函数（当不为 None 时）：
  - `context["search"](query, kb_name=None, top_k=5)` — 搜索知识库
  - `context["list_kbs"]()` — 列出所有知识库
  - `context["llm_chat"](prompt)` — 调用 LLM（用于复杂推理）
- 返回值必须是字符串

## 安全约束
允许的 import：math, json, re, datetime, typing, collections, itertools, functools, hashlib, base64, textwrap, string
禁止的 import：os, sys, subprocess, socket, http, requests, open(), 文件操作, 网络调用

## 参数类型映射
- 文本 → "string"
- 数字 → "number" 或 "integer"
- 布尔 → "boolean"
- 列表 → "array"
- 对象 → "object"
"""


REFINE_SYSTEM_PROMPT = """你是 KB-Studio 的工具代码优化器。用户会给你现有代码和改进反馈，请输出优化后的完整 JSON 对象。

输出格式与生成时相同（严格 JSON，无 markdown）：
{
  "name": "tool_name",
  "description": "...",
  "parameters": {...},
  "code": "..."
}

保持安全约束不变（禁止 os/sys/subprocess/文件操作/网络调用）。
"""


class ToolCodeGenerator:
    """Generates tool code from natural language descriptions using LLM."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate(self, description: str, context: str = "") -> GeneratedTool:
        """Generate a tool from a natural language description.

        Args:
            description: What the tool should do.
            context: Additional context (e.g., specific KB names, business logic).

        Returns:
            GeneratedTool with name, description, parameters, code.
        """
        user_msg = f"请生成一个工具：\n{description}"
        if context:
            user_msg += f"\n\n额外上下文：{context}"

        messages = [
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        raw = self.llm.chat_text(messages=messages, temperature=0.3, max_tokens=4000)
        return self._parse_and_validate(raw)

    def refine(self, existing_code: str, feedback: str) -> GeneratedTool:
        """Refine an existing tool based on user feedback.

        Args:
            existing_code: Current tool code or full JSON.
            feedback: What the user wants changed.

        Returns:
            Refined GeneratedTool.
        """
        messages = [
            {"role": "system", "content": REFINE_SYSTEM_PROMPT},
            {"role": "user", "content": f"现有代码/定义：\n{existing_code}\n\n请改进：{feedback}"},
        ]

        raw = self.llm.chat_text(messages=messages, temperature=0.3, max_tokens=4000)
        return self._parse_and_validate(raw)

    def validate_and_fix(self, tool: GeneratedTool) -> tuple[GeneratedTool, list[str]]:
        """Validate generated code. If syntax errors, attempt one auto-fix round.

        Returns:
            (possibly-fixed tool, list of remaining warnings).
        """
        warnings = list(tool.warnings)

        # Syntax check
        try:
            ast.parse(tool.code)
        except SyntaxError as e:
            # Try auto-fix: ask LLM to fix the syntax error
            fix_msg = f"以下代码有语法错误，请修复后重新输出完整的 JSON：\n\n错误：{e}\n\n代码：\n{tool.code}"
            messages = [
                {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": fix_msg},
            ]
            try:
                raw = self.llm.chat_text(messages=messages, temperature=0.1, max_tokens=4000)
                fixed = self._parse_and_validate(raw)
                tool = fixed
                warnings.append("已自动修复语法错误")
            except Exception:
                warnings.append(f"语法错误无法自动修复: {e}")

        # Safety check — reject unsafe code
        safety_errors = check_code_safety(tool.code)
        if safety_errors:
            raise ValueError(f"生成的代码包含不安全内容，已拒绝:\n" + "\n".join(safety_errors))

        # Check for run function
        try:
            tree = ast.parse(tool.code)
            has_run = any(
                isinstance(node, ast.FunctionDef) and node.name == "run"
                for node in ast.walk(tree)
            )
            if not has_run:
                warnings.append("代码中缺少 run(args, context) 函数")
        except Exception:
            pass

        tool.warnings = warnings
        return tool, warnings

    def _parse_and_validate(self, raw: str) -> GeneratedTool:
        """Parse LLM response into GeneratedTool."""
        raw = raw.strip()

        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(raw[start:end])
                except json.JSONDecodeError as e:
                    raise ValueError(f"LLM 输出无法解析为 JSON: {e}\n\n原始输出:\n{raw[:500]}")
            else:
                raise ValueError(f"LLM 输出中没有找到 JSON 对象:\n{raw[:500]}")

        # Validate required fields
        missing = []
        for key in ("name", "description", "parameters", "code"):
            if key not in data:
                missing.append(key)
        if missing:
            raise ValueError(f"LLM 输出缺少必要字段: {', '.join(missing)}")

        # Validate name format
        name = data["name"]
        if not name.replace("_", "").isalnum() or not name[0].isalpha():
            raise ValueError(f"工具名 '{name}' 格式不正确（需要 snake_case）")

        return GeneratedTool(
            name=name,
            description=data["description"],
            parameters=data.get("parameters", {"type": "object", "properties": {}}),
            code=data["code"],
        )
