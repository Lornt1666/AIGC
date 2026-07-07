from __future__ import annotations

from src.orchestration.dry_run_executor import run_workflow_dry_run
from src.orchestration.workflow_registry import list_workflows


def test_action_permit_workflow_cannot_self_approve() -> None:
    result = run_workflow_dry_run("action_permit_approval_queue")
    event_types = {event["event_type"] for event in result.events}

    assert "action_permit.requested" in event_types
    assert "human_approval.required" in event_types
    assert "human_approval.granted" not in event_types
    assert result.workflow_execution["approval_status"] == "human_review_required"


def test_all_workflows_keep_external_action_disallowed() -> None:
    for workflow in list_workflows():
        assert workflow.external_action_allowed is False
        assert "deployment" in workflow.blocked_actions
        assert "payment" in workflow.blocked_actions


def test_dry_runs_never_record_approved_external_action() -> None:
    for workflow in list_workflows():
        result = run_workflow_dry_run(workflow.workflow_id)
        assert result.workflow_execution["external_action_performed"] is False
        assert all(event["external_action_performed"] != "approved" for event in result.events)
