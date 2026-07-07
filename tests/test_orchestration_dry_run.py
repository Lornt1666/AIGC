from __future__ import annotations

from dataclasses import asdict

from src.orchestration.dry_run_executor import run_workflow_dry_run


def test_intake_dry_run_emits_work_order_created() -> None:
    result = run_workflow_dry_run("intake_to_work_order")

    assert result.external_action_performed is False
    assert any(event["event_type"] == "work_order.created" for event in result.events)
    assert result.workflow_execution["external_action_performed"] is False


def test_regression_dry_run_emits_passed_or_failed_status() -> None:
    result = run_workflow_dry_run("regression_guard_check")
    event_types = {event["event_type"] for event in result.events}

    assert "regression_guard.passed" in event_types or "regression_guard.failed" in event_types
    assert result.workflow_execution["dry_run"] is True


def test_delivery_draft_stops_before_external_action() -> None:
    result = run_workflow_dry_run("delivery_draft")

    assert result.workflow_execution["external_action_performed"] is False
    assert any(event["event_type"] == "delivery_packet.ready" for event in result.events)
    assert any(event["external_action_performed"] == "blocked" for event in result.events)
    assert "live action permit" in result.workflow_execution["next_safe_action"]


def test_dry_run_result_is_serializable() -> None:
    result = run_workflow_dry_run("actor_execution_dry_run")
    payload = asdict(result)

    assert payload["workflow_id"] == "actor_execution_dry_run"
    assert payload["external_action_performed"] is False
    assert len(payload["events"]) == 3
