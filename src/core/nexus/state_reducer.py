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
    """Derive the next epistemic state only from an empirical execution receipt.

    V1 intentionally does not infer external resource semantics from tool parameters.
    The reducer records receipt provenance and advances revision while preserving the
    immutable epistemic graph. Resource-specific reducers are added behind separately
    reviewed adapters.
    """
    assert_parent_state(state, receipt.parent_state_hash)

    if receipt.execution_status in {"partially_applied", "indeterminate"}:
        if not receipt.reconciliation_required:
            raise ReconciliationRequired("receipt requires reconciliation")

    return state.model_copy(
        update={
            "revision": state.revision + 1,
            "parent_state_hash": canonical_sha256(state),
        }
    )
