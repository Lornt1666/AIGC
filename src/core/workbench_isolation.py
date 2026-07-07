from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List

from src.core.contract_validator import validate_artifact
from src.orchestration.correlation import make_id, utc_now


DEFAULT_BUDGET_LIMITS = {
    "max_steps": 100,
    "max_tool_calls": 40,
    "max_retries": 0,
    "max_runtime_seconds": 1800,
    "max_estimated_cost_units": 0,
}


@dataclass(frozen=True)
class WorkOrderWorkspace:
    workspace_id: str
    tenant_id: str
    work_order_id: str
    correlation_id: str
    created_at: str
    data_classification: str
    budget_limits: Dict[str, Any]
    approval_state: str
    artifact_roots: List[str]
    allowed_reference_ids: List[str]
    external_action_performed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return validate_workspace(asdict(self))


def create_work_order_workspace(
    *,
    tenant_id: str,
    work_order_id: str,
    data_classification: str = "internal",
    approval_state: str = "not_approved_for_external_action",
    budget_limits: Dict[str, Any] | None = None,
    allowed_reference_ids: List[str] | None = None,
) -> WorkOrderWorkspace:
    if not tenant_id.strip():
        raise ValueError("tenant_id is required.")
    if not work_order_id.strip():
        raise ValueError("work_order_id is required.")
    workspace_id = make_id("AIGC-WORKSPACE")
    return WorkOrderWorkspace(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        correlation_id=make_id("AIGC-CORR"),
        created_at=utc_now(),
        data_classification=data_classification,
        budget_limits={**DEFAULT_BUDGET_LIMITS, **(budget_limits or {})},
        approval_state=approval_state,
        artifact_roots=[f"data/workspaces/{tenant_id}/{work_order_id}/{workspace_id}"],
        allowed_reference_ids=allowed_reference_ids or [],
        external_action_performed=False,
    )


def create_parallel_workbench(tenant_id: str, work_order_ids: Iterable[str]) -> List[Dict[str, Any]]:
    workspaces = [
        create_work_order_workspace(tenant_id=tenant_id, work_order_id=work_order_id).to_dict()
        for work_order_id in work_order_ids
    ]
    assert_workspaces_isolated(workspaces)
    return workspaces


def validate_workspace(workspace: Dict[str, Any]) -> Dict[str, Any]:
    if workspace.get("external_action_performed") is not False:
        raise ValueError("Work order workspaces must not perform external action.")
    if workspace.get("approval_state") == "approved_for_external_action":
        raise ValueError("Workspace isolation layer cannot approve external action.")
    budget = workspace.get("budget_limits", {})
    for key in ["max_steps", "max_tool_calls", "max_runtime_seconds"]:
        if int(budget.get(key, 0)) <= 0:
            raise ValueError(f"{key} must be positive.")
    return validate_artifact("work_order_workspace", workspace)


def assert_workspaces_isolated(workspaces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen_workspace_ids: set[str] = set()
    seen_correlation_ids: set[str] = set()
    seen_artifact_roots: set[str] = set()
    for workspace in workspaces:
        validate_workspace(workspace)
        workspace_id = workspace["workspace_id"]
        correlation_id = workspace["correlation_id"]
        if workspace_id in seen_workspace_ids:
            raise ValueError(f"Duplicate workspace_id: {workspace_id}")
        if correlation_id in seen_correlation_ids:
            raise ValueError(f"Duplicate correlation_id: {correlation_id}")
        for artifact_root in workspace.get("artifact_roots", []):
            if artifact_root in seen_artifact_roots:
                raise ValueError(f"Artifact root reused across workspaces: {artifact_root}")
            if ".." in artifact_root.replace("\\", "/").split("/"):
                raise ValueError(f"Artifact root cannot traverse directories: {artifact_root}")
            seen_artifact_roots.add(artifact_root)
        seen_workspace_ids.add(workspace_id)
        seen_correlation_ids.add(correlation_id)
    return workspaces


def export_workbench_manifest(workspaces: List[Dict[str, Any]]) -> Dict[str, Any]:
    assert_workspaces_isolated(workspaces)
    return {
        "manifest_id": make_id("AIGC-WORKBENCH"),
        "created_at": utc_now(),
        "workspace_count": len(workspaces),
        "workspaces": workspaces,
        "cross_workspace_mutable_state_allowed": False,
        "external_action_performed": False,
    }
