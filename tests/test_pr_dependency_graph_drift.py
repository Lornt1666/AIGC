from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from src.core.pr_dependency_graph import load_graph
from src.core.pr_dependency_graph_drift import (
    evaluate_drift,
    load_platform_snapshot,
    write_receipt,
)

ROOT = Path(__file__).resolve().parents[1]


def _current() -> tuple[dict, dict]:
    return load_graph(ROOT), load_platform_snapshot(ROOT)


def test_current_platform_snapshot_reports_pr74_drift_and_declared_self_exclusion() -> None:
    graph, snapshot = _current()
    receipt = evaluate_drift(graph, snapshot)

    assert receipt['conclusion'] == 'DRIFT_DETECTED'
    assert receipt['graph_node_count'] == 13
    assert receipt['platform_change_count'] == 14
    assert receipt['excluded_change_count'] == 1
    assert receipt['blocking_finding_count'] == 1
    assert receipt['advisory_finding_count'] == 1
    assert any(
        finding['change_id'] == 'AIGC-PR-74'
        and finding['code'] == 'HEAD_REVISION_CHANGED'
        for finding in receipt['findings']
    )
    assert any(
        finding == {
            'change_id': 'AIGC-PR-75',
            'severity': 'ADVISORY',
            'code': 'SELF_CHANGE_TRACKED_EXTERNALLY',
            'branch': 'codex/pr-dependency-graph-v1',
            'reason': 'SELF_REFERENTIAL_IMPLEMENTATION_CHANGE',
        }
        for finding in receipt['findings']
    )


def test_receipt_identity_ignores_observation_time_and_is_writeable(tmp_path: Path) -> None:
    graph, snapshot = _current()
    first = evaluate_drift(graph, snapshot)
    later = deepcopy(snapshot)
    later['observed_at'] = '2026-07-13T16:31:44Z'
    second = evaluate_drift(graph, later)

    assert first['receipt_id'] == second['receipt_id']
    assert first['platform_state_digest'] == second['platform_state_digest']
    assert first['platform_snapshot_digest'] != second['platform_snapshot_digest']

    output = tmp_path / 'drift-receipt.json'
    write_receipt(first, output)
    assert json.loads(output.read_text(encoding='utf-8')) == first


def test_head_revision_change_is_blocking_drift() -> None:
    graph, snapshot = _current()
    changed = deepcopy(snapshot)
    target = next(
        pr for pr in changed['pull_requests']
        if pr['change_id'] == 'AIGC-PR-74'
    )
    target['head_revision'] = 'f' * 40

    receipt = evaluate_drift(graph, changed)

    assert receipt['conclusion'] == 'DRIFT_DETECTED'
    assert any(
        finding['change_id'] == 'AIGC-PR-74'
        and finding['code'] == 'HEAD_REVISION_CHANGED'
        for finding in receipt['findings']
    )


def test_unregistered_platform_change_is_blocking_drift() -> None:
    graph, snapshot = _current()
    changed = deepcopy(snapshot)
    changed['pull_requests'].append({
        'change_id': 'AIGC-PR-999',
        'number': 999,
        'title': 'Unregistered change',
        'state': 'OPEN',
        'draft': True,
        'mergeable': True,
        'branch': 'codex/unregistered-change',
        'base_branch': 'main',
        'base_revision': changed['current_main_revision'],
        'head_revision': 'e' * 40,
    })

    receipt = evaluate_drift(graph, changed)

    assert receipt['conclusion'] == 'DRIFT_DETECTED'
    assert any(
        finding['change_id'] == 'AIGC-PR-999'
        and finding['code'] == 'PLATFORM_CHANGE_NOT_IN_GRAPH'
        for finding in receipt['findings']
    )


def test_missing_platform_node_is_blocking_drift() -> None:
    graph, snapshot = _current()
    changed = deepcopy(snapshot)
    changed['pull_requests'] = [
        pr for pr in changed['pull_requests']
        if pr['change_id'] != 'AIGC-PR-69'
    ]

    receipt = evaluate_drift(graph, changed)

    assert receipt['conclusion'] == 'DRIFT_DETECTED'
    assert any(
        finding['change_id'] == 'AIGC-PR-69'
        and finding['code'] == 'GRAPH_NODE_MISSING_FROM_PLATFORM'
        for finding in receipt['findings']
    )


def test_main_revision_change_is_blocking_drift() -> None:
    graph, snapshot = _current()
    changed = deepcopy(snapshot)
    changed['current_main_revision'] = 'd' * 40

    receipt = evaluate_drift(graph, changed)

    assert receipt['conclusion'] == 'DRIFT_DETECTED'
    assert any(finding['code'] == 'MAIN_REVISION_CHANGED' for finding in receipt['findings'])
