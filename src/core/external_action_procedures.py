from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.core.approval_gated_external_actions import build_review_popup_packet, load_policy
from src.core.contract_validator import validate_artifact, validate_file


CONTROLS_SCHEMA = "external_action_procedure_controls"
PROCEDURE_PACKET_SCHEMA = "external_action_procedure_packet"
HIGH_RISK_ACTIONS = {"accept", "pay", "purchase", "deploy", "bid", "deliver_work"}


class ExternalActionProcedureError(ValueError):
    """Raised when an external action procedure packet would violate governance."""


def load_controls(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExternalActionProcedureError(f"Expected object controls at {path}")
    validate_artifact(CONTROLS_SCHEMA, payload)
    validate_controls(payload)
    return payload


def validate_controls(controls: Dict[str, Any]) -> None:
    separation = dict(controls.get("separation_of_duties", {}))
    if separation.get("aigc_may_self_approve") is not False:
        raise ExternalActionProcedureError("aigc_may_self_approve must remain false.")
    if separation.get("operator_must_approve") is not True:
        raise ExternalActionProcedureError("operator_must_approve must remain true.")
    required_blocks = {
        "use_credentials_without_reviewed_integration",
        "bypass_platform_rules",
        "fabricate_credentials",
        "self_approve",
        "deliver_work_without_operator_review",
    }
    configured = {str(item) for item in controls.get("non_negotiable_blocks", [])}
    missing = sorted(required_blocks - configured)
    if missing:
        raise ExternalActionProcedureError(f"Missing non-negotiable blocks: {missing}")


def build_external_action_procedure_packet(
    approval_policy: Dict[str, Any],
    procedure_controls: Dict[str, Any],
    requested_action: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a professional procedure packet. This does not execute the action."""
    popup = build_review_popup_packet(approval_policy, requested_action)
    action = str(popup.get("action", ""))
    risk_class = str(popup.get("risk_class", "high"))
    hard_blocked = popup.get("status") in {"hard_blocked", "unknown_action_blocked"}
    high_risk = action in HIGH_RISK_ACTIONS or risk_class in {"high", "critical"}

    stages = list(procedure_controls.get("common_stages", []))
    if high_risk and not hard_blocked:
        stages = stages + matching_high_risk_stages(procedure_controls, action)

    status = "hard_blocked_procedure" if hard_blocked else "approval_gated_procedure_ready_for_operator_review"
    proceed_enabled = bool(popup.get("proceed_enabled", False)) and not hard_blocked

    packet = {
        "procedure_packet_id": make_id("AIGC-ACTION-PROCEDURE", action, popup.get("destination", ""), utc_now()),
        "created_at": utc_now(),
        "action": action,
        "status": status,
        "risk_class": risk_class,
        "operator_popup_required": True,
        "proceed_button_enabled": proceed_enabled,
        "external_action_performed": False,
        "popup_packet": popup,
        "procedure_stages": stages,
        "evidence_requirements": list(procedure_controls.get("evidence_requirements", [])),
        "audit_requirements": list(procedure_controls.get("audit_requirements", [])),
        "professional_controls": {
            "platform_terms_review_required": True,
            "truthfulness_review_required": True,
            "credential_review_required": True,
            "operator_review_required": True,
            "self_approval_allowed": False,
            "hard_blocked": hard_blocked,
        },
    }
    validate_artifact(PROCEDURE_PACKET_SCHEMA, packet)
    return packet


def run_external_action_procedure(
    project_root: Path,
    action: str,
    destination: str,
    payload: Dict[str, Any],
    risk_class: str = "high",
    platform_terms_status: str = "review_required",
    cost_or_terms: Dict[str, Any] | None = None,
    rollback_or_correction_plan: str = "operator must define before proceeding",
    policy_path: Path | None = None,
    controls_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    root = project_root.resolve()
    policy_path = policy_path or root / "config" / "approval_gated_external_actions.json"
    controls_path = controls_path or root / "config" / "external_action_procedure_controls.json"
    artifact_root = artifact_root or root / "reports" / "artifacts" / "external_action_procedures"

    approval_policy = load_policy(policy_path)
    procedure_controls = load_controls(controls_path)
    validate_file(CONTROLS_SCHEMA, controls_path)

    requested = {
        "action": action,
        "destination": destination,
        "payload": payload,
        "risk_class": risk_class,
        "platform_terms_status": platform_terms_status,
        "cost_or_terms": cost_or_terms or {},
        "rollback_or_correction_plan": rollback_or_correction_plan,
    }
    packet = build_external_action_procedure_packet(approval_policy, procedure_controls, requested)

    run_root = artifact_root / safe_path_name(packet["procedure_packet_id"])
    run_root.mkdir(parents=True, exist_ok=True)
    packet_path = run_root / "external_action_procedure_packet.json"
    report_path = run_root / "external_action_procedure_report.md"
    write_json(packet_path, packet)
    report_path.write_text(render_procedure_report(packet), encoding="utf-8")
    validate_file(PROCEDURE_PACKET_SCHEMA, packet_path)

    return {
        "procedure_packet": packet,
        "procedure_packet_path": relative_to_root(root, packet_path),
        "procedure_report_path": relative_to_root(root, report_path),
        "external_action_performed": False,
    }


def matching_high_risk_stages(controls: Dict[str, Any], action: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for stage in controls.get("high_risk_extra_stages", []):
        if not isinstance(stage, dict):
            continue
        applies_to = {str(item) for item in stage.get("applies_to", [])}
        if action in applies_to:
            matches.append(stage)
    return matches


def render_procedure_report(packet: Dict[str, Any]) -> str:
    lines = [
        "# AIGC External Action Procedure Packet",
        "",
        f"Generated At: {packet['created_at']}",
        f"Procedure Packet ID: {packet['procedure_packet_id']}",
        f"Action: {packet['action']}",
        f"Status: {packet['status']}",
        f"Risk Class: {packet['risk_class']}",
        f"Proceed Button Enabled: {packet['proceed_button_enabled']}",
        "External Action Performed: No",
        "",
        "## Procedure Stages",
    ]
    for stage in packet.get("procedure_stages", []):
        lines.extend([
            f"### {stage.get('name', stage.get('stage_id', 'stage'))}",
            f"- Stage ID: {stage.get('stage_id', '')}",
            f"- Purpose: {stage.get('purpose', '')}",
            f"- Required: {stage.get('required', True)}",
            "",
        ])
    lines.extend([
        "## Evidence Requirements",
        *[f"- {item}" for item in packet.get("evidence_requirements", [])],
        "",
        "## Audit Requirements",
        *[f"- {item}" for item in packet.get("audit_requirements", [])],
        "",
        "## Core Boundary",
        "AIGC may prepare and show a procedure packet. External execution remains blocked unless a future reviewed connector executes after explicit operator approval.",
    ])
    return "\n".join(lines) + "\n"


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


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
