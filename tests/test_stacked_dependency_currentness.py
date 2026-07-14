from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.core.stacked_dependency_sync import (
    StackedDependencySyncError,
    evaluate_pull_request_dependency_currentness,
    load_dependency_sync_receipt,
    load_github_event_dependency_currentness,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = (
    ROOT
    / "governance"
    / "evolution"
    / "production_deployment_dependency_sync_receipt_v1.json"
)


def _event(
    *,
    base_branch: str = "codex/production-connectors-secret-broker-v1",
    base_sha: str = "f5ffdb4aaf60b09f40b1a8840ef5e5b62b49a141",
    head_branch: str = "codex/production-deployment-baseline-v1",
    head_sha: str = "b" * 40,
    pull_request: int = 99,
) -> dict[str, object]:
    return {
        "number": pull_request,
        "pull_request": {
            "number": pull_request,
            "head": {"ref": head_branch, "sha": head_sha},
            "base": {"ref": base_branch, "sha": base_sha},
        },
    }


def test_current_stacked_pull_request_matches_the_recorded_upstream() -> None:
    result = evaluate_pull_request_dependency_currentness(
        load_dependency_sync_receipt(RECEIPT),
        _event(),
    )

    assert result.state == "CURRENT_STACK"
    assert result.current_stack is True
    assert result.reason_codes == ()
    assert result.base_head == "f5ffdb4aaf60b09f40b1a8840ef5e5b62b49a141"


def test_upstream_head_movement_fails_closed_as_dependency_drift() -> None:
    result = evaluate_pull_request_dependency_currentness(
        load_dependency_sync_receipt(RECEIPT),
        _event(base_sha="c" * 40),
    )

    assert result.state == "STALE_STACK"
    assert result.current_stack is False
    assert result.reason_codes == ("UPSTREAM_HEAD_DRIFT",)


def test_wrong_pull_request_or_branch_cannot_reuse_the_receipt() -> None:
    result = evaluate_pull_request_dependency_currentness(
        load_dependency_sync_receipt(RECEIPT),
        _event(pull_request=100, head_branch="codex/other-deployment-train"),
    )

    assert result.state == "STALE_STACK"
    assert result.current_stack is False
    assert result.reason_codes == (
        "PULL_REQUEST_MISMATCH",
        "DOWNSTREAM_BRANCH_MISMATCH",
    )


def test_combined_main_ci_is_recognized_but_not_claimed_as_current_stack() -> None:
    result = evaluate_pull_request_dependency_currentness(
        load_dependency_sync_receipt(RECEIPT),
        _event(base_branch="main", base_sha="d" * 40),
    )

    assert result.state == "COMBINED_MAIN_EVALUATION"
    assert result.current_stack is False
    assert result.reason_codes == ()


def test_malformed_github_event_is_rejected() -> None:
    with pytest.raises(StackedDependencySyncError, match="pull_request.head"):
        evaluate_pull_request_dependency_currentness(
            load_dependency_sync_receipt(RECEIPT),
            {"number": 99, "pull_request": {"base": {}}},
        )


def test_current_github_actions_event_matches_the_dependency_contract() -> None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        pytest.skip("GitHub event currentness gate runs inside GitHub Actions")

    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    if not isinstance(event, dict) or "pull_request" not in event:
        pytest.skip("Current workflow event is not a pull-request event")

    result = load_github_event_dependency_currentness(
        event_path=event_path,
        receipt_path=RECEIPT,
    )

    assert result.state in {"CURRENT_STACK", "COMBINED_MAIN_EVALUATION"}
    if result.state == "CURRENT_STACK":
        assert result.current_stack is True
