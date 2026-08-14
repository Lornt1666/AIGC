from __future__ import annotations

import json

import pytest

from src.integrations.aigc_plugin_bridge import dispatch_bridge_request


def test_status_bridge_is_sanitized_and_non_authorizing():
    result = dispatch_bridge_request({"operation": "aigc_get_status", "arguments": {}})
    assert result["authority_granted"] is False
    assert result["external_action_performed"] is False
    assert result["plugin"]["host_validation"] == "NOT_PERFORMED"
    serialized = json.dumps(result).lower()
    assert "authorization: bearer" not in serialized
    assert "private_key" not in serialized


def test_control_center_is_structured_and_widget_independent():
    result = dispatch_bridge_request(
        {"operation": "aigc_render_control_center", "arguments": {}}
    )
    assert result["widget_required"] is False
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
