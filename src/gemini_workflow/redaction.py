from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d .()_-]{7,}\d)(?!\d)")
_PEM = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"
    r".*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)",
    re.IGNORECASE | re.DOTALL,
)
_BEARER = re.compile(
    r"(?i)\b(?:authorization\s*[:=]\s*)?bearer\s+"
    r"[A-Za-z0-9._~+/=-]{8,}"
)
_JWT = re.compile(
    r"\beyJ[A-Za-z0-9_-]{5,}\."
    r"[A-Za-z0-9_-]{5,}\."
    r"[A-Za-z0-9_-]{5,}\b"
)
_KNOWN_TOKEN = re.compile(
    r"\b(?:"
    r"sk-[A-Za-z0-9_-]{12,}|"
    r"(?:AKIA|ASIA)[0-9A-Z]{16}|"
    r"ghp_[A-Za-z0-9_]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"glpat-[A-Za-z0-9_-]{20,}|"
    r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}|"
    r"AIza[0-9A-Za-z_-]{20,}|"
    r"ya29\.[0-9A-Za-z_-]{12,}|"
    r"xox[bp]-[A-Za-z0-9-]{12,}|"
    r"SK[0-9a-fA-F]{32}"
    r")\b"
)
_SECRET = re.compile(
    r"(?i)\b(api[_ -]?key|authorization|bearer|password|secret|token)\b"
    r"\s*[:=]\s*[^\s,;]{6,}"
)


def redact_text(value: str) -> tuple[str, int]:
    text = value
    count = 0
    for pattern, replacement in (
        (_PEM, "[REDACTED_PRIVATE_KEY]"),
        (_BEARER, "[REDACTED_BEARER_TOKEN]"),
        (_JWT, "[REDACTED_JWT]"),
        (_KNOWN_TOKEN, "[REDACTED_PROVIDER_TOKEN]"),
        (_EMAIL, "[REDACTED_EMAIL]"),
        (_PHONE, "[REDACTED_PHONE]"),
        (_SECRET, "[REDACTED_SECRET_REFERENCE]"),
    ):
        text, substitutions = pattern.subn(replacement, text)
        count += substitutions
    return text, count


def contains_secret_material(value: str) -> bool:
    return any(
        pattern.search(value or "")
        for pattern in (_PEM, _BEARER, _JWT, _KNOWN_TOKEN, _SECRET)
    )


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
    if parts.username or parts.password:
        raise ValueError("source_url must not contain user credentials")
    hostname = parts.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, "", "", ""))
