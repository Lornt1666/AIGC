from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from src.domain.repositories import StoredRecord


class QuestConductorError(RuntimeError): pass
class AgentRegistryError(QuestConductorError): pass
class AgentHandoffNotFound(QuestConductorError): pass
class AgentHandoffConflict(QuestConductorError): pass
class ReviewEvidenceConflict(QuestConductorError): pass


@dataclass(frozen=True)
class ReviewEvidenceResult:
    handoff: StoredRecord
    packet: StoredRecord


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return sha256(text.encode("utf-8")).hexdigest()


def record_review_evidence(
    service: Any,
    handoff_id: str,
    *,
    expected_handoff_revision: int,
    reviewer_agent_id: str,
    verdict: str,
    findings: Sequence[Mapping[str, Any]],
    acceptance_criteria_results: Sequence[Mapping[str, Any]],
    evidence_ids: Sequence[str],
    operator_role: str,
) -> ReviewEvidenceResult:
    service._operator(operator_role)
    verdict = str(verdict).strip().upper()
    statuses = {"PASS": "COMPLETED", "REWORK_REQUIRED": "REWORK_REQUIRED", "BLOCKED": "BLOCKED"}
    reviewer = service.agents.get(reviewer_agent_id)
    if verdict not in statuses:
        raise ValueError("invalid review verdict")
    if not reviewer or not reviewer["active"] or "review_handoff" not in reviewer["allowed_actions"]:
        raise AgentRegistryError("reviewer is not authorized")
    handoff = service.handoff_repository.get(handoff_id)
    if handoff is None:
        raise AgentHandoffNotFound(handoff_id)

    normalized_findings = _findings(findings)
    normalized_results = _results(acceptance_criteria_results)
    if verdict == "PASS" and (
        any(item["severity"] == "BLOCKING" for item in normalized_findings)
        or any(item["status"] != "PASS" for item in normalized_results)
    ):
        raise ValueError("PASS requires complete non-blocking evidence")

    logical = {
        "schema_version": "1.0.0",
        "evidence_subject": "INTERNAL_HANDOFF_REVIEW",
        "quest_id": handoff.payload["quest_id"],
        "quest_revision": handoff.payload["quest_revision"],
        "handoff_id": handoff_id,
        "handoff_revision": expected_handoff_revision,
        "reviewer_agent_id": reviewer_agent_id,
        "subject_agent_id": handoff.payload["to_agent_id"],
        "verdict": verdict,
        "findings": normalized_findings,
        "acceptance_criteria_results": normalized_results,
        "evidence_ids": sorted({str(value).strip() for value in evidence_ids if str(value).strip()}),
        "exact_revision": service.exact_revision,
        "authority_class": "ACCOUNTABLE_OPERATOR",
        "operator_review_required": True,
        "external_action_performed": False,
    }
    packet_digest = digest(logical)
    packet_id = f"review_{packet_digest[:24]}"
    linked = list(handoff.payload.get("review_packet_ids") or [])
    packet = service.review_repository.get(packet_id)
    if packet and packet_id in linked and handoff.revision == expected_handoff_revision + 1:
        return ReviewEvidenceResult(handoff, packet)
    if handoff.revision != expected_handoff_revision:
        raise AgentHandoffConflict("Handoff revision changed")
    if packet and packet.payload.get("packet_digest") != packet_digest:
        raise ReviewEvidenceConflict("review packet identity collision")
    if packet is None:
        packet_payload = {
            "packet_id": packet_id,
            **logical,
            "packet_digest": packet_digest,
            "created_at": now(),
        }
        service.review_validator.validate(packet_payload)
        packet = service.review_repository.put(
            packet_id, packet_payload, expected_revision=0, idempotency_key=packet_id
        )

    if packet_id not in linked:
        linked.append(packet_id)
    updated = dict(handoff.payload)
    updated.update({
        "status": statuses[verdict],
        "completed_at": now() if verdict == "PASS" else None,
        "review_packet_ids": linked,
        "last_review_verdict": verdict,
        "external_action_performed": False,
    })
    service.handoff_validator.validate(updated)
    handoff = service.handoff_repository.put(
        handoff_id,
        updated,
        expected_revision=expected_handoff_revision,
        idempotency_key=f"handoff-review:{packet_id}",
    )
    service._audit("quest_conductor.review_evidence_recorded", {
        "handoff_id": handoff_id,
        "handoff_resulting_revision": handoff.revision,
        "packet_id": packet_id,
        "verdict": verdict,
        "exact_revision": service.exact_revision,
    })
    return ReviewEvidenceResult(handoff, packet)


def _findings(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, value in enumerate(values, start=1):
        severity = str(value.get("severity") or "").strip().upper()
        code = str(value.get("code") or "").strip()
        message = str(value.get("message") or "").strip()
        if severity not in {"ADVISORY", "BLOCKING"} or not code or not message:
            raise ValueError("invalid review finding")
        evidence = sorted({
            str(item).strip()
            for item in value.get("evidence_ids") or []
            if str(item).strip()
        })
        material = {
            "index": index, "severity": severity, "code": code,
            "message": message, "evidence_ids": evidence,
        }
        result.append({
            "finding_id": f"finding_{digest(material)[:16]}",
            "severity": severity,
            "code": code,
            "message": message,
            "evidence_ids": evidence,
        })
    return result


def _results(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for value in values:
        criterion = str(value.get("criterion") or "").strip()
        status = str(value.get("status") or "").strip().upper()
        if not criterion or status not in {"PASS", "FAIL", "NOT_EVALUATED"}:
            raise ValueError("invalid acceptance criterion result")
        result.append({
            "criterion": criterion,
            "status": status,
            "evidence_ids": sorted({
                str(item).strip()
                for item in value.get("evidence_ids") or []
                if str(item).strip()
            }),
        })
    if not result:
        raise ValueError("at least one acceptance criterion result is required")
    return result
