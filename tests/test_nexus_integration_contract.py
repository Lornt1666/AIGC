from datetime import datetime, timezone

import pytest

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.specialist_registry import select_specialists
from src.core.nexus.state_reducer import ConcurrencyConflict, reduce_observed_state
from src.domain.epistemic.models import ArtifactState
from src.domain.nexus.contracts import (
    ChangeSet,
    ExecutionReceipt,
    WorkOrder,
)


def _state() -> ArtifactState:
    return ArtifactState(stage="candidate", revision=1)


def test_changeset_binds_exact_parent_state_hash() -> None:
    state = _state()
    change = ChangeSet(
        change_set_id="CHG-NEXUS001",
        work_order_id="WO-NEXUS001",
        parent_state_hash=canonical_sha256(state),
        producer_agent_id="AGT-ARCHITECT",
    )
    assert change.parent_state_hash == canonical_sha256(state)


def test_reconciliation_requires_trigger_receipt() -> None:
    with pytest.raises(ValueError, match="trigger_receipt_id"):
        ChangeSet(
            change_set_id="CHG-NEXUS002",
            change_type="reconciliation",
            work_order_id="WO-NEXUS001",
            parent_state_hash="a" * 64,
            producer_agent_id="AGT-ARCHITECT",
        )


def test_stale_receipt_is_rejected_by_occ() -> None:
    state = _state()
    receipt = ExecutionReceipt(
        receipt_id="EXEC-NEXUS001",
        change_set_id="CHG-NEXUS001",
        parent_state_hash="b" * 64,
        execution_status="failed",
    )
    with pytest.raises(ConcurrencyConflict):
        reduce_observed_state(state, receipt)


def test_partial_execution_requires_reconciliation() -> None:
    with pytest.raises(ValueError, match="requires reconciliation"):
        ExecutionReceipt(
            receipt_id="EXEC-NEXUS002",
            change_set_id="CHG-NEXUS001",
            parent_state_hash="a" * 64,
            execution_status="partially_applied",
            external_action_performed=True,
            reconciliation_required=False,
        )


def test_receipt_driven_reducer_advances_revision() -> None:
    state = _state()
    receipt = ExecutionReceipt(
        receipt_id="EXEC-NEXUS003",
        change_set_id="CHG-NEXUS001",
        parent_state_hash=canonical_sha256(state),
        execution_status="succeeded",
        external_action_performed=False,
    )
    next_state = reduce_observed_state(state, receipt)
    assert next_state.revision == 2
    assert next_state.parent_state_hash == canonical_sha256(state)


def test_dynamic_specialists_are_internal_only() -> None:
    work_order = WorkOrder(
        work_order_id="WO-NEXUS002",
        objective="Build the Nexus dashboard",
        domain_tags=("software", "security", "dashboard"),
    )
    selected = select_specialists(work_order)
    ids = {item.specialist_id for item in selected}
    assert "SPC-PYTHON" in ids
    assert "SPC-SECURITY" in ids
    assert "SPC-UX" in ids
    assert all(item.external_action_allowed is False for item in selected)
