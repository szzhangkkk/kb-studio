"""AST-based code analysis for tool sandboxing."""

from __future__ import annotations

import ast


ALLOWED_MODULES = frozenset({
    "math", "json", "re", "datetime", "typing", "collections",
    "itertools", "functools", "hashlib", "base64", "urllib.parse",
    "html", "textwrap", "string", "decimal", "fractions",
    "random", "statistics", "copy", "pprint", "enum",
})

BLOCKED_NAMES = frozenset({
    "os", "sys", "subprocess", "importlib", "shutil", "pathlib",
    "socket", "http", "urllib", "requests", "httpx",
    "ctypes", "signal", "threading", "multiprocessing",
    "sqlite3", "pickle", "shelve", "dbm",
    "__import__", "open", "exec", "eval", "compile",
    "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr",
    "breakpoint", "exit", "quit",
    "input",
})

# Allow urllib.parse specifically (it's safe), but block urllib broadly
SAFE_SUBMODULES = frozenset({"urllib.parse"})


class ImportChecker(ast.NodeVisitor):
    """AST visitor that flags disallowed imports in tool code."""

    def __init__(self):
        self.violations: list[str] = []

    def check(self, code: str) -> list[str]:
        """Parse code and return list of violation messages. Empty = safe."""
        self.violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return [f"语法错误: {e}"]
        self.visit(tree)
        return self.violations

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod = alias.name.split(".")[0]
            full = alias.name
            if full in SAFE_SUBMODULES:
                continue
            if mod in BLOCKED_NAMES or mod not in ALLOWED_MODULES:
                self.violations.append(f"禁止导入: import {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module is None:
            self.generic_visit(node)
            return
        mod = node.module.split(".")[0]
        full = node.module
        if full in SAFE_SUBMODULES:
            self.generic_visit(node)
            return
        if mod in BLOCKED_NAMES or mod not in ALLOWED_MODULES:
            self.violations.append(f"禁止导入: from {node.module} import ...")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Check for calls to dangerous builtins."""
        # Check direct calls like __import__("os")
        if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_NAMES:
            self.violations.append(f"禁止调用: {node.func.id}()")
        # Check open() calls
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            self.violations.append("禁止调用: open() — 工具不允许直接读写文件")
        self.generic_visit(node)


def check_code_safety(code: str) -> list[str]:
    """Check code for safety violations. Returns list of errors (empty = safe)."""
    checker = ImportChecker()
    return checker.check(code)
