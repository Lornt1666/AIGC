from __future__ import annotations

from src.core.contract_validator import validate_artifact
from src.orchestration.workflow_registry import get_workflow, list_workflows, workflow_registry_payload


def test_workflow_registry_loads_first_six_workflows() -> None:
    workflows = list_workflows()
    workflow_ids = {workflow.workflow_id for workflow in workflows}

    assert len(workflows) == 6
    assert {
        "intake_to_work_order",
        "action_permit_approval_queue",
        "regression_guard_check",
        "evidence_pack_refresh",
        "actor_execution_dry_run",
        "delivery_draft",
    }.issubset(workflow_ids)


def test_workflow_candidates_are_schema_valid_and_internal_only() -> None:
    for workflow in list_workflows():
        payload = workflow.to_dict()
        assert validate_artifact("workflow_candidate", payload) == payload
        assert payload["external_action_allowed"] is False
        assert "client_delivery" in payload["blocked_actions"]


def test_get_workflow_returns_named_workflow() -> None:
    workflow = get_workflow("delivery_draft")

    assert workflow.workflow_name == "Client Delivery Draft"
    assert workflow.requires_human_approval is True
    assert workflow.external_action_allowed is False


def test_registry_payload_disables_self_approval() -> None:
    payload = workflow_registry_payload()

    assert payload["workflow_count"] == 6
    assert payload["external_action_default"] is False
    assert payload["self_approval_allowed"] is False
