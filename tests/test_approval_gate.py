from __future__ import annotations

from src.core.work_order import build_approval_packet, build_governance_decision, work_order_from_payload


def make_work_order():
    return work_order_from_payload({
        "work_order_id": "AIGC-WO-APP-001",
        "title": "Internal work-order approval test",
        "objective": "Build an approval packet for internal preparation only.",
        "domain": "governance",
        "urgency": "normal",
        "risk_class": "medium",
        "desired_output": "approval packet",
        "external_action_intent": "none",
        "acceptance_criteria": ["exact phrase visible"],
        "operator_visible_summary": "Approval test.",
        "symbolic_layers": ["omni"],
        "requested_agents": [],
        "secret_references": [],
        "source": "pytest",
    })


def test_approval_packet_requires_exact_visible_phrase_and_never_self_approves() -> None:
    work_order = make_work_order()
    decision = build_governance_decision(work_order, "AIGC-CORR-APP")
    packet = build_approval_packet(work_order, decision, "AIGC-CORR-APP")

    assert packet.status == "pending_operator_review"
    assert packet.approved is False
    assert packet.denied is False
    assert packet.revision_required is False
    assert packet.self_approval_allowed is False
    assert packet.external_action_performed is False
    assert work_order.work_order_id in packet.required_phrase
    assert "internal governed preparation only" in packet.required_phrase
    assert "Revise AIGC work order" in packet.revision_phrase_template


def test_symbolic_layers_do_not_grant_execution_authority() -> None:
    work_order = make_work_order()
    decision = build_governance_decision(work_order, "AIGC-CORR-APP")

    assert decision.symbolic_layers_grant_authority is False
    assert decision.external_action_allowed is False
    assert decision.self_approval_allowed is False
