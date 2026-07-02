from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class IncidentReport:
    incident_id: str
    created_at: str
    incident_type: str
    severity: str
    status: str
    summary: str
    containment_steps: List[str]
    recovery_steps: List[str]
    evidence: Dict[str, Any] = field(default_factory=dict)
    external_action_performed: bool = False


class IncidentResponseLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create_report(
        self,
        incident_type: str,
        severity: str,
        summary: str,
        evidence: Dict[str, Any] | None = None,
    ) -> IncidentReport:
        report = IncidentReport(
            incident_id=f"AIGC-INCIDENT-{uuid.uuid4()}",
            created_at=datetime.now(timezone.utc).isoformat(),
            incident_type=incident_type,
            severity=severity,
            status="open_internal_review",
            summary=summary,
            containment_steps=default_containment_steps(incident_type),
            recovery_steps=default_recovery_steps(incident_type),
            evidence=evidence or {},
            external_action_performed=False,
        )
        self.append(report)
        return report

    def append(self, report: IncidentReport) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(report), ensure_ascii=False) + "\n")

    def list_reports(self) -> List[IncidentReport]:
        if not self.path.exists():
            return []
        reports: List[IncidentReport] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                reports.append(IncidentReport(
                    incident_id=payload["incident_id"],
                    created_at=payload["created_at"],
                    incident_type=payload["incident_type"],
                    severity=payload["severity"],
                    status=payload["status"],
                    summary=payload["summary"],
                    containment_steps=payload.get("containment_steps", []),
                    recovery_steps=payload.get("recovery_steps", []),
                    evidence=payload.get("evidence", {}),
                    external_action_performed=bool(payload.get("external_action_performed", False)),
                ))
        return reports


def default_containment_steps(incident_type: str) -> List[str]:
    common = [
        "Enable emergency stop if external execution risk exists.",
        "Preserve logs and do not rewrite history.",
        "Block related external action until review is complete.",
    ]
    if incident_type == "secret_leak_suspicion":
        return common + [
            "Run secret scanner on affected paths.",
            "Rotate affected credentials through the provider if leak is confirmed.",
            "Verify no secret value appears in audit logs, prompts, or reports.",
        ]
    if incident_type == "wrong_recipient":
        return common + [
            "Identify the approved recipient and actual recipient mismatch.",
            "Prevent further sends for the action ID.",
        ]
    if incident_type == "prompt_injection":
        return common + [
            "Quarantine the source text or listing.",
            "Treat source instructions as untrusted input.",
        ]
    if incident_type == "payment_dispute":
        return common + [
            "Freeze related finance ledger updates until reviewed.",
            "Collect contract, invoice, and delivery evidence internally.",
        ]
    if incident_type == "approval_bypass_attempt":
        return common + [
            "Verify authorization packet history.",
            "Check runtime events for rejected or malformed approval phrases.",
        ]
    return common


def default_recovery_steps(incident_type: str) -> List[str]:
    common = [
        "Write postmortem.",
        "Create an evolution patch proposal if process changes are needed.",
        "Require operator approval before resuming related external actions.",
    ]
    if incident_type == "secret_leak_suspicion":
        return [
            "Confirm affected credential scope.",
            "Rotate or revoke affected secret.",
            "Update secret manifest references if provider resource changed.",
        ] + common
    return common
