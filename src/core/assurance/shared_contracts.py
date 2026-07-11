from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CONTRACT_TYPES = {
    "actor_reference",
    "artifact_reference",
    "evidence_reference",
    "decision",
    "approval_reference",
    "gate_receipt",
    "traceability_manifest",
    "finding",
    "observation",
}

REQUIRED_FIELDS = {
    "actor_reference": {"actor_id", "actor_type", "display_name", "authority_source"},
    "artifact_reference": {"artifact_id", "artifact_type", "revision", "location"},
    "evidence_reference": {"evidence_id", "evidence_class", "revision", "location", "maturity"},
    "decision": {"decision_id", "decision_type", "result", "reason_codes", "revision"},
    "approval_reference": {"approval_id", "actor_id", "approval_class", "revision", "status"},
    "gate_receipt": {"receipt_id", "gate_id", "revision", "result", "reason_codes", "evidence_ids"},
    "traceability_manifest": {"manifest_id", "revision", "constitutional_articles", "artifact_ids", "evidence_ids", "rollback_boundary"},
    "finding": {"finding_id", "domain", "revision", "severity", "confidence", "blocking", "state"},
    "observation": {"observation_id", "sensor_id", "revision", "signal", "health_state"},
}


@dataclass(frozen=True)
class SharedContractResult:
    passed: bool
    reason_codes: tuple[str, ...]
    details: tuple[str, ...]


class SharedContractValidator:
    """Deterministic, fail-closed validation for EIAP shared contract envelopes."""

    def validate(self, envelope: dict[str, Any]) -> SharedContractResult:
        reasons: list[str] = []
        details: list[str] = []

        if envelope.get("contract_version") != "1.0.0":
            reasons.append("INVALID_CONTRACT_VERSION")

        contract_type = envelope.get("contract_type")
        if contract_type not in CONTRACT_TYPES:
            reasons.append("UNKNOWN_CONTRACT_TYPE")
            details.append(str(contract_type))
            return SharedContractResult(False, tuple(reasons), tuple(details))

        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            reasons.append("INVALID_PAYLOAD")
            return SharedContractResult(False, tuple(reasons), tuple(details))

        missing = sorted(REQUIRED_FIELDS[contract_type] - payload.keys())
        if missing:
            reasons.append("MISSING_REQUIRED_FIELDS")
            details.extend(missing)

        revision = payload.get("revision")
        if revision is not None and (not isinstance(revision, str) or len(revision) < 7):
            reasons.append("INVALID_REVISION")

        if contract_type == "finding":
            confidence = payload.get("confidence")
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                reasons.append("INVALID_CONFIDENCE")

        if contract_type == "traceability_manifest":
            articles = payload.get("constitutional_articles")
            if not isinstance(articles, list) or not articles:
                reasons.append("MISSING_CONSTITUTIONAL_TRACEABILITY")
            if not str(payload.get("rollback_boundary", "")).strip():
                reasons.append("MISSING_ROLLBACK_BOUNDARY")

        if contract_type == "approval_reference":
            if payload.get("approval_class") == "independent_human_review" and payload.get("actor_id") in {"", None}:
                reasons.append("MISSING_INDEPENDENT_REVIEWER_IDENTITY")

        return SharedContractResult(not reasons, tuple(reasons), tuple(details))
