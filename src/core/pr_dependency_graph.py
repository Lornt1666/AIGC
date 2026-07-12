from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

GRAPH_PATH = Path('governance/evolution/pr_dependency_graph_v1.json')
SCHEMA_PATH = Path('governance/schemas/evolution/pr_dependency_graph.schema.json')


class DependencyGraphError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def load_graph(project_root: str | Path, graph_path: str | Path = GRAPH_PATH) -> dict[str, Any]:
    root = Path(project_root)
    graph = _load(root / graph_path)
    schema = _load(root / SCHEMA_PATH)
    errors = sorted(Draft202012Validator(schema).iter_errors(graph), key=lambda e: list(e.absolute_path))
    if errors:
        details = '; '.join(
            f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise DependencyGraphError(details)
    validate_graph(graph)
    return graph


def _topological_order(nodes: Mapping[str, Mapping[str, Any]]) -> list[str]:
    pending = {node_id: set(node['relationships']['requires']) for node_id, node in nodes.items()}
    ready = sorted(node_id for node_id, requires in pending.items() if not requires)
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for candidate in sorted(pending):
            if node_id in pending[candidate]:
                pending[candidate].remove(node_id)
                if not pending[candidate] and candidate not in order and candidate not in ready:
                    ready.append(candidate)
                    ready.sort()
    if len(order) != len(nodes):
        cycle = sorted(node_id for node_id, requires in pending.items() if requires)
        raise DependencyGraphError(f"requires graph contains a cycle involving: {', '.join(cycle)}")
    return order


def validate_graph(graph: Mapping[str, Any]) -> None:
    nodes = list(graph['nodes'])
    by_id = {node['change_id']: node for node in nodes}
    if len(by_id) != len(nodes):
        raise DependencyGraphError('change_id values must be unique')

    for node in nodes:
        node_id = node['change_id']
        if node['number'] != int(node_id.rsplit('-', 1)[1]):
            raise DependencyGraphError(f'{node_id} number does not match its identifier')
        for relation in ('requires', 'blocks', 'conflicts_with'):
            for target in node['relationships'][relation]:
                if target == node_id:
                    raise DependencyGraphError(f'{node_id} cannot {relation} itself')
                if target not in by_id:
                    raise DependencyGraphError(f'{node_id} references unknown node {target}')
        for target in node['relationships']['conflicts_with']:
            if node_id not in by_id[target]['relationships']['conflicts_with']:
                raise DependencyGraphError(f'conflict relationship must be symmetric: {node_id} <-> {target}')
        for target in node['relationships']['blocks']:
            if node_id not in by_id[target]['relationships']['requires']:
                raise DependencyGraphError(f'block relationship must be mirrored by requires: {node_id} -> {target}')

    _topological_order(by_id)


def evaluate_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    validate_graph(graph)
    by_id = {node['change_id']: node for node in graph['nodes']}
    order = _topological_order(by_id)
    current_main = graph['current_main_revision']
    stale_base: list[str] = []
    blocked: list[str] = []
    findings: list[dict[str, str]] = []

    for node_id in order:
        node = by_id[node_id]
        if node['kind'] == 'PULL_REQUEST' and node['base_revision'] != current_main:
            stale_base.append(node_id)
            findings.append({'change_id': node_id, 'severity': 'BLOCKING', 'code': 'STALE_BASE'})
        unresolved = [
            target for target in node['relationships']['requires']
            if by_id[target]['state'] not in {'MERGED', 'CLOSED'}
        ]
        if unresolved:
            blocked.append(node_id)
            findings.append({
                'change_id': node_id,
                'severity': 'BLOCKING',
                'code': 'UNSATISFIED_DEPENDENCY',
                'targets': sorted(unresolved),
            })
        if node['evidence']['state'] == 'DECISION_REQUIRED':
            blocked.append(node_id)
            findings.append({'change_id': node_id, 'severity': 'BLOCKING', 'code': 'DECISION_REQUIRED'})
        if node['relationships']['conflicts_with']:
            findings.append({
                'change_id': node_id,
                'severity': 'ADVISORY',
                'code': 'CONFLICTING_AUTHORITY',
                'targets': sorted(node['relationships']['conflicts_with']),
            })

    payload = {
        'graph_id': graph['graph_id'],
        'graph_digest': sha256(_canonical(graph)).hexdigest(),
        'snapshot_at': graph['snapshot_at'],
        'current_main_revision': current_main,
        'node_count': len(by_id),
        'dependency_edge_count': sum(len(node['relationships']['requires']) for node in graph['nodes']),
        'topological_order': order,
        'stale_base_nodes': sorted(set(stale_base)),
        'blocked_nodes': sorted(set(blocked)),
        'critical_path': [node_id for node_id in order if by_id[node_id]['criticality'] == 'CRITICAL_PATH'],
        'operator_review_queue': [node_id for node_id in order if by_id[node_id]['state'] in {'OPEN_DRAFT', 'OPEN'}],
        'findings': findings,
        'conclusion': 'VALID_WITH_BLOCKERS' if findings else 'VALID_CLEAR',
        'operator_review_required': True,
        'automatic_merge_allowed': False,
        'external_action_performed': False,
    }
    identity = sha256(_canonical(payload)).hexdigest().upper()[:16]
    return {'receipt_id': f'AIGC-PR-DEPENDENCY-{identity}', **payload}


def write_receipt(receipt: Mapping[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
