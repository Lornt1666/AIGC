from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List

from src.core.contract_validator import validate_artifact


BLOCKED_EXTERNAL_ACTIONS = [
    "email",
    "messaging",
    "external_upload",
    "deployment",
    "publication",
    "procurement",
    "payment",
    "client_delivery",
]


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    workflow_name: str
    trigger_type: str
    description: str
    input_event_types: List[str]
    output_event_types: List[str]
    requires_human_approval: bool
    external_action_allowed: bool
    blocked_actions: List[str]

    def to_dict(self) -> Dict[str, object]:
        return validate_artifact("workflow_candidate", asdict(self))


def list_workflows() -> List[WorkflowDefinition]:
    return [
        WorkflowDefinition(
            workflow_id="intake_to_work_order",
            workflow_name="Intake to Work Order",
            trigger_type="manual_or_placeholder_webhook",
            description="Convert a fixture intake payload into a local work_order.created event.",
            input_event_types=["source_intake.completed"],
            output_event_types=["work_order.created"],
            requires_human_approval=True,
            external_action_allowed=False,
            blocked_actions=BLOCKED_EXTERNAL_ACTIONS,
        ),
        WorkflowDefinition(
            workflow_id="action_permit_approval_queue",
            workflow_name="Action Permit / Human Approval Queue",
            trigger_type="work_order.created",
            description="Create local permit and human approval requirement events without self-approval.",
            input_event_types=["work_order.created"],
            output_event_types=["action_permit.requested", "human_approval.required"],
            requires_human_approval=True,
            external_action_allowed=False,
            blocked_actions=BLOCKED_EXTERNAL_ACTIONS,
        ),
        WorkflowDefinition(
            workflow_id="regression_guard_check",
            workflow_name="Regression Guard Scheduled Check",
            trigger_type="manual_or_schedule_placeholder",
            description="Record a local regression guard dry-run outcome event.",
            input_event_types=["audit_event.written"],
            output_event_types=["regression_guard.passed"],
            requires_human_approval=False,
            external_action_allowed=False,
            blocked_actions=BLOCKED_EXTERNAL_ACTIONS,
        ),
        WorkflowDefinition(
            workflow_id="evidence_pack_refresh",
            workflow_name="Evidence Pack Refresh",
            trigger_type="baseline_or_evidence_event",
            description="Emit a local evidence_pack.updated fixture event.",
            input_event_types=["claim_records.generated"],
            output_event_types=["evidence_pack.updated"],
            requires_human_approval=True,
            external_action_allowed=False,
            blocked_actions=BLOCKED_EXTERNAL_ACTIONS,
        ),
        WorkflowDefinition(
            workflow_id="actor_execution_dry_run",
            workflow_name="Actor Execution Dry-Run",
            trigger_type="approved_local_permit_fixture",
            description="Simulate actor queue, start, and completion events without connector execution.",
            input_event_types=["action_permit.requested"],
            output_event_types=["actor_task.queued", "actor_task.started", "actor_task.completed"],
            requires_human_approval=True,
            external_action_allowed=False,
            blocked_actions=BLOCKED_EXTERNAL_ACTIONS,
        ),
        WorkflowDefinition(
            workflow_id="delivery_draft",
            workflow_name="Client Delivery Draft",
            trigger_type="qa.verification.passed",
            description="Prepare a local delivery_packet.ready event and stop before delivery.",
            input_event_types=["qa.verification.passed"],
            output_event_types=["delivery_packet.ready"],
            requires_human_approval=True,
            external_action_allowed=False,
            blocked_actions=BLOCKED_EXTERNAL_ACTIONS,
        ),
    ]


def get_workflow(workflow_id: str) -> WorkflowDefinition:
    for workflow in list_workflows():
        if workflow.workflow_id == workflow_id:
            return workflow
    raise KeyError(f"Unknown workflow: {workflow_id}")


def workflow_registry_payload() -> Dict[str, object]:
    workflows = [workflow.to_dict() for workflow in list_workflows()]
    return {
        "workflow_count": len(workflows),
        "workflows": workflows,
        "external_action_default": False,
        "self_approval_allowed": False,
    }
