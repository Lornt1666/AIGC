from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from src.core.approval_gated_external_actions import load_policy as load_approval_policy
from src.core.contract_validator import validate_artifact, validate_file
from src.core.counterparty_request_intake import build_acceptance_review, validate_request_safety
from src.core.external_action_procedures import build_external_action_procedure_packet, load_controls
from src.core.observer_authority_verification import load_policy as load_observer_authority_policy
from src.core.observer_authority_verification import build_authority_verification


RECEIPT_SCHEMA = "security_privacy_wiring_receipt"
COUNTERPARTY_SCHEMA = "counterparty_request_packet"
OBSERVER_AUTHORITY_SCHEMA = "observer_authority_verification"

READY_COUNTERPARTY_STATES = {"ready_for_operator_popup", "ready_for_operator_popup_high_risk"}
READY_AUTHORITY_STATES = {"ready_for_operator_review", "ready_for_operator_review_high_risk"}


class SecurityPrivacyWiringError(ValueError):
    """Raised when the security/privacy wiring policy or request is malformed."""


def run_security_privacy_wiring(
    project_root: Path,
    request_path: Path | None = None,
    policy_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    root = project_root.resolve()
    request_path = resolve_project_path(root, request_path or root / "config" / "counterparty_request_example.json")
    policy_path = resolve_project_path(root, policy_path or root / "config" / "security_privacy_wiring_policy.json")
    artifact_root = resolve_project_path(root, artifact_root or root / "reports" / "artifacts" / "security_privacy_wiring")

    policy = load_json_object(policy_path)
    request = load_json_object(request_path)
    receipt = build_security_privacy_wiring_receipt(root, policy, request)

    output_root = artifact_root / safe_path_name(receipt["receipt_id"])
    output_root.mkdir(parents=True, exist_ok=True)
    receipt_path = output_root / "security_privacy_wiring_receipt.json"
    report_path = output_root / "security_privacy_wiring_report.md"
    write_json(receipt_path, receipt)
    validate_file(RECEIPT_SCHEMA, receipt_path)
    report_path.write_text(render_wiring_report(receipt), encoding="utf-8")

    return {
        "receipt": receipt,
        "receipt_path": relative_to_root(root, receipt_path),
        "report_path": relative_to_root(root, report_path),
        "external_action_performed": False,
    }


def build_security_privacy_wiring_receipt(project_root: Path, policy: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
    validate_policy(policy)
    requested_action = str(request.get("requested_action", "")).strip()
    request_id = str(request.get("request_id", "manual-request"))
    enabled_controls: List[str] = []
    disabled_controls: List[str] = []
    gate_results: Dict[str, Any] = {}
    artifact_paths: Dict[str, Any] = {}

    def block(reason: str, next_step: str) -> Dict[str, Any]:
        return finalize_receipt(
            request_id=request_id,
            requested_action=requested_action,
            decision_state="blocked",
            blocked_reason=reason,
            required_next_step=next_step,
            enabled_controls=enabled_controls,
            disabled_controls=disabled_controls,
            gate_results=gate_results,
            artifact_paths=artifact_paths,
            proceed_enabled=False,
        )

    hard_block_findings = hard_block_precheck(request, policy)
    gate_results["hard_block_precheck"] = {
        "passed": not hard_block_findings,
        "findings": hard_block_findings,
    }
    if hard_block_findings:
        disabled_controls.append("hard_block_precheck")
        return block("hard_block_precheck_failed: " + "; ".join(hard_block_findings), "Remove hard-blocked content or action before retrying.")
    enabled_controls.append("hard_block_precheck")

    counterparty_required = requires_counterparty_intake(requested_action, policy)
    if counterparty_required:
        try:
            validate_artifact(COUNTERPARTY_SCHEMA, request)
            validate_request_safety(request)
            counterparty_review = build_acceptance_review(request)
            gate_results["counterparty_request_intake"] = counterparty_review
        except Exception as exc:  # noqa: BLE001 - receipt must preserve failure reason
            disabled_controls.append("counterparty_request_intake")
            gate_results["counterparty_request_intake"] = {"passed": False, "error": str(exc)}
            return block("counterparty_request_intake_failed", "Provide a complete counterparty request packet before approval or execution.")
        if counterparty_review.get("decision_state") not in READY_COUNTERPARTY_STATES:
            disabled_controls.append("counterparty_request_intake")
            return block(
                f"counterparty_request_not_ready: {counterparty_review.get('decision_state', '')}",
                "Resolve missing information or risk flags in the counterparty request.",
            )
        enabled_controls.append("counterparty_request_intake")
    else:
        gate_results["counterparty_request_intake"] = {"required": False, "passed": True}
        enabled_controls.append("counterparty_request_intake_not_required")

    observer_required = requires_observer_authority(requested_action, request, policy)
    if observer_required:
        authority_payload = request.get("observer_authority_verification")
        if not isinstance(authority_payload, dict):
            disabled_controls.append("observer_authority_verification")
            gate_results["observer_authority_verification"] = {"passed": False, "error": "observer_authority_verification missing"}
            return block("observer_authority_verification_missing", "Verify observer identity, role, organization/platform linkage, scope, expiry, and revocation before sharing.")
        try:
            validate_artifact(OBSERVER_AUTHORITY_SCHEMA, authority_payload)
        except Exception as exc:  # noqa: BLE001
            disabled_controls.append("observer_authority_verification")
            gate_results["observer_authority_verification"] = {"passed": False, "error": str(exc)}
            return block("observer_authority_verification_invalid", "Provide a schema-valid observer authority verification packet.")
        if authority_payload.get("decision", {}).get("state") not in READY_AUTHORITY_STATES:
            disabled_controls.append("observer_authority_verification")
            gate_results["observer_authority_verification"] = authority_payload
            return block("observer_authority_not_ready", "Resolve authority findings before observer access or sharing.")
        gate_results["observer_authority_verification"] = authority_payload
        enabled_controls.append("observer_authority_verification")
    else:
        gate_results["observer_authority_verification"] = {"required": False, "passed": True}
        enabled_controls.append("observer_authority_not_required")

    privacy_result = privacy_redaction_review(request, requested_action, policy)
    gate_results["redaction_privacy_review"] = privacy_result
    if not privacy_result["passed"]:
        disabled_controls.append("redaction_privacy_review")
        return block("redaction_privacy_review_failed: " + "; ".join(privacy_result["findings"]), "Remove private data or complete explicit redaction review before sharing.")
    enabled_controls.append("redaction_privacy_review")

    sentinel_result = sentinel_policy_review(request, policy)
    gate_results["sentinel_policy_review"] = sentinel_result
    if not sentinel_result["passed"]:
        disabled_controls.append("sentinel_policy_review")
        return block("sentinel_policy_review_failed", "Resolve Sentinel policy findings before proceeding.")
    enabled_controls.append("sentinel_policy_review")

    if requires_external_action_procedure(requested_action, policy):
        try:
            approval_policy = load_approval_policy(project_root / "config" / "approval_gated_external_actions.json")
            procedure_controls = load_controls(project_root / "config" / "external_action_procedure_controls.json")
            procedure_packet = build_external_action_procedure_packet(
                approval_policy,
                procedure_controls,
                {
                    "action": requested_action,
                    "destination": request.get("destination", request.get("source", "manual-review")),
                    "payload": build_safe_payload_summary(request),
                    "risk_class": "high" if counterparty_required else "medium",
                    "platform_terms_status": request.get("platform_terms_status", "review_required"),
                    "cost_or_terms": request.get("terms", {}),
                    "rollback_or_correction_plan": request.get("rollback_or_correction_plan", "operator must define before proceeding"),
                },
            )
            gate_results["approval_gated_procedure_packet"] = procedure_packet
        except Exception as exc:  # noqa: BLE001
            disabled_controls.append("approval_gated_procedure_packet")
            gate_results["approval_gated_procedure_packet"] = {"passed": False, "error": str(exc)}
            return block("approval_gated_procedure_packet_failed", "Create a valid approval-gated procedure packet before external action review.")
        if procedure_packet.get("external_action_performed") is not False:
            disabled_controls.append("approval_gated_procedure_packet")
            return block("procedure_packet_external_action_violation", "Procedure packets must remain preparation-only.")
        enabled_controls.append("approval_gated_procedure_packet")
    else:
        gate_results["approval_gated_procedure_packet"] = {"required": False, "passed": True}
        enabled_controls.append("approval_gated_procedure_not_required")

    decision_state = "ready_for_operator_review_high_risk" if counterparty_required or observer_required else "ready_for_operator_review"
    return finalize_receipt(
        request_id=request_id,
        requested_action=requested_action,
        decision_state=decision_state,
        blocked_reason="",
        required_next_step="Show the Security & Privacy Gate receipt in the future cockpit tab and require operator review before any external threshold.",
        enabled_controls=enabled_controls,
        disabled_controls=disabled_controls,
        gate_results=gate_results,
        artifact_paths=artifact_paths,
        proceed_enabled=True,
    )


def finalize_receipt(
    *,
    request_id: str,
    requested_action: str,
    decision_state: str,
    blocked_reason: str,
    required_next_step: str,
    enabled_controls: List[str],
    disabled_controls: List[str],
    gate_results: Dict[str, Any],
    artifact_paths: Dict[str, Any],
    proceed_enabled: bool,
) -> Dict[str, Any]:
    receipt = {
        "receipt_id": make_id("AIGC-SECURITY-WIRING", request_id, requested_action, utc_now()),
        "created_at": utc_now(),
        "request_id": request_id,
        "requested_action": requested_action,
        "decision_state": decision_state,
        "blocked_reason": blocked_reason,
        "required_next_step": required_next_step,
        "enabled_controls": sorted(set(enabled_controls)),
        "disabled_controls": sorted(set(disabled_controls)),
        "gate_results": gate_results,
        "artifact_paths": artifact_paths,
        "operator_popup_required": True,
        "proceed_enabled": proceed_enabled,
        "external_action_performed": False,
    }
    validate_artifact(RECEIPT_SCHEMA, receipt)
    return receipt


def hard_block_precheck(request: Dict[str, Any], policy: Dict[str, Any]) -> List[str]:
    findings: List[str] = []
    if request.get("external_action_performed") is not False:
        findings.append("external_action_performed must be false")
    if request.get("self_approval") or request.get("self_approve"):
        findings.append("self_approval is hard-blocked")
    if request.get("whole_account_access"):
        findings.append("whole_account_access is hard-blocked")
    if request.get("backend_access"):
        findings.append("backend_access is hard-blocked")
    if request.get("raw_chatlog_access") or str(request.get("requested_action", "")).lower() == "share_raw_chatlog":
        findings.append("raw_chatlog_sharing is hard-blocked")
    blob = json.dumps(request, ensure_ascii=False).lower()
    hard_phrases = {
        "bypass platform rules": "platform_rule_bypass",
        "fabricate credential": "fabricated_credentials",
        "fake credential": "fabricated_credentials",
        "self approve": "self_approval",
        "secret without approval": "raw_secret",
    }
    for phrase, label in hard_phrases.items():
        if phrase in blob:
            findings.append(label)
    return findings


def requires_counterparty_intake(action: str, policy: Dict[str, Any]) -> bool:
    return action in set(policy.get("external_action_families", []))


def requires_observer_authority(action: str, request: Dict[str, Any], policy: Dict[str, Any]) -> bool:
    return bool(request.get("observer_access_requested")) or action in set(policy.get("observer_action_families", []))


def requires_sharing_review(action: str, policy: Dict[str, Any]) -> bool:
    return action in set(policy.get("sharing_action_families", []))


def requires_external_action_procedure(action: str, policy: Dict[str, Any]) -> bool:
    return action in set(policy.get("external_action_families", []))


def privacy_redaction_review(request: Dict[str, Any], action: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[str] = []
    blob = json.dumps(request, ensure_ascii=False).lower()
    for marker in policy.get("privacy_scan", {}).get("blocked_secret_markers", []):
        marker_text = str(marker).lower()
        if marker_text and marker_text in blob:
            findings.append(f"blocked private/secret marker detected: {marker}")
    explicit_required = bool(policy.get("privacy_scan", {}).get("explicit_redaction_review_required_for_sharing", True))
    if explicit_required and requires_sharing_review(action, policy):
        status = request.get("redaction_review", {}).get("status") if isinstance(request.get("redaction_review"), dict) else ""
        if status != "passed":
            findings.append("explicit redaction_review.status=passed is required before sharing")
    return {"passed": not findings, "findings": findings}


def sentinel_policy_review(request: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[str] = []
    controls = dict(policy.get("sentinel_controls", {}))
    if controls.get("deny_by_default") is not True:
        findings.append("sentinel deny_by_default must be true")
    if controls.get("external_action_performed_default") is not False:
        findings.append("external_action_performed_default must be false")
    if controls.get("operator_popup_required") is not True:
        findings.append("operator_popup_required must be true")
    return {"passed": not findings, "findings": findings}


def build_safe_payload_summary(request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "request_id": request.get("request_id", ""),
        "requested_action": request.get("requested_action", ""),
        "counterparty": request.get("counterparty", {}),
        "work_description": request.get("work_description", {}),
        "deliverables": request.get("deliverables", []),
        "acceptance_criteria": request.get("acceptance_criteria", []),
        "timeline": request.get("timeline", {}),
    }


def render_wiring_report(receipt: Dict[str, Any]) -> str:
    lines = [
        "# AIGC Security & Privacy Wiring Gate Receipt",
        "",
        f"Receipt ID: {receipt['receipt_id']}",
        f"Created At: {receipt['created_at']}",
        f"Request ID: {receipt['request_id']}",
        f"Requested Action: {receipt['requested_action']}",
        f"Decision State: {receipt['decision_state']}",
        f"Proceed Enabled: {receipt['proceed_enabled']}",
        "External Action Performed: No",
        "",
        "## Blocked Reason",
        receipt.get("blocked_reason") or "None",
        "",
        "## Required Next Step",
        receipt.get("required_next_step", ""),
        "",
        "## Enabled Controls",
    ]
    lines.extend(f"- {item}" for item in receipt.get("enabled_controls", []))
    lines.extend(["", "## Disabled Controls"])
    lines.extend(f"- {item}" for item in receipt.get("disabled_controls", []) or ["None"])
    lines.extend([
        "",
        "## Core Boundary",
        "This receipt is preparation-only. Live external execution remains blocked unless a future connector PR satisfies procedure packet, observer authority, redaction, approval, and audit gates.",
    ])
    return "\n".join(lines) + "\n"


def validate_policy(policy: Dict[str, Any]) -> None:
    required_order = [
        "hard_block_precheck",
        "counterparty_request_intake",
        "observer_authority_verification",
        "redaction_privacy_review",
        "sentinel_policy_review",
        "approval_gated_procedure_packet",
        "operator_popup_review",
        "audit_receipt",
    ]
    if policy.get("gate_order") != required_order:
        raise SecurityPrivacyWiringError("security_privacy_wiring_policy.gate_order does not match required order")
    controls = dict(policy.get("sentinel_controls", {}))
    if controls.get("deny_by_default") is not True:
        raise SecurityPrivacyWiringError("sentinel_controls.deny_by_default must be true")
    if controls.get("external_action_performed_default") is not False:
        raise SecurityPrivacyWiringError("sentinel_controls.external_action_performed_default must be false")


def load_json_object(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def relative_to_root(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def safe_path_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in str(value))[:96]


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
