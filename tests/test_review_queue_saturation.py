from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.core.pr_dependency_graph import load_graph
from src.core.pr_dependency_graph_drift import load_platform_snapshot
from src.core.pr_platform_snapshot_request import load_snapshot_request
from src.core.review_queue_saturation import (
    ReviewQueueSaturationError,
    evaluate_saturation,
    load_policy,
    validate_policy,
    validate_receipt,
    write_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
EVALUATED_AT = '2026-07-13T16:30:45Z'


def _inputs() -> tuple[dict, dict, dict, dict]:
    return (
        load_policy(ROOT),
        load_snapshot_request(ROOT),
        load_graph(ROOT),
        load_platform_snapshot(ROOT),
    )


def test_current_review_queue_is_saturated_and_review_support_only() -> None:
    policy, request, graph, snapshot = _inputs()
    receipt = evaluate_saturation(
        policy,
        request,
        graph,
        snapshot,
        evaluated_at=EVALUATED_AT,
    )
    validate_receipt(ROOT, receipt)

    assert receipt['snapshot_completeness_conclusion'] == 'COMPLETE'
    assert receipt['open_decision_gates'] == ['AIGC-ISSUE-66']
    assert receipt['open_coordination_gates'] == ['AIGC-ISSUE-76']
    assert receipt['open_governance_gates'] == ['AIGC-ISSUE-66', 'AIGC-ISSUE-76']
    assert receipt['counts'] == {
        'open_critical_path_item_count': 4,
        'open_review_train_count': 13,
        'open_decision_gate_count': 1,
        'open_coordination_gate_count': 1,
        'open_governance_gate_count': 2,
    }
    assert receipt['excess'] == {
        'critical_path_item_count': 2,
        'review_train_count': 3,
    }
    assert receipt['saturation_reasons'] == [
        'CRITICAL_PATH_LIMIT_EXCEEDED',
        'REVIEW_TRAIN_LIMIT_EXCEEDED',
    ]
    assert receipt['saturated'] is True
    assert receipt['mode'] == 'REVIEW_SUPPORT_ONLY'
    assert receipt['new_independent_implementation_train_allowed'] is False
    assert 'EXISTING_CRITICAL_TRAIN_CORRECTION' in receipt['allowed_actions']
    assert 'NEW_INDEPENDENT_IMPLEMENTATION_TRAIN' in receipt['prohibited_actions']


def test_receipt_identity_is_stable_across_time_only_changes() -> None:
    policy, request, graph, snapshot = _inputs()
    first = evaluate_saturation(
        policy,
        request,
        graph,
        snapshot,
        evaluated_at='2026-07-13T16:30:45Z',
    )
    second = evaluate_saturation(
        policy,
        request,
        graph,
        snapshot,
        evaluated_at='2026-07-13T16:31:45Z',
    )
    assert first['receipt_id'] == second['receipt_id']
    assert first['snapshot_age_seconds'] != second['snapshot_age_seconds']


def test_relaxed_limits_allow_one_bounded_implementation_train() -> None:
    policy, request, graph, snapshot = _inputs()
    relaxed = deepcopy(policy)
    relaxed['maximum_open_critical_path_items'] = 20
    relaxed['maximum_open_review_trains'] = 20

    receipt = evaluate_saturation(
        relaxed,
        request,
        graph,
        snapshot,
        evaluated_at=EVALUATED_AT,
    )
    validate_receipt(ROOT, receipt)

    assert receipt['saturated'] is False
    assert receipt['mode'] == 'BOUNDED_IMPLEMENTATION_ALLOWED'
    assert receipt['new_independent_implementation_train_allowed'] is True
    assert receipt['saturation_reasons'] == []
    assert receipt['excess'] == {
        'critical_path_item_count': 0,
        'review_train_count': 0,
    }
    assert 'ONE_BOUNDED_IMPLEMENTATION_TRAIN' in receipt['allowed_actions']
    assert 'NEW_INDEPENDENT_IMPLEMENTATION_TRAIN' not in receipt['prohibited_actions']


def test_stale_snapshot_fails_before_saturation_is_claimed() -> None:
    policy, request, graph, snapshot = _inputs()
    with pytest.raises(ReviewQueueSaturationError, match='SNAPSHOT_TOO_OLD'):
        evaluate_saturation(
            policy,
            request,
            graph,
            snapshot,
            evaluated_at='2026-07-13T18:30:45Z',
        )


def test_false_implementation_permission_is_rejected() -> None:
    policy, request, graph, snapshot = _inputs()
    receipt = evaluate_saturation(
        policy,
        request,
        graph,
        snapshot,
        evaluated_at=EVALUATED_AT,
    )
    receipt['new_independent_implementation_train_allowed'] = True
    with pytest.raises(ReviewQueueSaturationError, match='implementation permission'):
        validate_receipt(ROOT, receipt)


def test_invalid_threshold_order_fails_closed() -> None:
    policy = deepcopy(load_policy(ROOT))
    policy['maximum_open_critical_path_items'] = 11
    policy['maximum_open_review_trains'] = 10
    with pytest.raises(ReviewQueueSaturationError, match='cannot exceed'):
        validate_policy(policy)


def test_receipt_is_writeable(tmp_path: Path) -> None:
    policy, request, graph, snapshot = _inputs()
    receipt = evaluate_saturation(
        policy,
        request,
        graph,
        snapshot,
        evaluated_at=EVALUATED_AT,
    )
    output = tmp_path / 'review_queue_saturation_receipt.json'
    write_receipt(receipt, output)
    assert json.loads(output.read_text(encoding='utf-8')) == receipt
