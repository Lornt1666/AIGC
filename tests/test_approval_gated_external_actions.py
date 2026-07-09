from __future__ import annotations

from pathlib import Path

from src.core.approval_gated_external_actions import build_review_popup_packet, load_policy, run_policy_smoke


POLICY_PATH = Path("config/approval_gated_external_actions.json")


def test_policy_loads_and_requires_operator_popup() -> None:
    policy = load_policy(POLICY_PATH)

    assert policy["operator_popup_required"] is True
    assert policy["proceed_button_required"] is True
    assert policy["global_controls"]["agent_self_approval_allowed"] is False
    assert policy["global_controls"]["external_action_default"] == "blocked_until_operator_proceeds"


def test_allowed_action_builds_proceed_required_popup() -> None:
    policy = load_policy(POLICY_PATH)
    popup = build_review_popup_packet(policy, {
        "action": "message",
        "destination": "manual-review",
        "payload": {"message": "Draft only"},
        "risk_class": "medium",
        "platform_terms_status": "review_required",
    })

    assert popup["status"] == "operator_proceed_required"
    assert popup["proceed_enabled"] is True
    assert popup["operator_review_required"] is True
    assert popup["external_action_performed"] is False


def test_hard_blocked_action_disables_proceed() -> None:
    policy = load_policy(POLICY_PATH)
    popup = build_review_popup_packet(policy, {
        "action": "fabricate_credentials",
        "destination": "blocked",
        "payload": {"claim": "false credential"},
        "risk_class": "critical",
        "platform_terms_status": "blocked",
    })

    assert popup["status"] == "hard_blocked"
    assert popup["proceed_enabled"] is False
    assert popup["agent_self_approval_allowed"] is False
    assert popup["external_action_performed"] is False


def test_policy_smoke_generates_allowed_and_blocked_examples() -> None:
    payload = run_policy_smoke(Path("."), POLICY_PATH)

    assert payload["external_action_performed"] is False
    assert payload["allowed_packet"]["proceed_enabled"] is True
    assert payload["blocked_packet"]["proceed_enabled"] is False
