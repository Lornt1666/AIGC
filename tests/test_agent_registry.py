from __future__ import annotations

import pytest

from src.core.agent_registry import build_agent_registry, build_workflow_plan, get_agent


def test_registry_contains_phase_adapters_and_all_seven_engineering_workflows() -> None:
    registry = build_agent_registry()

    assert len(registry) >= 30
    assert {"opportunity_radar", "controlled_execution", "runtime_preflight", "subagent_forge"}.issubset(registry)
    assert {
        "root_cause",
        "zero_regression_refactor",
        "adversarial_testing",
        "contract_synthesis",
        "architecture_tradeoff",
        "legacy_reverse_engineering",
        "red_team_review",
    }.issubset(registry)


def test_phase_agents_never_claim_direct_external_action_permission() -> None:
    for agent in build_agent_registry().values():
        assert agent.external_actions is False
        if agent.kind == "phase_adapter":
            assert agent.phase is not None


def test_workflow_planner_produces_bounded_auditable_plan() -> None:
    agent = get_agent("root_cause")
    plan = build_workflow_plan(agent, "Diagnose duplicate task delivery")

    assert plan["status"] == "plan_created"
    assert plan["task"] == "Diagnose duplicate task delivery"
    assert plan["safety_constraints"]["repository_mutations_allowed"] is False
    assert plan["safety_constraints"]["external_actions_allowed"] is False
    assert plan["execution_mode"] == "deterministic_workflow_plan_only"


def test_workflow_planner_rejects_empty_task() -> None:
    with pytest.raises(ValueError, match="non-empty task"):
        build_workflow_plan(get_agent("root_cause"), "  ")


def test_phase_adapter_cannot_be_used_as_workflow_planner() -> None:
    with pytest.raises(ValueError, match="not a workflow planner"):
        build_workflow_plan(get_agent("assessment"), "test")
