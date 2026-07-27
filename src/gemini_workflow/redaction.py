from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d .()_-]{7,}\d)(?!\d)")
_SECRET = re.compile(
    r"(?i)\b(api[_ -]?key|authorization|bearer|password|secret|token)\b"
    r"\s*[:=]\s*[^\s,;]{6,}"
)


def redact_text(value: str) -> tuple[str, int]:
    text = value
    count = 0
    for pattern, replacement in (
        (_EMAIL, "[REDACTED_EMAIL]"),
        (_PHONE, "[REDACTED_PHONE]"),
        (_SECRET, "[REDACTED_SECRET_REFERENCE]"),
    ):
        text, substitutions = pattern.subn(replacement, text)
        count += substitutions
    return text, count


def redact_value(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        redacted: list[Any] = []
        count = 0
        for item in value:
            clean, substitutions = redact_value(item)
            redacted.append(clean)
            count += substitutions
        return redacted, count
    if isinstance(value, dict):
        redacted_dict: dict[str, Any] = {}
        count = 0
        for key, item in value.items():
            clean, substitutions = redact_value(item)
            redacted_dict[key] = clean
            count += substitutions
        return redacted_dict, count
    return value, 0


def safe_source_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
