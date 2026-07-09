from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.core.contract_validator import validate_artifact, validate_file


POLICY_SCHEMA = "approval_gated_external_action_policy"

HARD_BLOCKED = {
    "use_credentials_without_reviewed_integration",
    "bypass_platform_rules",
    "fabricate_credentials",
    "self_approve",
    "deliver_work_without_operator_review",
}


class ApprovalGatedActionError(ValueError):
    """Raised when the approval-gated action policy is unsafe or malformed."""


def load_policy(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ApprovalGatedActionError(f"Expected object policy at {path}")
    validate_artifact(POLICY_SCHEMA, payload)
    validate_policy(payload)
    return payload


def validate_policy(policy: Dict[str, Any]) -> None:
    if not bool(policy.get("operator_popup_required")):
        raise ApprovalGatedActionError("operator_popup_required must be true.")
    if not bool(policy.get("proceed_button_required")):
        raise ApprovalGatedActionError("proceed_button_required must be true.")
    controls = dict(policy.get("global_controls", {}))
    if controls.get("agent_self_approval_allowed") is not False:
        raise ApprovalGatedActionError("agent_self_approval_allowed must remain false.")
    if controls.get("external_action_default") != "blocked_until_operator_proceeds":
        raise ApprovalGatedActionError("external_action_default must be blocked_until_operator_proceeds.")
    blocked = {str(item.get("action", "")) for item in policy.get("hard_blocked_actions", []) if isinstance(item, dict)}
    missing = sorted(HARD_BLOCKED - blocked)
    if missing:
        raise ApprovalGatedActionError(f"Missing hard-blocked actions: {missing}")


def build_review_popup_packet(policy: Dict[str, Any], requested_action: Dict[str, Any]) -> Dict[str, Any]:
    """Build a local popup payload. This does not execute the action."""
    action = str(requested_action.get("action", ""))
    hard_blocked = {item["action"]: item for item in policy.get("hard_blocked_actions", []) if isinstance(item, dict)}
    allowed = {item["action"]: item for item in policy.get("approval_automatable_actions", []) if isinstance(item, dict)}

    if action in hard_blocked:
        status = "hard_blocked"
        proceed_enabled = False
        reason = hard_blocked[action].get("reason", "Action is hard-blocked by AIGC policy.")
        requirements: List[str] = []
    elif action in allowed:
        status = "operator_proceed_required"
        proceed_enabled = True
        reason = "Operator must review the exact action and click Proceed before any external action can occur."
        requirements = list(allowed[action].get("requirements", []))
    else:
        status = "unknown_action_blocked"
        proceed_enabled = False
        reason = "Action is not in the approval-gated allowlist."
        requirements = []

    packet = {
        "popup_id": make_id("AIGC-ACTION-POPUP", action, requested_action.get("destination", ""), utc_now()),
        "created_at": utc_now(),
        "title": policy.get("global_controls", {}).get("popup_title", "AIGC External Action Review"),
        "action": action,
        "status": status,
        "proceed_button_label": policy.get("global_controls", {}).get("proceed_button_label", "Proceed"),
        "cancel_button_label": policy.get("global_controls", {}).get("cancel_button_label", "Cancel"),
        "proceed_enabled": proceed_enabled,
        "reason": reason,
        "requirements": requirements,
        "exact_payload": requested_action.get("payload", {}),
        "destination": requested_action.get("destination", ""),
        "risk_class": requested_action.get("risk_class", "high"),
        "cost_or_terms": requested_action.get("cost_or_terms", {}),
        "platform_terms_status": requested_action.get("platform_terms_status", "not_reviewed"),
        "rollback_or_correction_plan": requested_action.get("rollback_or_correction_plan", "operator must define before proceeding"),
        "operator_review_required": True,
        "agent_self_approval_allowed": False,
        "external_action_performed": False,
    }
    return packet


def run_policy_smoke(project_root: Path, policy_path: Path | None = None) -> Dict[str, Any]:
    root = project_root.resolve()
    policy_path = policy_path or root / "config" / "approval_gated_external_actions.json"
    policy = load_policy(policy_path)
    validate_file(POLICY_SCHEMA, policy_path)
    allowed_packet = build_review_popup_packet(policy, {
        "action": "message",
        "destination": "manual-review@example.local",
        "payload": {"message": "Draft message for operator review only."},
        "risk_class": "medium",
        "platform_terms_status": "review_required",
    })
    blocked_packet = build_review_popup_packet(policy, {
        "action": "fabricate_credentials",
        "destination": "blocked",
        "payload": {"claim": "untrue credential"},
        "risk_class": "critical",
        "platform_terms_status": "blocked",
    })
    return {
        "policy_id": policy.get("policy_id", ""),
        "allowed_packet": allowed_packet,
        "blocked_packet": blocked_packet,
        "external_action_performed": False,
    }


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
