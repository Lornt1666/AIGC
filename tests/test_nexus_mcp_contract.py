from __future__ import annotations

import asyncio
import json

import pytest

from src.integrations.mcp.server import build_mcp_server
from src.integrations.mcp.tools import (
    assess_aigc_action,
    get_aigc_status,
    procure_deep_research_plan,
    run_aigc_dry_run,
    run_employer_sandbox,
    seed_aigc_regenexcalibur_universe,
)


EXPECTED_TOOLS = {
    "aigc_get_status",
    "aigc_render_control_center",
    "assess_aigc_action",
    "run_aigc_dry_run",
    "aigc_run_employer_sandbox",
    "procure_deep_research_plan",
    "aigc_seed_regenexcalibur_universe",
}


def test_status_is_safe_and_truthful():
    status = get_aigc_status()
    assert status["authority_granted"] is False
    assert status["external_action_performed"] is False
    assert status["connectors"]["enabled_live_mutation_capabilities"] == 0
    assert len(status["occupation_packs"]) >= 13
    assert all(item["status"] == "DRAFT" for item in status["occupation_packs"])
    serialized = json.dumps(status).lower()
    assert "authorization: bearer" not in serialized
    assert "private_key" not in serialized


def test_action_assessment_cannot_accept_caller_asserted_authority():
    assessment = assess_aigc_action(
        intent_id="ACT-MESSAGE001",
        effect_class="COMMUNICATION",
        communication=True,
    )
    assert assessment["disposition"] == "BLOCK_PENDING_EXPLICIT_AUTHORITY"
    assert assessment["authority_granted"] is False
    assert assessment["external_action_performed"] is False

    with pytest.raises(TypeError):
        assess_aigc_action(
            intent_id="ACT-MESSAGE001",
            effect_class="COMMUNICATION",
            communication=True,
            existing_explicit_authority=True,
        )


def test_dry_run_is_deterministic_and_stops_before_execute():
    first = run_aigc_dry_run(goal="APPLICATION_PREPARATION")
    second = run_aigc_dry_run(goal="APPLICATION_PREPARATION")
    assert first == second
    assert first["zero_egress"] is True
    assert first["external_action_performed"] is False
    assert first["stages"][-1]["stage"] == "EXECUTE"
    assert first["stages"][-1]["status"] == "BLOCKED_PERMISSION"
    assert first["final_status"] == "BLOCKED_BEFORE_EXECUTE"


@pytest.mark.parametrize(
    "scenario",
    ["PROMPT_INJECTION", "EXTERNAL_ACTION_REQUEST", "REGULATED_SCOPE_REQUEST"],
)
def test_employer_sandbox_denies_adversarial_scenarios(scenario):
    result = run_employer_sandbox(
        pack_id="OCC-DATA_ANALYSIS_REPORTING",
        capability_id="CAP-DATA_QUALITY",
        scenario=scenario,
    )
    assert result["disposition"] == "DENIED_BY_SANDBOX_POLICY"
    assert result["zero_egress"] is True
    assert result["credentials_accessed"] is False
    assert result["authority_granted"] is False
    assert result["external_action_performed"] is False


def test_employer_sandbox_rejects_cross_pack_capability():
    with pytest.raises(ValueError, match="does not belong"):
        run_employer_sandbox(
            pack_id="OCC-ADMINISTRATIVE_COORDINATOR",
            capability_id="CAP-DATA_QUALITY",
        )


def test_mcp_metadata_is_exact_read_only_and_closed_to_authority_inputs():
    tools = asyncio.run(build_mcp_server().list_tools())
    assert {item.name for item in tools} == EXPECTED_TOOLS
    for item in tools:
        assert item.annotations.readOnlyHint is True
        assert item.annotations.destructiveHint is False
        assert item.annotations.idempotentHint is True
        assert item.annotations.openWorldHint is False
        assert item.outputSchema is not None
    assessment = next(item for item in tools if item.name == "assess_aigc_action")
    assert "existing_explicit_authority" not in assessment.inputSchema["properties"]
    assert "permit_id" not in assessment.inputSchema["properties"]


def test_mcp_tool_call_returns_model_readable_and_structured_results():
    content, structured = asyncio.run(
        build_mcp_server().call_tool("run_aigc_dry_run", {"goal": "WORK_SEARCH"})
    )
    assert content[0].type == "text"
    assert structured["zero_egress"] is True
    assert structured["external_action_performed"] is False
    assert structured["final_status"] == "BLOCKED_BEFORE_EXECUTE"


def test_canonical_employer_sandbox_tool_emits_zero_egress_receipt():
    content, structured = asyncio.run(
        build_mcp_server().call_tool("aigc_run_employer_sandbox", {"mode": "sandbox"})
    )
    assert content[0].type == "text"
    assert structured["terminal_status"] == "PASS"
    assert structured["external_actions_performed"] == 0
    assert structured["provider_calls_performed"] == 0
    assert len(structured["receipt_sha256"]) == 64


def test_deep_research_mcp_tool_only_builds_a_local_procurement_plan():
    result = procure_deep_research_plan(
        request_id="RESEARCH-MCP-001",
        question="Which occupation capability packs should AIGC prioritize for supervised evaluation?",
        intended_decision="Select the next occupation-pack evaluation backlog.",
        jurisdictions=["Canada", "United States"],
        maximum_sources=20,
        maximum_spend_cad="10.00",
    )
    assert result["provider_call_count"] == 0
    assert result["external_action_performed"] is False
    assert result["authority_granted"] is False
    assert result["final_status"] == "BLOCKED_BEFORE_SOURCE_RETRIEVAL"


def test_regenexcalibur_mcp_tool_emits_deterministic_zero_egress_receipt():
    first = seed_aigc_regenexcalibur_universe(requested_evolution_depth=1)
    second = seed_aigc_regenexcalibur_universe(requested_evolution_depth=1)
    assert first == second
    assert first["terminal_status"] == "PASS"
    assert first["zero_egress"] is True
    assert first["provider_calls_performed"] == 0
    assert first["external_actions_performed"] == 0
    assert first["authority_granted"] is False
    assert len(first["agents"]) == 8
    assert len(first["receipt_sha256"]) == 64
