"""Static AST policy arbiter. It never compiles or executes submitted code.

Important: AST screening is one defense-in-depth signal, NOT a sandbox. Any accepted
code must still run in a separate OS/container sandbox with no secrets, restricted
syscalls/network, resource quotas and a disposable filesystem.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    line: int
    column: int
    message: str


@dataclass(frozen=True)
class AuditReport:
    status: str
    source_sha256: str
    findings: tuple[Finding, ...]
    policy_version: str = "ast-arbiter-v1"
    execution_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_sha256": self.source_sha256,
            "findings": [asdict(f) for f in self.findings],
            "policy_version": self.policy_version,
            "execution_performed": False,
        }


_BANNED_CALLS = {
    "eval", "exec", "compile", "open", "__import__", "input",
    "breakpoint", "globals", "locals", "vars", "getattr", "setattr",
    "delattr", "help", "memoryview",
}
_BANNED_MODULES = {
    "subprocess", "socket", "ctypes", "multiprocessing", "pickle", "marshal",
    "importlib", "pty", "shlex", "webbrowser", "pathlib", "os", "sys",
}
_ALLOWED_IMPORTS = {"math", "statistics", "decimal", "fractions", "json", "re", "datetime", "typing"}
_ALLOWED_BUILTIN_CALLS = {"abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len", "list", "max", "min", "range", "round", "set", "sorted", "str", "sum", "tuple", "zip"}
_ALLOWED_NODES = (
    ast.Module, ast.Expr, ast.Assign, ast.AnnAssign, ast.AugAssign,
    ast.Name, ast.Load, ast.Store, ast.Constant, ast.List, ast.Tuple, ast.Set,
    ast.Dict, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.If,
    ast.IfExp, ast.For, ast.While, ast.Break, ast.Continue, ast.Pass,
    ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Call, ast.Import, ast.ImportFrom, ast.alias,
    ast.keyword, ast.Subscript, ast.Slice, ast.Attribute, ast.Add, ast.Sub,
    ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd,
    ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt,
    ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.ListComp, ast.SetComp,
    ast.DictComp, ast.comprehension, ast.JoinedStr, ast.FormattedValue,
)


def audit_python_source(source: str, *, max_bytes: int = 128_000,
                        max_nodes: int = 10_000, max_nesting: int = 64) -> AuditReport:
    if not isinstance(source, str):
        raise TypeError("source_must_be_text")
    for name, value, upper_bound in (
        ("max_bytes", max_bytes, 1_000_000),
        ("max_nodes", max_nodes, 100_000),
        ("max_nesting", max_nesting, 256),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= upper_bound:
            raise ValueError(f"{name}_out_of_bounds")
    try:
        encoded = source.encode("utf-8")
    except UnicodeEncodeError:
        encoded = source.encode("utf-8", errors="surrogatepass")
        digest = hashlib.sha256(encoded).hexdigest()
        return AuditReport("BLOCK", digest, (Finding("AST-012", "HIGH", 1, 0, "source_utf8_encoding_failed"),))
    digest = hashlib.sha256(encoded).hexdigest()
    findings: list[Finding] = []
    if len(encoded) > max_bytes:
        return AuditReport("BLOCK", digest, (Finding("AST-001", "CRITICAL", 1, 0, "source_size_limit_exceeded"),))
    try:
        tree = ast.parse(source, mode="exec", type_comments=False)
    except (SyntaxError, ValueError, RecursionError) as exc:
        return AuditReport("BLOCK", digest, (Finding("AST-002", "HIGH", getattr(exc, "lineno", 1) or 1,
            getattr(exc, "offset", 0) or 0, "source_parse_failed"),))
    # Bound traversal itself, rather than materializing an arbitrarily large AST
    # before enforcing max_nodes. The source-size limit is a second independent cap.
    nodes: list[ast.AST] = []
    pending: list[ast.AST] = [tree]
    while pending and len(nodes) <= max_nodes:
        node = pending.pop()
        nodes.append(node)
        pending.extend(ast.iter_child_nodes(node))
    if len(nodes) > max_nodes:
        return AuditReport("BLOCK", digest, (Finding("AST-003", "CRITICAL", 1, 0, "ast_node_limit_exceeded"),))
    def depth(node: ast.AST, current: int = 0) -> int:
        if current > max_nesting:
            return current
        children = list(ast.iter_child_nodes(node))
        return max([current] + [depth(child, current + 1) for child in children])
    try:
        if depth(tree) > max_nesting:
            findings.append(Finding("AST-004", "HIGH", 1, 0, "ast_nesting_limit_exceeded"))
    except RecursionError:
        findings.append(Finding("AST-004", "CRITICAL", 1, 0, "ast_nesting_recursion_limit_exceeded"))
    for node in nodes:
        if not isinstance(node, _ALLOWED_NODES):
            findings.append(Finding("AST-005", "HIGH", getattr(node, "lineno", 1),
                getattr(node, "col_offset", 0), "node_type_not_allowlisted:" + type(node).__name__))
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in _ALLOWED_IMPORTS:
                    findings.append(Finding("AST-006", "CRITICAL", node.lineno, node.col_offset, "import_not_allowlisted:" + alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] not in _ALLOWED_IMPORTS or node.level:
                findings.append(Finding("AST-006", "CRITICAL", node.lineno, node.col_offset, "import_from_not_allowlisted:" + module))
        elif isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if name in _BANNED_CALLS:
                findings.append(Finding("AST-007", "CRITICAL", node.lineno, node.col_offset, "dangerous_call_blocked:" + name))
            elif isinstance(node.func, ast.Name) and name not in _ALLOWED_BUILTIN_CALLS:
                findings.append(Finding("AST-011", "HIGH", node.lineno, node.col_offset, "call_not_allowlisted:" + name))
            elif isinstance(node.func, ast.Attribute):
                base = node.func.value
                if not (isinstance(base, ast.Name) and base.id in _ALLOWED_IMPORTS and name.isidentifier() and not name.startswith("_")):
                    findings.append(Finding("AST-011", "HIGH", node.lineno, node.col_offset, "attribute_call_not_allowlisted:" + name))
            if isinstance(node.func, ast.Attribute) and node.func.attr.startswith("__"):
                findings.append(Finding("AST-008", "CRITICAL", node.lineno, node.col_offset, "dunder_attribute_call_blocked"))
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            findings.append(Finding("AST-008", "CRITICAL", node.lineno, node.col_offset, "dunder_attribute_blocked"))
        elif isinstance(node, ast.Name) and node.id.startswith("__"):
            findings.append(Finding("AST-008", "CRITICAL", node.lineno, node.col_offset, "dunder_name_blocked"))
        elif isinstance(node, ast.While):
            findings.append(Finding("AST-009", "MEDIUM", node.lineno, node.col_offset, "unbounded_loop_requires_runtime_fuel_limit"))
        elif isinstance(node, ast.Pow) or isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            findings.append(Finding("AST-010", "MEDIUM", getattr(node, "lineno", 1), getattr(node, "col_offset", 0), "exponentiation_requires_runtime_resource_limits"))
    findings.sort(key=lambda f: (f.line, f.column, f.rule_id, f.message))
    status = "PASS_STATIC_SCREEN_ONLY" if not findings else "BLOCK"
    return AuditReport(status, digest, tuple(findings))
