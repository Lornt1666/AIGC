from __future__ import annotations

"""Deterministic, fail-safe redaction for untrusted text projections.

This boundary is intentionally small.  It protects receipts, prompts, and error
messages from common credential forms; it is not a substitute for a dedicated
secret scanner at the repository or deployment boundary.
"""

from dataclasses import dataclass, field
import re
from typing import Pattern


REDACTION_MARKER = "[REDACTED_SECRET]"


def _compiled_patterns() -> tuple[Pattern[str], ...]:
    flags = re.IGNORECASE | re.MULTILINE
    return (
        # Authorization credentials are handled before generic key/value
        # assignments so ``Authorization: Bearer <token>`` is redacted as one
        # unit instead of consuming only the word ``Bearer``.
        re.compile(
            r"(?P<prefix>\bAuthorization\s*:\s*(?:Bearer|Basic)\s+)"
            r"[A-Za-z0-9._~+/=-]{8,}",
            flags,
        ),
        re.compile(r"(?P<prefix>\bBearer\s+)[A-Za-z0-9._~+/=-]{8,}", flags),
        re.compile(r"(?P<prefix>\bBasic\s+)[A-Za-z0-9+/=]{8,}", flags),
        # Key/value credentials, with optional quoting.  Preserve the key so a
        # reviewer can still understand what kind of value was removed.
        re.compile(
            r"(?P<prefix>\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|"
            r"client[_-]?secret|password|passwd|secret|token)\b"
            r"\s*[:=]\s*)(?P<quote>['\"]?)(?P<value>[^\s,;}\]\"']{4,})(?P=quote)",
            flags,
        ),
        # Common provider token prefixes.  Deliberately require a meaningful
        # suffix to avoid redacting ordinary prose containing these fragments.
        re.compile(
            r"\b(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza)[A-Za-z0-9_-]{12,}\b",
            flags,
        ),
        # Private-key material must never enter model or receipt projections.
        re.compile(
            r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?"
            r"-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
            re.DOTALL,
        ),
    )


@dataclass(frozen=True)
class Redactor:
    """Redact credential-like values while retaining useful surrounding text."""

    marker: str = REDACTION_MARKER
    patterns: tuple[Pattern[str], ...] = field(default_factory=_compiled_patterns)

    def __post_init__(self) -> None:
        if not self.marker:
            raise ValueError("redaction marker cannot be empty")
        if not self.patterns:
            raise ValueError("at least one redaction pattern is required")

    def redact_text(self, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("redaction input must be text")
        projected = value
        for pattern in self.patterns:
            projected = pattern.sub(self._replacement, projected)
        return projected

    def _replacement(self, match: re.Match[str]) -> str:
        prefix = match.groupdict().get("prefix") or ""
        return f"{prefix}{self.marker}"
