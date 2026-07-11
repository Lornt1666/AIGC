from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class LifecycleDecision:
    passed: bool
    reason_codes: tuple[str, ...]


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def validate_amendment(record: dict[str, Any]) -> LifecycleDecision:
    reasons: list[str] = []
    if record.get("constitution_id") != "AEC-001":
        reasons.append("INVALID_CONSTITUTION_ID")
    if record.get("from_version") == record.get("to_version"):
        reasons.append("VERSION_NOT_INCREMENTED")
    if not record.get("affected_articles"):
        reasons.append("NO_AFFECTED_ARTICLES")
    for field in ("rationale", "risk_analysis", "compatibility_assessment", "migration_plan", "rollback_plan", "exact_revision"):
        if record.get(field) in (None, "", [], {}):
            reasons.append(f"MISSING_{field.upper()}")
    if record.get("status") == "approved":
        if record.get("review_path") not in {"independent_human_review", "constitutional_council_review"}:
            reasons.append("INVALID_APPROVAL_REVIEW_PATH")
        if record.get("operator_ratification") is not True:
            reasons.append("MISSING_OPERATOR_RATIFICATION")
    return LifecycleDecision(not reasons, tuple(sorted(set(reasons))))


def validate_waiver(record: dict[str, Any], *, now: datetime | None = None) -> LifecycleDecision:
    reasons: list[str] = []
    now = now or datetime.now(timezone.utc)
    if not record.get("article_ids"):
        reasons.append("NO_ARTICLES")
    if record.get("revocable") is not True:
        reasons.append("WAIVER_NOT_REVOCABLE")
    for field in ("scope", "owner", "risk_statement", "mitigations", "issued_at", "expires_at", "approval_reference", "exact_revision"):
        if record.get(field) in (None, "", [], {}):
            reasons.append(f"MISSING_{field.upper()}")
    try:
        issued_at = _parse_time(str(record.get("issued_at")))
        expires_at = _parse_time(str(record.get("expires_at")))
        if expires_at <= issued_at:
            reasons.append("INVALID_EXPIRY_ORDER")
        if record.get("status") == "active" and expires_at <= now:
            reasons.append("ACTIVE_WAIVER_EXPIRED")
    except (TypeError, ValueError):
        reasons.append("INVALID_WAIVER_TIME")
    return LifecycleDecision(not reasons, tuple(sorted(set(reasons))))


def validate_governance_registry(registry: dict[str, Any]) -> LifecycleDecision:
    reasons: list[str] = []
    if registry.get("registry_id") != "AIGC-GOVERNANCE-REGISTRY-001":
        reasons.append("INVALID_REGISTRY_ID")
    expected_order = ["constitution", "charter", "standard", "policy", "procedure", "control", "implementation"]
    if registry.get("authority_order") != expected_order:
        reasons.append("INVALID_AUTHORITY_ORDER")
    if registry.get("external_action_performed") is not False:
        reasons.append("EXTERNAL_ACTION_FLAG_INVALID")
    artifacts = registry.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        reasons.append("MISSING_GOVERNANCE_ARTIFACTS")
    else:
        ids = [item.get("artifact_id") for item in artifacts if isinstance(item, dict)]
        if len(ids) != len(set(ids)):
            reasons.append("DUPLICATE_GOVERNANCE_ARTIFACT")
        if "AEC-001" not in ids:
            reasons.append("CONSTITUTION_NOT_REGISTERED")
    return LifecycleDecision(not reasons, tuple(sorted(set(reasons))))
