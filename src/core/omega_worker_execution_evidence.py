from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .omega_worker_execution import ExecutionResult


@dataclass(frozen=True)
class ExecutionEvidence:
    """Evidence emitted after controlled execution; it does not prove external acceptance."""

    record_version: str
    evidence_id: str
    timestamp: str
    event: str
    subject: str
    claims: tuple[str, ...]
    artifacts: tuple[str, ...]
    verification_status: str
    verification_method: tuple[str, ...]
    external_action_performed: bool

    def to_record(self) -> dict:
        return {
            "record_version": self.record_version,
            "evidence_id": self.evidence_id,
            "timestamp": self.timestamp,
            "event": self.event,
            "subject": self.subject,
            "claims": list(self.claims),
            "artifacts": list(self.artifacts),
            "verification": {
                "status": self.verification_status,
                "method": list(self.verification_method),
            },
            "external_action_performed": self.external_action_performed,
        }


def record_execution(
    result: ExecutionResult,
    *,
    subject: str,
    artifacts: Iterable[str] = (),
    external_action_performed: bool = False,
) -> ExecutionEvidence:
    """Create schema-shaped evidence without upgrading execution into verified success."""
    now = datetime.now(timezone.utc).isoformat()
    return ExecutionEvidence(
        record_version="AIGC-OMEGA-EVIDENCE-0.1",
        evidence_id=f"exec:{result.permit_id}:{result.action}",
        timestamp=now,
        event=result.action,
        subject=subject,
        claims=(
            f"Execution permit {result.permit_id} was accepted for action {result.action}.",
            "Callable completion is not equivalent to external acceptance or payment.",
        ),
        artifacts=tuple(artifacts),
        verification_status="UNVERIFIED",
        verification_method=("execution-boundary-result",),
        external_action_performed=external_action_performed,
    )
