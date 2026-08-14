from __future__ import annotations

import json

import pytest

from src.integrations.aigc_plugin_bridge import dispatch_bridge_request


def test_status_bridge_is_sanitized_and_non_authorizing():
    result = dispatch_bridge_request({"operation": "aigc_get_status", "arguments": {}})
    assert result["authority_granted"] is False
    assert result["external_action_performed"] is False
    assert result["plugin"]["host_validation"] == "NOT_PERFORMED"
    assert result["readiness"]["verified_required_checks"] == 12
    assert result["readiness"]["verified_applicable_ratio"] == 0.352941
    assert result["readiness"]["production_ready"] is False
    serialized = json.dumps(result).lower()
    assert "authorization: bearer" not in serialized
    assert "private_key" not in serialized


def test_control_center_is_structured_and_widget_independent():
    result = dispatch_bridge_request(
        {"operation": "aigc_render_control_center", "arguments": {}}
    )
    assert result["widget_required"] is False
    assert result["readiness"]["verified_required_checks"] == 12
    assert "cloud_mutation" in result["blocked_actions"]
    assert result["authority_granted"] is False


def test_one_click_sandbox_defaults_to_valid_zero_egress_scenario():
    result = dispatch_bridge_request(
        {"operation": "aigc_run_employer_sandbox", "arguments": {"mode": "sandbox"}}
    )
    assert result["terminal_status"] == "PASS"
    assert result["external_actions_performed"] == 0
    assert result["provider_calls_performed"] == 0
    assert len(result["receipt_sha256"]) == 64


def test_regenexcalibur_bridge_is_closed_and_zero_egress():
    result = dispatch_bridge_request(
        {
            "operation": "aigc_seed_regenexcalibur_universe",
            "arguments": {"requested_evolution_depth": 1},
        }
    )
    assert result["terminal_status"] == "PASS"
    assert result["provider_calls_performed"] == 0
    assert result["external_actions_performed"] == 0
    assert result["authority_granted"] is False

    with pytest.raises(ValueError, match="unknown RegenExcalibur fields"):
        dispatch_bridge_request(
            {
                "operation": "aigc_seed_regenexcalibur_universe",
                "arguments": {"permit_id": "not-authority"},
            }
        )


def test_wealth_operator_bridge_exposes_planning_without_authority():
    result = dispatch_bridge_request(
        {
            "operation": "aigc_plan_wealth_work",
            "arguments": {
                "request_id": "WREQ-BRIDGE001",
                "action": "RESEARCH_OPPORTUNITIES",
                "objective": "Find verified remote contract opportunities.",
            },
        }
    )
    assert result["terminal_status"] == "PASS"
    assert result["authority_granted"] is False
    assert result["external_action_performed"] is False

    with pytest.raises(ValueError, match="unknown wealth work fields"):
        dispatch_bridge_request(
            {
                "operation": "aigc_plan_wealth_work",
                "arguments": {
                    "request_id": "WREQ-BRIDGE002",
                    "action": "SPEND_FUNDS",
                    "objective": "Attempt authority injection.",
                    "permit_id": "PERMIT-FAKE001",
                },
            }
        )


def test_llm_lifecycle_bridge_is_closed_and_zero_action():
    result = dispatch_bridge_request(
        {"operation": "aigc_plan_llm_lifecycle", "arguments": {}}
    )
    assert result["terminal_status"] == "BLOCKED"
    assert result["training_steps_performed"] == 0
    assert result["provider_calls_performed"] == 0
    assert result["external_actions_performed"] == 0
    assert result["authority_granted"] is False

    with pytest.raises(ValueError, match="accepts no arguments"):
        dispatch_bridge_request(
            {
                "operation": "aigc_plan_llm_lifecycle",
                "arguments": {"execution_authorized": True},
            }
        )


@pytest.mark.parametrize(
    "bridge_request",
    [
        {"operation": "unknown", "arguments": {}},
        {"operation": "aigc_get_status", "arguments": {"authority": True}},
        {"operation": "aigc_run_employer_sandbox", "arguments": {"permit_id": "fake"}},
        {"operation": "aigc_get_status", "arguments": {}, "secret": "forbidden"},
    ],
)
def test_bridge_rejects_unknown_and_authority_shaped_inputs(bridge_request):
    with pytest.raises(ValueError):
        dispatch_bridge_request(bridge_request)
