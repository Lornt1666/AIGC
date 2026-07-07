from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from src.orchestration.correlation import make_id
from src.orchestration.event_contracts import create_orchestration_event, create_workflow_execution_record
from src.orchestration.workflow_registry import get_workflow


@dataclass(frozen=True)
class DryRunResult:
    workflow_id: str
    workflow_execution: Dict[str, Any]
    events: List[Dict[str, Any]]
    external_action_performed: bool


def run_workflow_dry_run(
    workflow_id: str,
    *,
    work_order_id: str = "WORK-ORDER-FIXTURE",
    action_permit_id: str = "",
    payload: Dict[str, Any] | None = None,
) -> DryRunResult:
    workflow = get_workflow(workflow_id)
    workflow_execution_id = make_id("AIGC-WORKFLOW")
    input_event_id = make_id("AIGC-INPUT")
    audit_event_id = make_id("AIGC-AUDIT")
    events = [
        create_orchestration_event(
            event_type,
            workflow_execution_id=workflow_execution_id,
            work_order_id=work_order_id,
            audit_event_id=audit_event_id,
            action_permit_id=action_permit_id,
            payload=_event_payload(workflow_id, event_type, payload or {}),
            requires_human_approval=workflow.requires_human_approval,
            status=_event_status(workflow_id, event_type),
            external_action_performed=_external_action_state(workflow_id, event_type),
        )
        for event_type in workflow.output_event_types
    ]
    execution = create_workflow_execution_record(
        workflow_execution_id=workflow_execution_id,
        workflow_name=workflow.workflow_name,
        trigger_type=workflow.trigger_type,
        input_event_id=input_event_id,
        output_event_ids=[event["event_id"] for event in events],
        work_order_id=work_order_id,
        action_permit_id=action_permit_id,
        audit_event_id=audit_event_id,
        approval_required=workflow.requires_human_approval,
        approval_status="human_review_required" if workflow.requires_human_approval else "not_required_for_internal_check",
        external_action_performed=False,
        blocked_actions=workflow.blocked_actions,
        next_safe_action=_next_safe_action(workflow_id),
    )
    return DryRunResult(
        workflow_id=workflow_id,
        workflow_execution=execution,
        events=events,
        external_action_performed=False,
    )


def write_dry_run_report(result: DryRunResult, project_root: Path) -> Path:
    report_dir = project_root / "reports" / "orchestration"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{result.workflow_id}_dry_run_report.json"
    report_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True), encoding="utf-8")
    return report_path


def _event_payload(workflow_id: str, event_type: str, base_payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "workflow_id": workflow_id,
        "fixture": True,
        "no_external_action": True,
    }
    payload.update(base_payload)
    if event_type == "delivery_packet.ready":
        payload["delivery_blocked_until_human_approval"] = True
    return payload


def _event_status(workflow_id: str, event_type: str) -> str:
    if workflow_id == "delivery_draft" or event_type == "human_approval.required":
        return "waiting_for_human_review"
    return "dry_run_recorded"


def _external_action_state(workflow_id: str, event_type: str) -> Any:
    if workflow_id == "delivery_draft" or event_type == "external_action.blocked":
        return "blocked"
    return False


def _next_safe_action(workflow_id: str) -> str:
    if workflow_id == "delivery_draft":
        return "Review delivery packet; create a separate live action permit before any delivery."
    if workflow_id == "action_permit_approval_queue":
        return "Human operator must approve, deny, or revise; self-approval is disabled."
    return "Review dry-run report and keep external actions disabled."
