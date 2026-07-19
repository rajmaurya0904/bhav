"""Static AST guard for strategy files.

Strategy files are `exec`'d by the engine (`bhav.cli._load_strategy`), so an
uploaded or AI-generated file is arbitrary code running with the server's
privileges. This module parses the source *without executing it* and rejects the
common escape hatches: dangerous imports, `eval`/`exec`/`open`, `__import__`, and
dunder attribute access (`__globals__`, `__subclasses__`, ...) used to break out
of a restricted namespace.

It is a static gate, not a true sandbox — it raises the bar and blocks accidental
or obviously-malicious code. Review generated code before trusting it with money.
"""
from __future__ import annotations

import ast

# Top-level modules a strategy is allowed to import. Whitelist, not blocklist:
# anything not named here is refused. Kept deliberately small — a strategy needs
# arithmetic, dates, and the bhav API, very little else.
ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        "bhav",
        "math",
        "statistics",
        "datetime",
        "collections",
        "dataclasses",
        "typing",
        "itertools",
        "functools",
        "decimal",
        "enum",
        "abc",
        "re",
        "random",
        "zoneinfo",
        "polars",
        "__future__",
    }
)

# Builtins that enable code execution, imports, or filesystem/process access.
FORBIDDEN_CALLS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "memoryview",
    }
)

# Dunder attributes that are the usual sandbox-escape ladder.
FORBIDDEN_ATTRS: frozenset[str] = frozenset(
    {
        "__globals__",
        "__subclasses__",
        "__bases__",
        "__base__",
        "__mro__",
        "__builtins__",
        "__class__",
        "__dict__",
        "__code__",
        "__loader__",
        "__import__",
        "__getattribute__",
    }
)


class ValidationError(Exception):
    """Raised when a strategy source contains disallowed constructs.

    `violations` is the full list of `"line N: message"` strings so callers (API,
    CLI, frontend) can surface every problem at once rather than one at a time.
    """

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("; ".join(violations))


class _Guard(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[str] = []

    def _flag(self, node: ast.AST, msg: str) -> None:
        line = getattr(node, "lineno", "?")
        self.violations.append(f"line {line}: {msg}")

    def _check_module(self, node: ast.AST, module: str) -> None:
        top = module.split(".", 1)[0]
        if top not in ALLOWED_IMPORTS:
            self._flag(node, f"import of '{module}' is not allowed")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_module(node, alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # `from . import x` (relative, module is None) never reaches user files.
        if node.module is not None:
            self._check_module(node, node.module)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
            self._flag(node, f"call to '{func.id}()' is not allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_CALLS and node.id in {"eval", "exec", "__import__"}:
            # bare reference (e.g. `f = exec`) as well as direct calls
            self._flag(node, f"reference to '{node.id}' is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in FORBIDDEN_ATTRS:
            self._flag(node, f"access to '{node.attr}' is not allowed")
        self.generic_visit(node)


def check_strategy_source(source: str) -> list[str]:
    """Return a list of violations (empty means clean). Does not raise for
    disallowed constructs; a syntax error is reported as a single violation."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"line {e.lineno}: syntax error: {e.msg}"]
    guard = _Guard()
    guard.visit(tree)
    if "strategy" not in {
        t.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for t in node.targets
        if isinstance(t, ast.Name)
    }:
        guard.violations.append("line 0: file must assign a module-level `strategy`")
    return guard.violations


def validate_strategy_source(source: str) -> None:
    """Raise ValidationError if `source` contains any disallowed construct."""
    violations = check_strategy_source(source)
    if violations:
        raise ValidationError(violations)
