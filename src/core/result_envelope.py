from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass(frozen=True)
class ResultEnvelope:
    success: bool
    status: str
    phase: str
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    event_id: str = ""
    external_action_performed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json_ready(self) -> Dict[str, Any]:
        return self.to_dict()


def ok(phase: str, summary: str, data: Dict[str, Any] | None = None, event_id: str = "") -> ResultEnvelope:
    return ResultEnvelope(
        success=True,
        status="completed",
        phase=phase,
        summary=summary,
        data=data or {},
        event_id=event_id,
        external_action_performed=False,
    )


def blocked(phase: str, summary: str, errors: List[str] | None = None, event_id: str = "") -> ResultEnvelope:
    return ResultEnvelope(
        success=False,
        status="blocked",
        phase=phase,
        summary=summary,
        errors=errors or [],
        event_id=event_id,
        external_action_performed=False,
    )
