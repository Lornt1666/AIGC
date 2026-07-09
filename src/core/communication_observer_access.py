from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.core.contract_validator import validate_artifact, validate_file


OBSERVER_SCHEMA = "communication_observer_access"


class CommunicationObserverAccessError(ValueError):
    """Raised when communication observer access would violate governance."""


def load_policy(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CommunicationObserverAccessError(f"Expected JSON object policy at {path}")
    validate_policy(payload)
    return payload


def validate_policy(policy: Dict[str, Any]) -> None:
    controls = dict(policy.get("approval_controls", {}))
    required_true = [
        "operator_popup_required",
        "proceed_button_required",
        "counterparty_request_required",
        "visibility_scope_required",
        "privacy_review_required",
        "redaction_review_required",
        "audit_receipt_required",
    ]
    for key in required_true:
        if controls.get(key) is not True:
            raise CommunicationObserverAccessError(f"approval_controls.{key} must be true")
    if controls.get("external_invite_sent_by_default") is not False:
        raise CommunicationObserverAccessError("external_invite_sent_by_default must remain false")
    defaults = dict(policy.get("observer_access_defaults", {}))
    for key in ["read_only", "counterparty_specific", "project_specific", "redacted_by_default", "hide_secrets"]:
        if defaults.get(key) is not True:
            raise CommunicationObserverAccessError(f"observer_access_defaults.{key} must be true")


def build_observer_access_packet(
    policy: Dict[str, Any],
    counterparty: Dict[str, Any],
    project_id: str,
    visibility_scope: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    validate_policy(policy)
    scope = [dict(item) for item in visibility_scope]
    if not counterparty.get("name"):
        raise CommunicationObserverAccessError("counterparty.name is required before observer access can be prepared")
    if not counterparty.get("request_summary"):
        raise CommunicationObserverAccessError("counterparty.request_summary is required before observer access can be prepared")
    if not scope:
        raise CommunicationObserverAccessError("visibility_scope must include at least one selected artifact or status item")

    packet = {
        "packet_id": make_id("AIGC-COMM", project_id, counterparty.get("name", ""), utc_now()),
        "created_at": utc_now(),
        "mode": "observer_invite_preparation_only",
        "operator_contact_email": str(policy.get("operator_contact_email", "JustLornt95@gmail.com")),
        "counterparty": {
            "name": counterparty.get("name", ""),
            "organization": counterparty.get("organization", ""),
            "email": counterparty.get("email", ""),
            "platform": counterparty.get("platform", ""),
            "request_summary": counterparty.get("request_summary", ""),
            "project_id": project_id,
        },
        "observer_access": {
            **dict(policy.get("observer_access_defaults", {})),
            "chatgpt_application_observer_link": "future_integration_not_enabled_in_current_pr",
            "email_contact_available": True,
            "local_artifact_packet_available": True,
            "invite_requires_operator_proceed": True,
        },
        "visibility_scope": scope,
        "privacy_boundary": {
            "show_only_selected_project_scope": True,
            "hide_secrets": True,
            "hide_private_repo_internals": True,
            "hide_unrelated_clients": True,
            "hide_operator_private_notes_by_default": True,
            "redaction_review_required_before_share": True,
            "operator_can_revoke": True,
        },
        "approval_required": True,
        "external_invite_sent": False,
    }
    validate_artifact(OBSERVER_SCHEMA, packet)
    return packet


def run_observer_access_packet(
    project_root: Path,
    policy_path: Path | None = None,
    counterparty_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    root = project_root.resolve()
    policy_path = policy_path or root / "config" / "communication_observer_access.json"
    counterparty_path = counterparty_path or root / "config" / "counterparty_request_example.json"
    artifact_root = artifact_root or root / "reports" / "artifacts" / "communications"

    policy = load_policy(policy_path)
    request = json.loads(counterparty_path.read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise CommunicationObserverAccessError("counterparty request must be a JSON object")

    counterparty = {
        "name": request.get("counterparty", {}).get("name", ""),
        "organization": request.get("counterparty", {}).get("organization", ""),
        "email": request.get("counterparty", {}).get("email", ""),
        "platform": request.get("source", {}).get("platform", ""),
        "request_summary": request.get("work_description", ""),
    }
    visibility_scope = [
        {
            "item": "counterparty_request_summary",
            "description": "The other party's description of what they need done.",
            "shareable_after_redaction_review": True,
        },
        {
            "item": "deliverables_and_acceptance_criteria",
            "description": "Deliverables, acceptance criteria, and success outcome for the project/task/job.",
            "shareable_after_redaction_review": True,
        },
        {
            "item": "status_and_audit_receipts",
            "description": "Selected status updates and audit receipts approved by the operator.",
            "shareable_after_redaction_review": True,
        },
    ]

    packet = build_observer_access_packet(policy, counterparty, str(request.get("request_id", "manual-project")), visibility_scope)
    output_root = artifact_root / safe_path_name(packet["packet_id"])
    output_root.mkdir(parents=True, exist_ok=True)
    packet_path = output_root / "communication_observer_access.json"
    report_path = output_root / "communication_observer_access.md"
    write_json(packet_path, packet)
    validate_file(OBSERVER_SCHEMA, packet_path)
    report_path.write_text(render_observer_access_report(packet), encoding="utf-8")

    return {
        "packet": packet,
        "packet_path": relative_to_root(root, packet_path),
        "report_path": relative_to_root(root, report_path),
        "external_invite_sent": False,
    }


def render_observer_access_report(packet: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# AIGC Communication Observer Access Packet",
        "",
        f"Packet ID: {packet['packet_id']}",
        f"Created At: {packet['created_at']}",
        f"Operator Contact Email: {packet['operator_contact_email']}",
        "External Invite Sent: No",
        "",
        "## Counterparty",
        f"- Name: {packet['counterparty'].get('name', '')}",
        f"- Organization: {packet['counterparty'].get('organization', '')}",
        f"- Platform: {packet['counterparty'].get('platform', '')}",
        "",
        "## Visibility Scope",
    ]
    for item in packet.get("visibility_scope", []):
        lines.append(f"- {item.get('item', '')}: {item.get('description', '')}")
    lines.extend([
        "",
        "## Privacy Boundary",
        "- Read-only observer access only.",
        "- Secrets and private repo internals remain hidden.",
        "- Only selected redacted project artifacts may be shared.",
        "- Operator approval is required before any invite or external communication.",
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
