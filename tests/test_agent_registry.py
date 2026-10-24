from __future__ import annotations

import sqlite3
import subprocess

import pytest

import src.aigc_agents as aigc_agents
from src.core.agent_registry import build_agent_registry, build_workflow_plan, get_agent
from src.aigc_agents import main as agent_main


def test_registry_inventory_matches_documented_agent_counts() -> None:
    registry = build_agent_registry()

    assert sum(agent.kind == "phase_adapter" for agent in registry.values()) == 24
    assert sum(agent.kind == "workflow_planner" for agent in registry.values()) == 21
    assert len(registry) == 45
    assert {"opportunity_radar", "controlled_execution", "runtime_preflight", "subagent_forge", "regenexcalibur_envelope", "cloud_orchestration", "protocol_governance", "ci_diagnostics"}.issubset(registry)
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


def test_list_command_does_not_initialize_runtime_database(tmp_path, capsys) -> None:
    root = tmp_path / "project"
    root.mkdir()

    assert agent_main(["--root", str(root), "list"]) == 0
    capsys.readouterr()

    assert not (root / "memory" / "aigc_state.sqlite").exists()


def test_inspect_command_does_not_initialize_runtime_database(tmp_path, capsys) -> None:
    root = tmp_path / "project"
    root.mkdir()

    assert agent_main(["--root", str(root), "inspect", "root_cause"]) == 0
    capsys.readouterr()

    assert not (root / "memory" / "aigc_state.sqlite").exists()



def test_run_rejects_non_positive_timeout_without_initializing_database(tmp_path, capsys) -> None:
    root = tmp_path / "project"
    root.mkdir()

    assert agent_main(["--root", str(root), "run", "assessment", "--timeout-seconds", "0"]) == 2
    assert "--timeout-seconds must be greater than zero." in capsys.readouterr().err
    assert not (root / "memory" / "aigc_state.sqlite").exists()


def test_phase_adapter_timeout_is_recorded_as_terminal_failure(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "project"
    root.mkdir()

    def expire(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(aigc_agents.subprocess, "run", expire)

    assert agent_main([
        "--root", str(root), "run", "assessment", "--timeout-seconds", "0.01"
    ]) == 124
    assert "exceeded timeout of 0.01 seconds" in capsys.readouterr().err

    database = root / "memory" / "aigc_state.sqlite"
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT event_type, status, data_json FROM runtime_events "
            "WHERE event_type = 'agent_run_timed_out'"
        ).fetchone()

    assert row is not None
    assert row[0] == "agent_run_timed_out"
    assert row[1] == "timed_out"
    assert '"timeout_seconds": 0.01' in row[2]



def test_workflow_plan_output_is_removed_if_audit_event_fails(tmp_path, monkeypatch) -> None:
    root = tmp_path / "project"
    root.mkdir()
    output = root / "artifacts" / "plan.json"

    def fail_audit(*args, **kwargs):
        raise sqlite3.OperationalError("simulated audit database failure")

    monkeypatch.setattr(aigc_agents.AIGCStateStore, "insert_event", fail_audit)

    with pytest.raises(sqlite3.OperationalError, match="simulated audit database failure"):
        agent_main([
            "--root", str(root), "run", "root_cause",
            "--task", "Diagnose duplicate task delivery",
            "--output", "artifacts/plan.json",
        ])

    assert not output.exists()
    assert not list(output.parent.glob(".plan.json.*.tmp"))


def test_workflow_plan_output_is_atomic_and_audited(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    output = root / "artifacts" / "plan.json"

    assert agent_main([
        "--root", str(root), "run", "root_cause",
        "--task", "Diagnose duplicate task delivery",
        "--output", "artifacts/plan.json",
    ]) == 0

    import json

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["status"] == "plan_created"

    database = root / "memory" / "aigc_state.sqlite"
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT data_json FROM runtime_events "
            "WHERE event_type = 'workflow_agent_plan_created'"
        ).fetchone()

    assert row is not None
    event_data = json.loads(row[0])
    assert event_data["output_written"] is True
    assert event_data["output_path"] == str(output)



def test_workflow_plan_refuses_to_overwrite_existing_artifact(tmp_path, capsys) -> None:
    root = tmp_path / "project"
    root.mkdir()
    output = root / "artifacts" / "plan.json"
    output.parent.mkdir()
    output.write_text("preserve-me", encoding="utf-8")

    assert agent_main([
        "--root", str(root), "run", "root_cause",
        "--task", "Diagnose duplicate task delivery",
        "--output", "artifacts/plan.json",
    ]) == 2

    assert "refusing to overwrite an existing artifact" in capsys.readouterr().out
    assert output.read_text(encoding="utf-8") == "preserve-me"



def test_sensitive_phase_adapter_respects_emergency_stop_before_dispatch(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "project"
    root.mkdir()
    database = root / "memory" / "aigc_state.sqlite"
    store = aigc_agents.AIGCStateStore(database)
    store.set_flag("emergency_stop", "true")

    def unexpected_dispatch(*args, **kwargs):
        raise AssertionError("phase subprocess must not be called while emergency stop is active")

    monkeypatch.setattr(aigc_agents.subprocess, "run", unexpected_dispatch)

    assert agent_main([
        "--root", str(root), "--state-db", str(database),
        "run", "controlled_execution",
    ]) == 2
    assert "Emergency stop is active" in capsys.readouterr().out

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT event_type, status FROM runtime_events "
            "WHERE event_type = 'agent_run_blocked_by_emergency_stop'"
        ).fetchone()

    assert row == ("agent_run_blocked_by_emergency_stop", "blocked")
