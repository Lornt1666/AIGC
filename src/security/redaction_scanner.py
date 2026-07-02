from __future__ import annotations

import argparse
import json
import math
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
    severity: str = "high"
    line_number: int = 0


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
        value = text or ""
        for pattern in self.redactor.SECRET_PATTERNS + extra_secret_patterns():
            for match in re.finditer(pattern, value, flags=re.DOTALL):
                if self._is_false_positive(match.group(0)):
                    continue
                findings.append(RedactionFinding(
                    path=path,
                    pattern=pattern,
                    redacted_preview=self.redactor.redact_text(value)[:500],
                    severity="critical" if "PRIVATE KEY" in match.group(0) else "high",
                    line_number=line_number_for_offset(value, match.start()),
                ))
        findings.extend(self._scan_secret_like_assignments(value, path))
        return findings

    def scan_paths(self, roots: Iterable[Path], suffixes: set[str] | None = None) -> List[RedactionFinding]:
        suffixes = suffixes or {".py", ".json", ".jsonl", ".md", ".txt", ".toml", ".yaml", ".yml"}
        findings: List[RedactionFinding] = []
        for root in roots:
            if root.is_file():
                candidates = [root]
            elif not root.exists():
                continue
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
            right = value.split(":", 1)[1].strip().strip("\"' ,)")
        elif "=" in value:
            right = value.split("=", 1)[1].strip().strip("\"' ,)")
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
        if len(right) < 12 and not known_secret_prefix(right):
            return True
        code_like_prefixes = (
            "request.",
            "record.",
            "self.",
            "issued.",
            "raw_",
            "hash_",
            "json.",
            "Path",
        )
        if right.startswith(code_like_prefixes):
            return True
        if "+" in value or "(" in right or ")" in right:
            return True
        if right[:1].isupper() and right.replace("_", "").isalnum():
            return True
        if "[" in right or "]" in right:
            return True
        return False

    def _scan_secret_like_assignments(self, text: str, path: str) -> List[RedactionFinding]:
        findings: List[RedactionFinding] = []
        assignment_pattern = re.compile(
            r"(?i)\b(api[_-]?key|token|secret|password|authorization|cookie|client[_-]?secret)\b"
            r"\s*[\"']?\s*[:=]\s*[\"']([^\"'\s,;]{12,})[\"']?"
        )
        for match in assignment_pattern.finditer(text or ""):
            value = match.group(2).strip()
            if self._is_placeholder(value) or self._is_false_positive(match.group(0)):
                continue
            if entropy(value) < 3.2 and not known_secret_prefix(value):
                continue
            findings.append(RedactionFinding(
                path=path,
                pattern="secret_like_assignment",
                redacted_preview=self.redactor.redact_text(text)[:500],
                severity="high",
                line_number=line_number_for_offset(text, match.start()),
            ))
        return findings

    def _is_placeholder(self, value: str) -> bool:
        lowered = value.lower()
        placeholder_terms = [
            "your_",
            "example",
            "placeholder",
            "fake",
            "local_fake",
            "test_only",
            "redacted",
            "never_logged",
            "none",
            "null",
        ]
        return any(term in lowered for term in placeholder_terms)


def extra_secret_patterns() -> List[str]:
    return [
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"AIza[0-9A-Za-z_\-]{20,}",
        r"ya29\.[0-9A-Za-z_\-]+",
        r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}",
        r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    ]


def known_secret_prefix(value: str) -> bool:
    return value.startswith(("sk-", "ghp_", "github_pat_", "glpat-", "xoxb-", "xoxp-", "xoxa-", "AIza", "ya29."))


def entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {char: value.count(char) for char in set(value)}
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def line_number_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan files for secret-like content.")
    parser.add_argument("--paths", nargs="+", default=["src", "config", "docs", "README.md", "AGENTS.md"])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scanner = RedactionScanner()
    findings = scanner.scan_paths([Path(item) for item in args.paths])
    payload = scanner.findings_as_dicts(findings)
    if args.json:
        print(json.dumps(payload, indent=2))
    elif findings:
        for finding in findings:
            print(f"{finding.severity}: {finding.path}:{finding.line_number} matched {finding.pattern}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
