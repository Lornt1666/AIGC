from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.core.stacked_dependency_sync import (
    StackedDependencySyncError,
    canonical_receipt_digest,
    load_dependency_sync_receipt,
    receipt_id_for_digest,
    validate_dependency_sync_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = (
    ROOT
    / "governance"
    / "evolution"
    / "production_deployment_dependency_sync_receipt_v1.json"
)


def _refresh_integrity(receipt: dict[str, object]) -> None:
    digest = canonical_receipt_digest(receipt)
    receipt["receipt_digest"] = digest
    receipt["receipt_id"] = receipt_id_for_digest(digest)


def test_committed_dependency_receipt_is_strict_and_self_authenticating() -> None:
    receipt = load_dependency_sync_receipt(RECEIPT)

    assert receipt["upstream"]["pull_request"] == 98
    assert receipt["downstream"]["pull_request"] == 99
    assert receipt["downstream"]["dependency_parent_head"] == receipt["upstream"][
        "head"
    ]
    assert receipt["alignment"]["behind_by"] == 0
    assert receipt["evidence"]["tests_passed"] == 449
    assert receipt["safety"]["external_action_performed"] is False


def test_dependency_receipt_detects_content_tampering() -> None:
    receipt = load_dependency_sync_receipt(RECEIPT)
    tampered = deepcopy(receipt)
    tampered["evidence"]["tests_passed"] = 450

    with pytest.raises(StackedDependencySyncError, match="digest does not match"):
        validate_dependency_sync_receipt(tampered)


def test_dependency_parent_must_equal_the_recorded_upstream_head() -> None:
    receipt = load_dependency_sync_receipt(RECEIPT)
    forged = deepcopy(receipt)
    forged["downstream"]["dependency_parent_head"] = "a" * 40
    _refresh_integrity(forged)

    with pytest.raises(StackedDependencySyncError, match="exact recorded upstream head"):
        validate_dependency_sync_receipt(forged)


def test_receipt_rejects_unknown_fields_and_nondeterministic_path_order() -> None:
    receipt = load_dependency_sync_receipt(RECEIPT)

    unknown = deepcopy(receipt)
    unknown["forged_authority"] = True
    with pytest.raises(StackedDependencySyncError, match="Additional properties"):
        validate_dependency_sync_receipt(unknown)

    unsorted = deepcopy(receipt)
    unsorted["alignment"]["imported_paths"] = list(
        reversed(unsorted["alignment"]["imported_paths"])
    )
    _refresh_integrity(unsorted)
    with pytest.raises(StackedDependencySyncError, match="lexicographically sorted"):
        validate_dependency_sync_receipt(unsorted)
