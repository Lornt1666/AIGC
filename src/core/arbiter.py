"""Static AST policy auditor for untrusted agent source.

IMPORTANT: static inspection is a preflight signal, not a sandbox. Never execute
untrusted source in the orchestrator process; use an OS/container isolation layer.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path


MAX_SOURCE_BYTES = 256 * 1024

_BLOCKED_IMPORT_ROOTS = {
    "aiohttp",
    "ctypes",
    "ftplib",
    "httpx",
    "importlib",
    "marshal",
    "multiprocessing",
    "os",
    "pickle",
    "pty",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "smtplib",
    "telnetlib",
    "urllib",
    "websocket",
    "websockets",
    "webbrowser",
}
_BLOCKED_CALL_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "execfile",
    "getattr",
    "globals",
    "input",
    "open",
    "locals",
    "setattr",
    "delattr",
    "vars",
}
_BLOCKED_QUALIFIED_CALLS = {
    "os.popen",
    "os.system",
    "os.execv",
    "os.execve",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.Popen",
    "subprocess.run",
    "pickle.load",
    "pickle.loads",
    "marshal.loads",
}


@dataclass(frozen=True, order=True)
class AuditFinding:
    rule_id: str
    message: str
    line: int
    column: int


@dataclass(frozen=True)
class AuditReport:
    accepted: bool
    source_sha256: str
    findings: tuple[AuditFinding, ...]

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "source_sha256": self.source_sha256,
            "findings": [asdict(item) for item in self.findings],
            "execution_performed": False,
            "sandbox_established": False,
        }


def audit_source(source: str, *, max_source_bytes: int = MAX_SOURCE_BYTES) -> AuditReport:
    """Inspect Python source without importing, compiling, or executing it."""
    import hashlib

    encoded = source.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    findings: list[AuditFinding] = []

    if len(encoded) > max_source_bytes:
        findings.append(AuditFinding(
            "AST001", f"Source exceeds {max_source_bytes} byte limit.", 1, 0
        ))
        return AuditReport(False, digest, tuple(findings))

    try:
        tree = ast.parse(source, mode="exec", type_comments=False)
    except (SyntaxError, ValueError) as exc:
        findings.append(AuditFinding(
            "AST002", f"Source is not valid Python syntax: {exc.msg if isinstance(exc, SyntaxError) else str(exc)}",
            getattr(exc, "lineno", 1) or 1, max((getattr(exc, "offset", 1) or 1) - 1, 0)
        ))
        return AuditReport(False, digest, tuple(findings))

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for module in modules:
                root = module.split(".", 1)[0]
                if root in _BLOCKED_IMPORT_ROOTS:
                    findings.append(AuditFinding(
                        "AST010", f"Import of blocked module '{module}'.",
                        node.lineno, node.col_offset
                    ))

        if isinstance(node, ast.Call):
            name = _qualified_name(node.func)
            leaf = name.rsplit(".", 1)[-1]
            if leaf in _BLOCKED_CALL_NAMES:
                findings.append(AuditFinding(
                    "AST020", f"Call to blocked dynamic or interactive primitive '{name}'.",
                    node.lineno, node.col_offset
                ))
            if name in _BLOCKED_QUALIFIED_CALLS:
                findings.append(AuditFinding(
                    "AST021", f"Call to blocked process, shell, or unsafe deserialization API '{name}'.",
                    node.lineno, node.col_offset
                ))

        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            findings.append(AuditFinding(
                "AST030", f"Dunder attribute access '{node.attr}' is blocked by policy.",
                node.lineno, node.col_offset
            ))

    ordered = tuple(sorted(set(findings)))
    return AuditReport(accepted=not ordered, source_sha256=digest, findings=ordered)


def audit_file(path: str | Path, *, max_source_bytes: int = MAX_SOURCE_BYTES) -> AuditReport:
    """Read a bounded UTF-8 source file and inspect it; never import or execute it."""
    file_path = Path(path)
    with file_path.open("rb") as handle:
        raw = handle.read(max_source_bytes + 1)
    source = raw.decode("utf-8", errors="replace")
    return audit_source(source, max_source_bytes=max_source_bytes)


def _qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""
