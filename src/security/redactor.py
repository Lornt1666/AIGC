from __future__ import annotations

import re
from typing import List


class Redactor:
    SECRET_PATTERNS = [
        r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_\-]{10,}",
        r"AKIA[0-9A-Z]{16}",
        r"ghp_[A-Za-z0-9_]{20,}",
        r"glpat-[A-Za-z0-9_\-]{20,}",
        r"xox[baprs]-[A-Za-z0-9\-]+",
        r"-----BEGIN PRIVATE KEY-----.*?-----END PRIVATE KEY-----",
        r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+",
        r"(?i)(token\s*[:=]\s*)[^\s,;]+",
        r"(?i)(secret\s*[:=]\s*)[^\s,;]+",
        r"(?i)(password\s*[:=]\s*)[^\s,;]+",
        r"(?i)(authorization\s*:\s*)[^\n]+",
        r"(?i)(cookie\s*:\s*)[^\n]+",
    ]
    PRIVATE_DATA_PATTERNS = [
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b\d{16}\b",
    ]

    def redact_text(self, text: str) -> str:
        redacted = text or ""
        for pattern in self.SECRET_PATTERNS:
            redacted = re.sub(pattern, "[REDACTED_SECRET]", redacted, flags=re.DOTALL)
        for pattern in self.PRIVATE_DATA_PATTERNS:
            redacted = re.sub(pattern, "[REDACTED_PRIVATE_DATA]", redacted)
        return redacted

    def scan_for_secret_like_content(self, text: str) -> List[str]:
        value = text or ""
        return [
            pattern
            for pattern in self.SECRET_PATTERNS
            if re.search(pattern, value, flags=re.DOTALL)
        ]
