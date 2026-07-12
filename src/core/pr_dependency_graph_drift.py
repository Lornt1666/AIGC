from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.core.pr_dependency_graph import load_graph, validate_graph

SNAPSHOT_PATH = Path('governance/evolution/pr_platform_snapshot_2026_07_12T142738Z.json')
SNAPSHOT_SCHEMA_PATH = Path('governance/schemas/evolution/pr_platform_snapshot.schema.json')


class DependencyGraphDriftError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def _validate_schema(instance: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        details = '; '.join(
            f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise DependencyGraphDriftError(details)


def validate_platform_snapshot(snapshot: Mapping[str, Any]) -> None:
    pull_requests = list(snapshot['pull_requests'])
    decision_gates = list(snapshot['decision_gates'])
    exclusions = list(snapshot['excluded_changes'])
    all_changes = pull_requests + decision_gates

    by_id = {change['change_id']: change for change in all_changes}
    if len(by_id) != len(all_changes):
        raise DependencyGraphDriftError('platform change_id values must be unique')

    for change in all_changes:
        if change['number'] != int(change['change_id'].rsplit('-', 1)[1]):
            raise DependencyGraphDriftError(f"{change['change_id']} number does not match its identifier")

    exclusion_ids = [entry['change_id'] for entry in exclusions]
    if len(set(exclusion_ids)) != len(exclusion_ids):
        raise DependencyGraphDriftError('excluded change_id values must be unique')
    for entry in exclusions:
        change = by_id.get(entry['change_id'])
        if change is None:
            raise DependencyGraphDriftError(
                f"excluded change {entry['change_id']} is not present in the platform snapshot"
            )
        if change.get('branch') != entry['branch']:
            raise DependencyGraphDriftError(
                f"excluded change {entry['change_id']} branch does not match the platform snapshot"
            )


def load_platform_snapshot(
    project_root: str | Path,
    snapshot_path: str | Path = SNAPSHOT_PATH,
) -> dict[str, Any]:
    root = Path(project_root)
    snapshot = _load(root / snapshot_path)
    schema = _load(root / SNAPSHOT_SCHEMA_PATH)
    _validate_schema(snapshot, schema)
    validate_platform_snapshot(snapshot)
    return snapshot


def _expected_platform_state(graph_state: str) -> tuple[str, bool | None]:
    if graph_state == 'OPEN_DRAFT':
        return 'OPEN', True
    if graph_state == 'OPEN':
        return 'OPEN', False
    if graph_state == 'CLOSED':
        return 'CLOSED', None
    if graph_state == 'MERGED':
        return 'MERGED', None
    raise DependencyGraphDriftError(f'unsupported graph state: {graph_state}')


def _snapshot_state(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in snapshot.items() if key != 'observed_at'}


def evaluate_drift(
    graph: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    validate_graph(graph)
    validate_platform_snapshot(snapshot)

    if graph['repository'] != snapshot['repository']:
        raise DependencyGraphDriftError('graph and platform snapshot repositories differ')

    graph_by_id = {node['change_id']: node for node in graph['nodes']}
    platform_changes = list(snapshot['pull_requests']) + list(snapshot['decision_gates'])
    platform_by_id = {change['change_id']: change for change in platform_changes}
    exclusions = {entry['change_id']: entry for entry in snapshot['excluded_changes']}

    findings: list[dict[str, Any]] = []

    if graph['current_main_revision'] != snapshot['current_main_revision']:
        findings.append({
            'change_id': 'AIGC-REPOSITORY-MAIN',
            'severity': 'BLOCKING',
            'code': 'MAIN_REVISION_CHANGED',
            'expected': graph['current_main_revision'],
            'observed': snapshot['current_main_revision'],
        })

    for change_id, node in sorted(graph_by_id.items()):
        observed = platform_by_id.get(change_id)
        if observed is None:
            findings.append({
                'change_id': change_id,
                'severity': 'BLOCKING',
                'code': 'GRAPH_NODE_MISSING_FROM_PLATFORM',
            })
            continue

        expected_kind = 'PULL_REQUEST' if change_id.startswith('AIGC-PR-') else 'DECISION_GATE'
        observed_kind = 'PULL_REQUEST' if 'head_revision' in observed else 'DECISION_GATE'
        if expected_kind != observed_kind:
            findings.append({
                'change_id': change_id,
                'severity': 'BLOCKING',
                'code': 'CHANGE_KIND_CHANGED',
                'expected': expected_kind,
                'observed': observed_kind,
            })
            continue

        if node['kind'] == 'PULL_REQUEST':
            expected_state, expected_draft = _expected_platform_state(node['state'])
            if observed['state'] != expected_state:
                findings.append({
                    'change_id': change_id,
                    'severity': 'BLOCKING',
                    'code': 'STATE_CHANGED',
                    'expected': expected_state,
                    'observed': observed['state'],
                })
            if expected_draft is not None and observed['draft'] != expected_draft:
                findings.append({
                    'change_id': change_id,
                    'severity': 'BLOCKING',
                    'code': 'DRAFT_STATE_CHANGED',
                    'expected': expected_draft,
                    'observed': observed['draft'],
                })
            for field, code, severity in (
                ('branch', 'BRANCH_CHANGED', 'BLOCKING'),
                ('base_revision', 'BASE_REVISION_CHANGED', 'BLOCKING'),
                ('head_revision', 'HEAD_REVISION_CHANGED', 'BLOCKING'),
                ('mergeable', 'MERGEABILITY_CHANGED', 'ADVISORY'),
            ):
                if node[field] != observed[field]:
                    findings.append({
                        'change_id': change_id,
                        'severity': severity,
                        'code': code,
                        'expected': node[field],
                        'observed': observed[field],
                    })
        elif node['state'] != observed['state']:
            findings.append({
                'change_id': change_id,
                'severity': 'BLOCKING',
                'code': 'DECISION_GATE_STATE_CHANGED',
                'expected': node['state'],
                'observed': observed['state'],
            })

    for change_id, observed in sorted(platform_by_id.items()):
        if change_id in graph_by_id:
            continue
        exclusion = exclusions.get(change_id)
        if exclusion is not None:
            findings.append({
                'change_id': change_id,
                'severity': 'ADVISORY',
                'code': 'SELF_CHANGE_TRACKED_EXTERNALLY',
                'branch': exclusion['branch'],
                'reason': exclusion['reason'],
            })
            continue
        findings.append({
            'change_id': change_id,
            'severity': 'BLOCKING',
            'code': 'PLATFORM_CHANGE_NOT_IN_GRAPH',
            'observed_state': observed['state'],
        })

    blocking = [finding for finding in findings if finding['severity'] == 'BLOCKING']
    advisory = [finding for finding in findings if finding['severity'] == 'ADVISORY']

    graph_digest = sha256(_canonical(graph)).hexdigest()
    snapshot_digest = sha256(_canonical(snapshot)).hexdigest()
    snapshot_state_digest = sha256(_canonical(_snapshot_state(snapshot))).hexdigest()

    if blocking:
        conclusion = 'DRIFT_DETECTED'
    elif advisory:
        conclusion = 'CURRENT_WITH_DECLARED_EXCLUSIONS'
    else:
        conclusion = 'CURRENT'

    payload = {
        'graph_id': graph['graph_id'],
        'graph_digest': graph_digest,
        'platform_snapshot_id': snapshot['snapshot_id'],
        'platform_snapshot_digest': snapshot_digest,
        'platform_state_digest': snapshot_state_digest,
        'observed_at': snapshot['observed_at'],
        'current_main_revision': snapshot['current_main_revision'],
        'graph_node_count': len(graph_by_id),
        'platform_change_count': len(platform_by_id),
        'excluded_change_count': len(exclusions),
        'blocking_finding_count': len(blocking),
        'advisory_finding_count': len(advisory),
        'findings': findings,
        'conclusion': conclusion,
        'operator_review_required': True,
        'automatic_mutation_allowed': False,
        'external_action_performed': False,
    }
    identity_payload = {
        key: value
        for key, value in payload.items()
        if key not in {'observed_at', 'platform_snapshot_digest'}
    }
    identity = sha256(_canonical(identity_payload)).hexdigest().upper()[:16]
    return {'receipt_id': f'AIGC-PR-GRAPH-DRIFT-{identity}', **payload}


def evaluate_repository_drift(
    project_root: str | Path,
    snapshot_path: str | Path = SNAPSHOT_PATH,
) -> dict[str, Any]:
    root = Path(project_root)
    graph = load_graph(root)
    snapshot = load_platform_snapshot(root, snapshot_path)
    return evaluate_drift(graph, snapshot)


def write_receipt(receipt: Mapping[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
