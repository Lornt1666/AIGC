from __future__ import annotations

from src.core.work_order import build_governance_decision, classify_work_order, work_order_from_payload


def make_payload(**overrides: object) -> dict:
    payload = {
        "work_order_id": "AIGC-WO-GOV-001",
        "title": "Draft customer proposal",
        "objective": "Prepare a customer-facing draft without sending it.",
        "domain": "customer proposal",
        "urgency": "normal",
        "risk_class": "medium",
        "desired_output": "customer-facing draft",
        "external_action_intent": "none",
        "acceptance_criteria": ["visible draft", "review packet"],
        "operator_visible_summary": "Governance test.",
        "symbolic_layers": ["mythic constellation mode"],
        "requested_agents": ["planner"],
        "secret_references": [],
        "source": "pytest",
    }
    payload.update(overrides)
    return payload


def test_customer_facing_draft_classification_without_external_action() -> None:
    work_order = work_order_from_payload(make_payload())

    assert classify_work_order(work_order) == "customer-facing-draft"

    decision = build_governance_decision(work_order, "AIGC-CORR-TEST")
    assert decision.external_action_allowed is False
    assert decision.self_approval_allowed is False
    assert decision.symbolic_layers_grant_authority is False
    assert "approval_required_before_external_action" not in decision.allowed_operations
    assert "outreach_message" in decision.blocked_operations
    assert "operator_review_required" in decision.required_approvals


def test_external_action_intent_requires_permit_and_blocks_execution() -> None:
    work_order = work_order_from_payload(make_payload(external_action_intent="proposed"))
    decision = build_governance_decision(work_order, "AIGC-CORR-TEST")

    assert decision.classification == "requires-permit"
    assert decision.external_action_allowed is False
    assert "external_action_permit_required" in decision.required_approvals
    assert "external_api_side_effect" in decision.blocked_operations


def test_high_risk_outward_action_is_blocked_high_risk() -> None:
    work_order = work_order_from_payload(make_payload(
        title="Submit job application",
        objective="Submit an application externally.",
        risk_class="high",
        external_action_intent="proposed",
    ))

    assert classify_work_order(work_order) == "blocked/high-risk"
