from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.core.contract_validator import validate_artifact, validate_file


SCHEMA_NAME = "observer_authority_verification"


class ObserverAuthorityVerificationError(ValueError):
    """Raised when observer authority evidence is unsafe or incomplete."""


def load_policy(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ObserverAuthorityVerificationError(f"Expected JSON object policy at {path}")
    validate_policy(payload)
    return payload


def validate_policy(policy: Dict[str, Any]) -> None:
    checks = dict(policy.get("required_checks", {}))
    required_true = [
        "identity_proof_required",
        "organization_or_platform_link_required",
        "role_authority_required",
        "project_scope_required",
        "counterparty_request_link_required",
        "operator_approval_required",
        "redaction_review_required",
        "expiry_required",
        "revocation_required",
        "audit_receipt_required",
    ]
    for key in required_true:
        if checks.get(key) is not True:
            raise ObserverAuthorityVerificationError(f"required_checks.{key} must be true")
    hard_blocks = set(policy.get("hard_blocks", []))
    required_blocks = {
        "whole_account_access",
        "backend_access",
        "raw_chatlog_access_by_default",
        "unrelated_project_access",
        "silent_sharing",
        "unverified_identity",
        "unverified_role_authority",
        "expired_authority",
        "unrevocable_access",
    }
    missing = sorted(required_blocks - hard_blocks)
    if missing:
        raise ObserverAuthorityVerificationError(f"Missing hard blocks: {missing}")


def build_authority_verification(
    policy: Dict[str, Any],
    *,
    observer: Dict[str, Any],
    authority_basis: Dict[str, Any],
    scope: Dict[str, Any],
) -> Dict[str, Any]:
    validate_policy(policy)
    findings = evaluate_findings(observer, authority_basis, scope)
    decision_state = decide(findings, authority_basis, scope)
    proceed_enabled = decision_state in {"ready_for_operator_review", "ready_for_operator_review_high_risk"}
    high_risk = decision_state == "ready_for_operator_review_high_risk"

    packet = {
        "verification_id": make_id("AIGC-OBS-AUTH", observer.get("email", ""), scope.get("chatlog_artifact_id", ""), utc_now()),
        "created_at": utc_now(),
        "observer": {
            "name": observer.get("name", ""),
            "organization": observer.get("organization", ""),
            "email": observer.get("email", ""),
            "observer_type": observer.get("observer_type", "employer_or_client"),
        },
        "authority_basis": {
            "identity_verified": bool(authority_basis.get("identity_verified")),
            "organization_or_platform_link_verified": bool(authority_basis.get("organization_or_platform_link_verified")),
            "role_authority_verified": bool(authority_basis.get("role_authority_verified")),
            "counterparty_request_linked": bool(authority_basis.get("counterparty_request_linked")),
            "documented_basis": authority_basis.get("documented_basis", ""),
            "basis_reference": authority_basis.get("basis_reference", ""),
            "review_notes": authority_basis.get("review_notes", ""),
        },
        "scope": {
            "chatlog_artifact_id": scope.get("chatlog_artifact_id", ""),
            "project_id": scope.get("project_id", ""),
            "allowed_sections": list(scope.get("allowed_sections", [])),
            "expires_at": scope.get("expires_at", ""),
            "revocable": bool(scope.get("revocable", False)),
            "read_only": bool(scope.get("read_only", True)),
            "whole_account_access": bool(scope.get("whole_account_access", False)),
            "backend_access": bool(scope.get("backend_access", False)),
            "raw_chatlog_access": bool(scope.get("raw_chatlog_access", False)),
        },
        "decision": {
            "state": decision_state,
            "proceed_enabled": proceed_enabled,
            "high_risk": high_risk,
            "findings": findings,
            "operator_review_required": True,
            "external_invite_sent": False,
        },
        "controls": {
            "least_privilege": True,
            "deny_by_default": True,
            "specific_chatlog_only": True,
            "redaction_review_required": True,
            "scope_hash": make_scope_hash(scope),
            "no_backend_access": not bool(scope.get("backend_access", False)),
            "no_whole_account_access": not bool(scope.get("whole_account_access", False)),
            "revocation_required": True,
            "expiry_required": True,
        },
        "audit": {
            "audit_receipt_required": True,
            "evidence_export_only": True,
            "minimum_necessary": True,
            "silent_sharing_allowed": False,
        },
    }
    validate_artifact(SCHEMA_NAME, packet)
    return packet


def evaluate_findings(observer: Dict[str, Any], authority_basis: Dict[str, Any], scope: Dict[str, Any]) -> List[str]:
    findings: List[str] = []
    if not observer.get("name") or not observer.get("email"):
        findings.append("missing_observer_identity")
    if not authority_basis.get("identity_verified"):
        findings.append("unverified_identity")
    if not authority_basis.get("organization_or_platform_link_verified"):
        findings.append("unverified_organization_or_platform_link")
    if not authority_basis.get("role_authority_verified"):
        findings.append("unverified_role_authority")
    if not authority_basis.get("counterparty_request_linked"):
        findings.append("missing_counterparty_request_link")
    if not scope.get("chatlog_artifact_id") or not scope.get("project_id"):
        findings.append("missing_specific_scope")
    if not list(scope.get("allowed_sections", [])):
        findings.append("missing_allowed_sections")
    if not scope.get("expires_at"):
        findings.append("missing_expiry")
    if scope.get("revocable") is not True:
        findings.append("unrevocable_access")
    if scope.get("read_only") is not True:
        findings.append("non_read_only_scope")
    if scope.get("whole_account_access"):
        findings.append("whole_account_access_requested")
    if scope.get("backend_access"):
        findings.append("backend_access_requested")
    if scope.get("raw_chatlog_access"):
        findings.append("raw_chatlog_access_requested")
    return findings


def decide(findings: Iterable[str], authority_basis: Dict[str, Any], scope: Dict[str, Any]) -> str:
    finding_set = set(findings)
    hard_overreach = {
        "whole_account_access_requested",
        "backend_access_requested",
        "raw_chatlog_access_requested",
        "unrevocable_access",
    }
    if finding_set & hard_overreach:
        return "blocked_scope_overreach"
    missing_authority = {
        "missing_observer_identity",
        "unverified_identity",
        "unverified_organization_or_platform_link",
        "unverified_role_authority",
        "missing_counterparty_request_link",
        "missing_specific_scope",
        "missing_allowed_sections",
        "missing_expiry",
    }
    if finding_set & missing_authority:
        return "insufficient_authority"
    observer_type = str(authority_basis.get("observer_type", "") or "")
    high_risk_basis = authority_basis.get("high_risk", False) or str(scope.get("risk_class", "")).lower() in {"high", "critical"}
    return "ready_for_operator_review_high_risk" if high_risk_basis else "ready_for_operator_review"


def run_observer_authority_verification(
    project_root: Path,
    policy_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    root = project_root.resolve()
    policy_path = policy_path or root / "config" / "observer_authority_verification.json"
    artifact_root = artifact_root or root / "reports" / "artifacts" / "observer_authority"
    policy = load_policy(policy_path)
    packet = build_authority_verification(
        policy,
        observer={
            "name": "Example Employer",
            "organization": "Example Org",
            "email": "employer@example.com",
            "observer_type": "employer_or_client",
        },
        authority_basis={
            "identity_verified": True,
            "organization_or_platform_link_verified": True,
            "role_authority_verified": True,
            "counterparty_request_linked": True,
            "documented_basis": "Example platform/client project record reviewed by operator.",
            "basis_reference": "REQ-EXAMPLE-001",
            "review_notes": "Example packet only; no invite sent.",
        },
        scope={
            "chatlog_artifact_id": "AIGC-CHATLOG-EXAMPLE-001",
            "project_id": "REQ-EXAMPLE-001",
            "allowed_sections": ["counterparty_request_summary", "approved_deliverables", "approved_status_updates"],
            "expires_at": "2099-01-01T00:00:00Z",
            "revocable": True,
            "read_only": True,
            "whole_account_access": False,
            "backend_access": False,
            "raw_chatlog_access": False,
        },
    )
    output_root = artifact_root / safe_path_name(packet["verification_id"])
    output_root.mkdir(parents=True, exist_ok=True)
    packet_path = output_root / "observer_authority_verification.json"
    report_path = output_root / "observer_authority_verification.md"
    write_json(packet_path, packet)
    validate_file(SCHEMA_NAME, packet_path)
    report_path.write_text(render_report(packet), encoding="utf-8")
    return {
        "packet": packet,
        "packet_path": relative_to_root(root, packet_path),
        "report_path": relative_to_root(root, report_path),
        "external_invite_sent": False,
    }


def render_report(packet: Dict[str, Any]) -> str:
    return "\n".join([
        "# AIGC Observer Authority Verification",
        "",
        f"Verification ID: {packet['verification_id']}",
        f"Decision: {packet['decision']['state']}",
        f"Observer: {packet['observer'].get('name', '')} <{packet['observer'].get('email', '')}>",
        f"Project Scope: {packet['scope'].get('project_id', '')}",
        f"Chat-log Artifact: {packet['scope'].get('chatlog_artifact_id', '')}",
        "External Invite Sent: No",
        "",
        "## Authority Evidence",
        f"- Identity verified: {packet['authority_basis']['identity_verified']}",
        f"- Organization/platform link verified: {packet['authority_basis']['organization_or_platform_link_verified']}",
        f"- Role authority verified: {packet['authority_basis']['role_authority_verified']}",
        f"- Counterparty request linked: {packet['authority_basis']['counterparty_request_linked']}",
        "",
        "## Scope Boundary",
        "- Specific chat-log artifact only.",
        "- Read-only observer packet only.",
        "- No whole-account access.",
        "- No backend access.",
        "- Revocable and time-bounded.",
    ]) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative_to_root(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def safe_path_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in str(value))[:96]


def make_scope_hash(scope: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(scope, sort_keys=True).encode("utf-8")).hexdigest()


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
