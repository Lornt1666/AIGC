"""Deterministic, fail-closed governance policy for AIGC.

This module is a policy decision point, not an identity provider, signature verifier,
execution controller, or release authority. Callers must independently authenticate
evidence and enforce the returned decision before any side effect.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

POLICY_VERSION = "aigc-governor-policy/1.0.0"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
DECISIONS = {"ALLOW_SCOPED", "REVIEW_REQUIRED", "BLOCK"}
HUMAN_GATED_ACTIONS = {
    "deploy", "release", "publish_external", "send_external_message",
    "spend", "delete", "modify_production", "change_permissions",
    "manage_secrets", "change_governance_policy",
}
HIGH_RISK_CATEGORIES = {
    "security", "privacy", "legal", "financial", "safety", "rights_affecting",
    "production", "external_communication", "release", "destructive",
}
REQUIRED_FIELDS = {
    "request_id", "task_id", "source_sha", "task_digest", "action_ids",
    "risk_tier", "requested_capabilities", "policy_version", "expires_at",
    "evidence", "human_approval",
}
EVIDENCE_FIELDS = {"id", "sha256", "source_sha", "authenticated", "issuer", "purpose"}


def canonical_json(value: Any) -> str:
    """Stable JSON encoding used for local content digests."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    """SHA-256 of canonical JSON; not a digital signature."""
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def evaluate_governance(request: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Evaluate a proposed agent action. Missing, stale, ambiguous, or mismatched proof blocks.

    The evidence.authenticated field is an upstream verifier result, not something this
    function can establish. The execution controller must independently revalidate it.
    """
    reasons: list[str] = []
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(request, Mapping):
        return _decision("BLOCK", ["request_not_an_object"], None, [])

    missing = REQUIRED_FIELDS - set(request.keys())
    unknown = set(request.keys()) - REQUIRED_FIELDS
    if missing:
        reasons.append("missing_fields:" + ",".join(sorted(missing)))
    if unknown:
        reasons.append("unknown_fields:" + ",".join(sorted(unknown)))

    source_sha = request.get("source_sha")
    if not isinstance(source_sha, str) or not FULL_SHA.fullmatch(source_sha):
        reasons.append("invalid_source_sha")

    task_digest = request.get("task_digest")
    if not isinstance(task_digest, str) or not HEX_DIGEST.fullmatch(task_digest):
        reasons.append("invalid_task_digest")

    if request.get("policy_version") != POLICY_VERSION:
        reasons.append("policy_version_mismatch")

    expires_at = _utc(request.get("expires_at"))
    if expires_at is None:
        reasons.append("invalid_expiry")
    elif expires_at <= now_utc:
        reasons.append("expired_request")

    request_id = request.get("request_id")
    task_id = request.get("task_id")
    if not isinstance(request_id, str) or not request_id.strip():
        reasons.append("invalid_request_id")
    if not isinstance(task_id, str) or not task_id.strip():
        reasons.append("invalid_task_id")

    action_ids = request.get("action_ids")
    if not isinstance(action_ids, list) or not action_ids:
        reasons.append("action_ids_must_be_nonempty_list")
        action_ids = []
    elif any(not isinstance(a, str) or not a.strip() or a.strip() in {"*", "all", "any"} for a in action_ids):
        reasons.append("invalid_or_wildcard_action_id")
    elif len(set(action_ids)) != len(action_ids):
        reasons.append("duplicate_action_id")

    risk_tier = request.get("risk_tier")
    if risk_tier not in {"low", "moderate", "high", "critical", "unknown"}:
        reasons.append("invalid_risk_tier")
    elif risk_tier in {"critical", "unknown"}:
        reasons.append("risk_tier_not_permittable")

    capabilities = request.get("requested_capabilities")
    if not isinstance(capabilities, list) or any(not isinstance(x, str) or not x.strip() for x in capabilities):
        reasons.append("invalid_requested_capabilities")
        capabilities = []

    evidence = request.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        reasons.append("evidence_required")
        evidence = []
    else:
        for index, item in enumerate(evidence):
            prefix = f"evidence_{index}"
            if not isinstance(item, Mapping):
                reasons.append(prefix + "_not_object")
                continue
            missing_evidence = EVIDENCE_FIELDS - set(item.keys())
            if missing_evidence:
                reasons.append(prefix + "_missing_fields")
                continue
            if not isinstance(item.get("id"), str) or not item["id"].strip():
                reasons.append(prefix + "_invalid_id")
            if not isinstance(item.get("sha256"), str) or not HEX_DIGEST.fullmatch(item["sha256"]):
                reasons.append(prefix + "_invalid_digest")
            if item.get("source_sha") != source_sha:
                reasons.append(prefix + "_source_sha_mismatch")
            if item.get("authenticated") is not True:
                reasons.append(prefix + "_not_authenticated_by_upstream_verifier")
            if not isinstance(item.get("issuer"), str) or not item["issuer"].strip():
                reasons.append(prefix + "_invalid_issuer")
            if not isinstance(item.get("purpose"), str) or not item["purpose"].strip():
                reasons.append(prefix + "_invalid_purpose")

    human_approval = request.get("human_approval")
    if not isinstance(human_approval, Mapping):
        reasons.append("human_approval_object_required")
        human_approval = {}
    approval_required = (
        any(a in HUMAN_GATED_ACTIONS for a in action_ids)
        or any(c in HIGH_RISK_CATEGORIES for c in capabilities)
        or risk_tier in {"high", "critical", "unknown"}
    )
    if approval_required:
        if human_approval.get("approved") is not True:
            reasons.append("explicit_human_approval_required")
        if human_approval.get("request_digest") != digest({
            "request_id": request_id,
            "task_id": task_id,
            "source_sha": source_sha,
            "task_digest": task_digest,
            "action_ids": action_ids,
            "requested_capabilities": capabilities,
        }):
            reasons.append("human_approval_subject_mismatch")
        if not isinstance(human_approval.get("approver_id"), str) or not human_approval.get("approver_id", "").strip():
            reasons.append("human_approver_identity_required")
        if human_approval.get("authenticated") is not True:
            reasons.append("human_approval_not_authenticated")
    elif human_approval.get("approved") is True and human_approval.get("authenticated") is not True:
        reasons.append("claimed_human_approval_not_authenticated")

    if reasons:
        return _decision("BLOCK", sorted(set(reasons)), request_id if isinstance(request_id, str) else None, action_ids)

    # Governance only grants a narrowly scoped policy result for low/moderate risk.
    # A separate execution controller must recheck identity, authorization, state,
    # idempotency, limits, and subject digests before taking any action.
    decision = "REVIEW_REQUIRED" if risk_tier == "moderate" else "ALLOW_SCOPED"
    return _decision(decision, ["policy_checks_passed_execution_controller_revalidation_required"], request_id, action_ids)


def _decision(decision: str, reasons: list[str], request_id: str | None, action_ids: list[Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "policy_version": POLICY_VERSION,
        "request_id": request_id,
        "decision": decision,
        "reasons": reasons,
        "permitted_action_ids": action_ids if decision == "ALLOW_SCOPED" else [],
        "authority": "governance_policy_advisory",
        "release_decision_authority": False,
        "execution_controller_revalidation_required": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
