from __future__ import annotations

import uuid
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    clean_prefix = prefix.strip().upper().replace(" ", "-")
    return f"{clean_prefix}-{uuid.uuid4()}"
