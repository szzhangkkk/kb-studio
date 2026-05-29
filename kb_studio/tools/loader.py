"""Dynamic tool loader with sandboxed execution."""

from __future__ import annotations

import ast
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from kb_studio.tools.registry import ToolDefinition, ToolResult
from kb_studio.tools.sandbox import check_code_safety


# Safe modules that tools can use via import
SAFE_MODULES = {
    "math": math,
    "json": json,
    "re": re,
    "datetime": datetime,
}


def _make_safe_import(allowed_modules: dict) -> Callable:
    """Create a safe __import__ that only allows whitelisted modules."""
    def safe_import(name, *args, **kwargs):
        top = name.split(".")[0]
        if top in allowed_modules or name in allowed_modules:
            return allowed_modules.get(name, allowed_modules.get(top))
        raise ImportError(f"Import of '{name}' is not allowed in tool sandbox")
    return safe_import


def _build_safe_globals() -> dict:
    """Build a restricted globals dict for exec()."""
    safe_import = _make_safe_import(SAFE_MODULES)

    safe_builtins = {
        "__import__": safe_import,
        # Data types
        "bool": bool, "int": int, "float": float, "str": str,
        "list": list, "dict": dict, "tuple": tuple, "set": set,
        "frozenset": frozenset, "bytes": bytes, "bytearray": bytearray,
        # Functions (safe subset)
        "abs": abs, "all": all, "any": any, "bin": bin, "chr": chr,
        "divmod": divmod, "enumerate": enumerate, "filter": filter,
        "format": format, "hash": hash, "hex": hex,
        "isinstance": isinstance, "issubclass": issubclass, "iter": iter,
        "len": len, "map": map, "max": max, "min": min, "next": next,
        "oct": oct, "ord": ord, "pow": pow, "print": print,
        "range": range, "repr": repr, "reversed": reversed, "round": round,
        "sorted": sorted, "sum": sum, "zip": zip,
        # Exceptions
        "Exception": Exception, "ValueError": ValueError,
        "TypeError": TypeError, "KeyError": KeyError,
        "IndexError": IndexError, "AttributeError": AttributeError,
        "RuntimeError": RuntimeError, "StopIteration": StopIteration,
        "ZeroDivisionError": ZeroDivisionError,
        # Constants
        "True": True, "False": False, "None": None,
    }

    return {
        "__builtins__": safe_builtins,
        **SAFE_MODULES,
        # Re-export common sub-modules
        "timedelta": timedelta,
        "timezone": timezone,
    }


class ToolLoader:
    """Loads and executes tool code in a restricted sandbox."""

    def load_tool(self, definition: ToolDefinition, code: str) -> Callable:
        """Compile and load a tool's code into a callable.

        The code must define a function named 'run' with signature:
            run(args: dict, context: dict = None) -> str

        Returns a wrapped callable that matches ToolRegistry's handler interface.
        """
        # Validate first
        errors = self.validate_code(code)
        if errors:
            raise ValueError(f"代码安全检查失败:\n" + "\n".join(errors))

        safe_globals = _build_safe_globals()
        safe_locals: dict[str, Any] = {}

        try:
            compiled = compile(code, f"<tool:{definition.name}>", "exec")
            exec(compiled, safe_globals, safe_locals)
        except SyntaxError as e:
            raise ValueError(f"语法错误: {e}") from e
        except Exception as e:
            raise ValueError(f"代码执行错误: {e}") from e

        # Find the run function
        run_fn = safe_locals.get("run")
        if run_fn is None:
            # Try to find a function matching the tool name
            run_fn = safe_locals.get(definition.name)
        if run_fn is None:
            raise ValueError("代码中必须定义 run(args, context=None) 函数")
        if not callable(run_fn):
            raise ValueError("run 必须是一个可调用的函数")

        return self._wrap_handler(run_fn, definition)

    def validate_code(self, code: str) -> list[str]:
        """Validate code for safety. Returns list of errors (empty = valid)."""
        errors = []

        # Check syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"语法错误: {e}")
            return errors

        # Check for 'run' function
        try:
            tree = ast.parse(code)
            has_run = False
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "run":
                    has_run = True
                    break
            if not has_run:
                errors.append("代码必须定义名为 'run' 的函数")
        except Exception:
            pass  # Syntax already checked above

        # AST-based safety check
        safety_errors = check_code_safety(code)
        errors.extend(safety_errors)

        return errors

    def _wrap_handler(self, fn: Callable, definition: ToolDefinition) -> Callable:
        """Wrap a loaded function to match the tool handler interface with timeout."""
        import threading

        def handler(args: dict, context: dict) -> str:
            timeout = 30  # seconds
            result_holder: list = []
            error_holder: list = []

            def target():
                try:
                    result_holder.append(fn(args, context))
                except Exception as e:
                    error_holder.append(e)

            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            thread.join(timeout=timeout)

            if thread.is_alive():
                return f"[超时] 工具执行超过 {timeout}s 限制"

            if error_holder:
                e = error_holder[0]
                return f"[工具执行错误] {type(e).__name__}: {e}"

            result = result_holder[0] if result_holder else None
            return str(result) if result is not None else ""

        return handler
