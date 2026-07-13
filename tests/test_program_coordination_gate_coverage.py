from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.core.pr_dependency_graph import load_graph
from src.core.pr_dependency_graph_drift import (
    DependencyGraphDriftError,
    load_platform_snapshot,
    validate_platform_snapshot,
)
from src.core.pr_platform_snapshot_request import (
    evaluate_snapshot_request,
    load_snapshot_request,
    validate_request_receipt,
)
from src.core.review_queue_saturation import (
    evaluate_saturation,
    load_policy,
    validate_receipt,
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


def test_current_snapshot_requires_typed_program_coordination_gate() -> None:
    policy, request, graph, snapshot = _inputs()
    completeness = evaluate_snapshot_request(request, graph, snapshot, EVALUATED_AT)
    validate_request_receipt(ROOT, completeness)

    assert completeness['conclusion'] == 'COMPLETE'
    assert completeness['decision_gate_count'] == 1
    assert completeness['coordination_gate_count'] == 1
    assert completeness['governance_gate_count'] == 2

    receipt = evaluate_saturation(
        policy,
        request,
        graph,
        snapshot,
        evaluated_at=EVALUATED_AT,
    )
    validate_receipt(ROOT, receipt)

    assert receipt['open_decision_gates'] == ['AIGC-ISSUE-66']
    assert receipt['open_coordination_gates'] == ['AIGC-ISSUE-76']
    assert receipt['open_governance_gates'] == [
        'AIGC-ISSUE-66',
        'AIGC-ISSUE-76',
    ]
    assert receipt['counts'] == {
        'open_critical_path_item_count': 4,
        'open_review_train_count': 13,
        'open_decision_gate_count': 1,
        'open_coordination_gate_count': 1,
        'open_governance_gate_count': 2,
    }
    assert receipt['mode'] == 'REVIEW_SUPPORT_ONLY'
    assert receipt['automatic_mutation_allowed'] is False
    assert receipt['external_action_performed'] is False


def test_missing_required_coordination_gate_fails_closed() -> None:
    _, request, graph, snapshot = _inputs()
    changed = deepcopy(snapshot)
    changed['coordination_gates'] = []

    receipt = evaluate_snapshot_request(request, graph, changed, EVALUATED_AT)

    assert receipt['conclusion'] == 'INCOMPLETE'
    assert any(
        finding['code'] == 'REQUIRED_COORDINATION_GATE_MISSING'
        and finding['change_id'] == 'AIGC-ISSUE-76'
        for finding in receipt['findings']
    )


def test_current_snapshot_cannot_downgrade_coordination_contract_version() -> None:
    _, request, graph, snapshot = _inputs()
    changed = deepcopy(snapshot)
    changed['schema_version'] = '1.0.0'
    changed.pop('coordination_gates')

    receipt = evaluate_snapshot_request(request, graph, changed, EVALUATED_AT)

    assert receipt['conclusion'] == 'INCOMPLETE'
    assert any(
        finding['code'] == 'COORDINATION_GATE_SCHEMA_VERSION_REQUIRED'
        for finding in receipt['findings']
    )
    assert any(
        finding['code'] == 'REQUIRED_COORDINATION_GATE_MISSING'
        for finding in receipt['findings']
    )


def test_invalid_coordination_gate_kind_fails_closed() -> None:
    _, _, _, snapshot = _inputs()
    changed = deepcopy(snapshot)
    changed['coordination_gates'][0]['gate_kind'] = 'DECISION_GATE'

    with pytest.raises(DependencyGraphDriftError, match='unsupported coordination gate kind'):
        validate_platform_snapshot(changed)


def test_duplicate_coordination_gate_identifier_fails_closed() -> None:
    _, _, _, snapshot = _inputs()
    changed = deepcopy(snapshot)
    changed['coordination_gates'].append(deepcopy(changed['coordination_gates'][0]))

    with pytest.raises(DependencyGraphDriftError, match='change_id values must be unique'):
        validate_platform_snapshot(changed)
