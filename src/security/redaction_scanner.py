from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Iterable, List

try:
    from .redactor import Redactor
except ImportError:  # pragma: no cover - direct script fallback
    from redactor import Redactor


@dataclass
class RedactionFinding:
    path: str
    pattern: str
    redacted_preview: str


class RedactionScanner:
    DEFAULT_SKIP_PARTS = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
    }

    def __init__(self, redactor: Redactor | None = None):
        self.redactor = redactor or Redactor()

    def scan_text(self, text: str, path: str = "<memory>") -> List[RedactionFinding]:
        findings: List[RedactionFinding] = []
        for pattern in self.redactor.SECRET_PATTERNS:
            for match in re.finditer(pattern, text or "", flags=re.DOTALL):
                if self._is_false_positive(match.group(0)):
                    continue
                findings.append(RedactionFinding(
                    path=path,
                    pattern=pattern,
                    redacted_preview=self.redactor.redact_text(text)[:500],
                ))
        return findings

    def scan_paths(self, roots: Iterable[Path], suffixes: set[str] | None = None) -> List[RedactionFinding]:
        suffixes = suffixes or {".py", ".json", ".jsonl", ".md", ".txt", ".toml", ".yaml", ".yml"}
        findings: List[RedactionFinding] = []
        for root in roots:
            if root.is_file():
                candidates = [root]
            else:
                candidates = [path for path in root.rglob("*") if path.is_file()]
            for path in candidates:
                if any(part in self.DEFAULT_SKIP_PARTS for part in path.parts):
                    continue
                if path.suffix.lower() not in suffixes:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                findings.extend(self.scan_text(text, str(path)))
        return findings

    def findings_as_dicts(self, findings: List[RedactionFinding]) -> List[dict]:
        return [asdict(finding) for finding in findings]

    def _is_false_positive(self, match_text: str) -> bool:
        value = match_text.strip()
        if ".*?" in value and "BEGIN PRIVATE KEY" in value:
            return True
        if "\n" in value or "\r" in value:
            return True
        if "{" in value or "}" in value:
            return True
        if ":" in value:
            right = value.split(":", 1)[1].strip().strip("\"'")
        elif "=" in value:
            right = value.split("=", 1)[1].strip().strip("\"'")
        else:
            return False
        type_like = {
            "Any",
            "Dict",
            "List",
            "Optional",
            "Path",
            "bool",
            "str",
            "int",
            "float",
            "SecretAccessRequest",
            "SecretAccessDenied",
            "SecretPolicyGate",
            "ExecutionAuthorization",
        }
        if right in type_like:
            return True
        if right[:1].isupper() and right.replace("_", "").isalnum():
            return True
        if "[" in right or "]" in right:
            return True
        return False
