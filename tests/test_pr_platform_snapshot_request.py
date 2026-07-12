from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from src.core.pr_dependency_graph import load_graph
from src.core.pr_dependency_graph_drift import load_platform_snapshot
from src.core.pr_platform_snapshot_request import (
    evaluate_snapshot_request,
    load_snapshot_request,
    validate_request_receipt,
    write_receipt,
)

ROOT = Path(__file__).resolve().parents[1]


def _current() -> tuple[dict, dict, dict]:
    return load_snapshot_request(ROOT), load_graph(ROOT), load_platform_snapshot(ROOT)


def test_current_snapshot_satisfies_request_and_receipt_contract(tmp_path: Path) -> None:
    request, graph, snapshot = _current()
    receipt = evaluate_snapshot_request(request, graph, snapshot, '2026-07-12T16:00:00Z')
    validate_request_receipt(ROOT, receipt)

    assert receipt['conclusion'] == 'COMPLETE'
    assert receipt['finding_count'] == 0
    assert receipt['pull_request_count'] == 13
    assert receipt['decision_gate_count'] == 1
    assert receipt['excluded_change_count'] == 1
    assert receipt['snapshot_age_seconds'] == 5542
    assert receipt['maximum_snapshot_age_seconds'] == 7200

    output = tmp_path / 'snapshot-request-receipt.json'
    write_receipt(receipt, output)
    assert json.loads(output.read_text(encoding='utf-8')) == receipt


def test_receipt_identity_is_stable_while_snapshot_remains_complete() -> None:
    request, graph, snapshot = _current()
    first = evaluate_snapshot_request(request, graph, snapshot, '2026-07-12T15:30:00Z')
    second = evaluate_snapshot_request(request, graph, snapshot, '2026-07-12T16:00:00Z')

    assert first['conclusion'] == second['conclusion'] == 'COMPLETE'
    assert first['receipt_id'] == second['receipt_id']
    assert first['snapshot_age_seconds'] != second['snapshot_age_seconds']


def test_snapshot_older_than_request_limit_fails_closed() -> None:
    request, graph, snapshot = _current()
    receipt = evaluate_snapshot_request(request, graph, snapshot, '2026-07-12T16:40:00Z')
    validate_request_receipt(ROOT, receipt)

    assert receipt['conclusion'] == 'INCOMPLETE'
    assert any(finding['code'] == 'SNAPSHOT_TOO_OLD' for finding in receipt['findings'])


def test_missing_required_decision_gate_fails_closed() -> None:
    request, graph, snapshot = _current()
    changed = deepcopy(snapshot)
    changed['decision_gates'] = []

    receipt = evaluate_snapshot_request(request, graph, changed, '2026-07-12T16:00:00Z')

    assert receipt['conclusion'] == 'INCOMPLETE'
    assert any(
        finding['code'] == 'REQUIRED_DECISION_GATE_MISSING'
        and finding['change_id'] == 'AIGC-ISSUE-66'
        for finding in receipt['findings']
    )


def test_exclusion_count_above_request_limit_fails_closed() -> None:
    request, graph, snapshot = _current()
    changed = deepcopy(snapshot)
    pr_74 = next(pr for pr in changed['pull_requests'] if pr['change_id'] == 'AIGC-PR-74')
    changed['excluded_changes'].append({
        'change_id': 'AIGC-PR-74',
        'reason': 'SELF_REFERENTIAL_IMPLEMENTATION_CHANGE',
        'branch': pr_74['branch'],
        'notes': 'Synthetic negative test for exclusion cardinality.',
    })

    receipt = evaluate_snapshot_request(request, graph, changed, '2026-07-12T16:00:00Z')

    assert receipt['conclusion'] == 'INCOMPLETE'
    assert any(finding['code'] == 'EXCLUSION_LIMIT_EXCEEDED' for finding in receipt['findings'])
