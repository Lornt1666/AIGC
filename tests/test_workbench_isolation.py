from __future__ import annotations

import pytest

from src.core.contract_validator import validate_artifact
from src.core.workbench_isolation import (
    assert_workspaces_isolated,
    create_parallel_workbench,
    create_work_order_workspace,
    export_workbench_manifest,
)


def test_workspace_schema_validates_and_blocks_external_action() -> None:
    workspace = create_work_order_workspace(tenant_id="OWNER-LOCAL", work_order_id="WORK-ORDER-01").to_dict()

    assert validate_artifact("work_order_workspace", workspace) == workspace
    assert workspace["external_action_performed"] is False
    assert workspace["approval_state"] == "not_approved_for_external_action"


def test_ten_job_workbench_isolated() -> None:
    workspaces = create_parallel_workbench(
        tenant_id="OWNER-LOCAL",
        work_order_ids=[f"WORK-ORDER-{index:02d}" for index in range(1, 11)],
    )
    manifest = export_workbench_manifest(workspaces)

    assert manifest["workspace_count"] == 10
    assert manifest["cross_workspace_mutable_state_allowed"] is False
    assert manifest["external_action_performed"] is False
    assert len({workspace["workspace_id"] for workspace in workspaces}) == 10
    assert len({workspace["correlation_id"] for workspace in workspaces}) == 10


def test_shared_artifact_root_is_rejected() -> None:
    workspaces = create_parallel_workbench(tenant_id="OWNER-LOCAL", work_order_ids=["A", "B"])
    workspaces[1]["artifact_roots"] = list(workspaces[0]["artifact_roots"])

    with pytest.raises(ValueError, match="Artifact root reused"):
        assert_workspaces_isolated(workspaces)


def test_workspace_cannot_approve_external_action() -> None:
    workspace = create_work_order_workspace(tenant_id="OWNER-LOCAL", work_order_id="WORK-ORDER-01").to_dict()
    workspace["approval_state"] = "approved_for_external_action"

    with pytest.raises(ValueError, match="cannot approve external action"):
        assert_workspaces_isolated([workspace])
