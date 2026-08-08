from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.core.pr_dependency_graph import DependencyGraphError, evaluate_graph, load_graph, validate_graph, write_receipt

ROOT = Path(__file__).resolve().parents[1]


def test_current_graph_is_valid_and_truthfully_blocked() -> None:
    receipt = evaluate_graph(load_graph(ROOT))
    assert receipt['conclusion'] == 'VALID_WITH_BLOCKERS'
    assert receipt['node_count'] == 13
    assert receipt['dependency_edge_count'] == 10
    assert receipt['stale_base_nodes'] == ['AIGC-PR-11', 'AIGC-PR-15', 'AIGC-PR-21']
    assert 'AIGC-PR-69' in receipt['blocked_nodes']
    assert 'AIGC-ISSUE-66' in receipt['blocked_nodes']
    assert receipt['critical_path'] == ['AIGC-ISSUE-66', 'AIGC-PR-74', 'AIGC-PR-69', 'AIGC-PR-65']


def test_receipt_is_deterministic_and_writeable(tmp_path: Path) -> None:
    graph = load_graph(ROOT)
    first = evaluate_graph(graph)
    second = evaluate_graph(graph)
    assert first == second
    output = tmp_path / 'receipt.json'
    write_receipt(first, output)
    assert json.loads(output.read_text(encoding='utf-8')) == first


def test_unknown_dependency_fails_closed() -> None:
    broken = deepcopy(load_graph(ROOT))
    broken['nodes'][0]['relationships']['requires'].append('AIGC-PR-999')
    with pytest.raises(DependencyGraphError, match='unknown node'):
        validate_graph(broken)


def test_dependency_cycle_fails_closed() -> None:
    broken = deepcopy(load_graph(ROOT))
    by_id = {node['change_id']: node for node in broken['nodes']}
    by_id['AIGC-PR-74']['relationships']['requires'].append('AIGC-PR-69')
    with pytest.raises(DependencyGraphError, match='cycle'):
        validate_graph(broken)


def test_asymmetric_conflict_fails_closed() -> None:
    broken = deepcopy(load_graph(ROOT))
    by_id = {node['change_id']: node for node in broken['nodes']}
    by_id['AIGC-PR-71']['relationships']['conflicts_with'].clear()
    with pytest.raises(DependencyGraphError, match='conflict relationship must be symmetric'):
        validate_graph(broken)
