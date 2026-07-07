from __future__ import annotations

from typing import Any, Dict, List

from src.core.contract_validator import validate_artifact
from src.orchestration.correlation import make_id, utc_now


EVENT_TYPES = [
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
]

EXTERNAL_ACTION_STATES: List[Any] = [False, "blocked", "approved"]


def create_orchestration_event(
    event_type: str,
    *,
    workflow_execution_id: str,
    work_order_id: str,
    audit_event_id: str | None = None,
    action_permit_id: str = "",
    payload: Dict[str, Any] | None = None,
    risk_level: str = "low",
    requires_human_approval: bool = True,
    allowed_authority_level: str = "A1_INTERNAL",
    status: str = "created",
    external_action_performed: Any = False,
) -> Dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown orchestration event type: {event_type}")
    if external_action_performed not in EXTERNAL_ACTION_STATES:
        raise ValueError("external_action_performed must be false, blocked, or approved.")
    event = {
        "event_id": make_id("AIGC-ORCH-EVENT"),
        "event_type": event_type,
        "timestamp": utc_now(),
        "source_system": "aigc_orchestration_fabric",
        "workflow_execution_id": workflow_execution_id,
        "audit_event_id": audit_event_id or make_id("AIGC-AUDIT"),
        "work_order_id": work_order_id,
        "action_permit_id": action_permit_id,
        "payload": payload or {},
        "risk_level": risk_level,
        "requires_human_approval": requires_human_approval,
        "allowed_authority_level": allowed_authority_level,
        "status": status,
        "external_action_performed": external_action_performed,
    }
    return validate_orchestration_event(event)


def create_workflow_execution_record(
    *,
    workflow_execution_id: str,
    workflow_name: str,
    trigger_type: str,
    input_event_id: str,
    output_event_ids: List[str],
    work_order_id: str,
    audit_event_id: str,
    action_permit_id: str = "",
    status: str = "completed",
    approval_required: bool = True,
    approval_status: str = "human_review_required",
    external_action_performed: Any = False,
    blocked_actions: List[str] | None = None,
    errors: List[str] | None = None,
    next_safe_action: str = "Review generated local artifacts before any external action.",
) -> Dict[str, Any]:
    if external_action_performed not in EXTERNAL_ACTION_STATES:
        raise ValueError("external_action_performed must be false, blocked, or approved.")
    record = {
        "id": workflow_execution_id,
        "workflow_name": workflow_name,
        "workflow_engine": "aigc_local_dry_run",
        "trigger_type": trigger_type,
        "dry_run": True,
        "started_at": utc_now(),
        "completed_at": utc_now(),
        "status": status,
        "input_event_id": input_event_id,
        "output_event_ids": output_event_ids,
        "work_order_id": work_order_id,
        "action_permit_id": action_permit_id,
        "audit_event_id": audit_event_id,
        "external_action_performed": external_action_performed,
        "approval_required": approval_required,
        "approval_status": approval_status,
        "blocked_actions": blocked_actions or [
            "send_email",
            "send_message",
            "submit_application",
            "deploy_service",
            "publish_release",
            "procure_or_purchase",
            "client_delivery",
        ],
        "errors": errors or [],
        "next_safe_action": next_safe_action,
    }
    return validate_workflow_execution_record(record)


def validate_orchestration_event(event: Dict[str, Any]) -> Dict[str, Any]:
    if event.get("event_type") not in EVENT_TYPES:
        raise ValueError(f"Unknown orchestration event type: {event.get('event_type')}")
    return validate_artifact("orchestration_event", event)


def validate_workflow_execution_record(record: Dict[str, Any]) -> Dict[str, Any]:
    if record.get("dry_run") is not True:
        raise ValueError("Workflow execution records in this fabric must be dry_run=true.")
    if record.get("external_action_performed") == "approved":
        raise ValueError("Dry-run workflow execution cannot record approved external action.")
    return validate_artifact("workflow_execution_record", record)
