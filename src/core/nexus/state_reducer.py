from __future__ import annotations

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.epistemic.models import ArtifactState
from src.domain.nexus.contracts import ExecutionReceipt


class ConcurrencyConflict(ValueError):
    pass


class ReconciliationRequired(ValueError):
    pass


def assert_parent_state(state: ArtifactState, parent_state_hash: str) -> None:
    observed = canonical_sha256(state)
    if observed != parent_state_hash:
        raise ConcurrencyConflict(
            f"stale parent state: expected {parent_state_hash}, observed {observed}"
        )


def reduce_observed_state(state: ArtifactState, receipt: ExecutionReceipt) -> ArtifactState:
    """Advance canonical artifact state only from a confirmed successful receipt.

    Failed/not-started/cancelled/timed-out attempts do not prove a new artifact state and
    therefore leave canonical state unchanged. Partial or indeterminate execution cannot
    be represented faithfully by the current ArtifactState schema, so it must stop at a
    reconciliation boundary until a reconciliation ChangeSet produces a new confirmed
    receipt. Resource-specific reducers may later project proven receipt semantics behind
    separately reviewed adapters.
    """
    assert_parent_state(state, receipt.parent_state_hash)

    if receipt.execution_status in {"partially_applied", "indeterminate"}:
        raise ReconciliationRequired(
            "partial/indeterminate receipt requires a reconciliation ChangeSet before canonical state may advance"
        )

    if receipt.execution_status in {"not_started", "failed", "cancelled", "timed_out"}:
        return state

    if receipt.execution_status != "succeeded":
        raise ValueError(f"unsupported execution status: {receipt.execution_status}")

    return state.model_copy(
        update={
            "revision": state.revision + 1,
            "parent_state_hash": canonical_sha256(state),
        }
    )
