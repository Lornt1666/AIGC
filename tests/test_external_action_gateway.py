from __future__ import annotations

from src.core.work_order import build_external_action_permit, build_governance_decision, work_order_from_payload


def payload(external_action_intent: str) -> dict:
    return {
        "work_order_id": "AIGC-WO-EXT-001",
        "title": "Prepare outreach packet",
        "objective": "Prepare an outreach draft but do not send it.",
        "domain": "communications",
        "urgency": "normal",
        "risk_class": "medium",
        "desired_output": "reviewable outreach draft",
        "external_action_intent": external_action_intent,
        "acceptance_criteria": ["draft visible", "no sending"],
        "operator_visible_summary": "External action gateway test.",
        "symbolic_layers": [],
        "requested_agents": [],
        "secret_references": [],
        "source": "pytest",
    }


def test_external_action_requested_remains_blocked_by_default() -> None:
    work_order = work_order_from_payload(payload("proposed"))
    decision = build_governance_decision(work_order, "AIGC-CORR-EXT")
    permit = build_external_action_permit(work_order, decision, "AIGC-CORR-EXT")

    assert permit.requested is True
    assert permit.live_execution_allowed is False
    assert permit.external_action_performed is False
    assert permit.status == "blocked_pending_future_review"
    assert "operator_confirmation" in permit.required_future_controls


def test_external_action_not_requested_still_keeps_gateway_disabled() -> None:
    work_order = work_order_from_payload(payload("none"))
    decision = build_governance_decision(work_order, "AIGC-CORR-EXT")
    permit = build_external_action_permit(work_order, decision, "AIGC-CORR-EXT")

    assert permit.requested is False
    assert permit.live_execution_allowed is False
    assert permit.external_action_performed is False
    assert permit.status == "not_requested_blocked_by_default"
