from __future__ import annotations

from src.core.contract_validator import validate_artifact
from src.orchestration.event_contracts import (
    EVENT_TYPES,
    create_orchestration_event,
    create_workflow_execution_record,
)


def test_orchestration_event_schema_validates_required_fields() -> None:
    event = create_orchestration_event(
        "work_order.created",
        workflow_execution_id="AIGC-WORKFLOW-TEST",
        work_order_id="WORK-ORDER-TEST",
        payload={"fixture": True},
    )

    assert validate_artifact("orchestration_event", event) == event
    assert event["event_type"] == "work_order.created"
    assert event["external_action_performed"] is False
    assert event["requires_human_approval"] is True


def test_all_required_event_types_are_declared() -> None:
    expected = {
        "work_order.created",
        "source_intake.completed",
        "claim_records.generated",
        "action_permit.requested",
        "human_approval.required",
        "human_approval.granted",
        "human_approval.rejected",
        "actor_task.queued",
        "actor_task.started",
        "actor_task.completed",
        "actor_task.failed",
        "qa.verification.passed",
        "qa.verification.failed",
        "evidence_pack.updated",
        "regression_guard.passed",
        "regression_guard.failed",
        "release_candidate.ready",
        "delivery_packet.ready",
        "external_action.blocked",
        "audit_event.written",
    }

    assert expected.issubset(set(EVENT_TYPES))


def test_workflow_execution_record_is_dry_run_only() -> None:
    record = create_workflow_execution_record(
        workflow_execution_id="AIGC-WORKFLOW-TEST",
        workflow_name="Test Workflow",
        trigger_type="manual",
        input_event_id="AIGC-INPUT-TEST",
        output_event_ids=["AIGC-OUTPUT-TEST"],
        work_order_id="WORK-ORDER-TEST",
        audit_event_id="AIGC-AUDIT-TEST",
    )

    assert validate_artifact("workflow_execution_record", record) == record
    assert record["dry_run"] is True
    assert record["external_action_performed"] is False
    assert "client_delivery" in record["blocked_actions"]
