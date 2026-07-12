from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.core.pr_dependency_graph import load_graph, validate_graph
from src.core.pr_dependency_graph_drift import (
    SNAPSHOT_PATH,
    load_platform_snapshot,
    validate_platform_snapshot,
)

REQUEST_PATH = Path('governance/evolution/pr_platform_snapshot_request_v1.json')
REQUEST_SCHEMA_PATH = Path('governance/schemas/evolution/pr_platform_snapshot_request.schema.json')
RECEIPT_SCHEMA_PATH = Path('governance/schemas/evolution/pr_platform_snapshot_request_receipt.schema.json')


class PlatformSnapshotRequestError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def _validate_schema(instance: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        details = '; '.join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise PlatformSnapshotRequestError(details)


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + '+00:00' if value.endswith('Z') else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise PlatformSnapshotRequestError(f'invalid timestamp: {value}') from exc
    if parsed.tzinfo is None:
        raise PlatformSnapshotRequestError(f'timestamp must include a timezone: {value}')
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def validate_snapshot_request(request: Mapping[str, Any]) -> None:
    if request['operator_id'].strip() == '':
        raise PlatformSnapshotRequestError('operator_id must not be blank')
    if set(request['include_pull_request_states']) != {'OPEN'}:
        raise PlatformSnapshotRequestError('v1 snapshot requests must inspect all open pull requests')
    if set(request['exclusion_policy']['allowed_reasons']) != {'SELF_REFERENTIAL_IMPLEMENTATION_CHANGE'}:
        raise PlatformSnapshotRequestError('v1 permits only the self-referential implementation exclusion')
    if request['exclusion_policy']['maximum_exclusions'] > 1:
        raise PlatformSnapshotRequestError('v1 permits at most one declared exclusion')


def load_snapshot_request(
    project_root: str | Path,
    request_path: str | Path = REQUEST_PATH,
) -> dict[str, Any]:
    root = Path(project_root)
    request = _load(root / request_path)
    schema = _load(root / REQUEST_SCHEMA_PATH)
    _validate_schema(request, schema)
    validate_snapshot_request(request)
    return request


def validate_request_receipt(project_root: str | Path, receipt: Mapping[str, Any]) -> None:
    schema = _load(Path(project_root) / RECEIPT_SCHEMA_PATH)
    _validate_schema(receipt, schema)
    if receipt['finding_count'] != len(receipt['findings']):
        raise PlatformSnapshotRequestError('finding_count does not match findings')


def evaluate_snapshot_request(
    request: Mapping[str, Any],
    graph: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    evaluated_at: str,
) -> dict[str, Any]:
    validate_snapshot_request(request)
    validate_graph(graph)
    validate_platform_snapshot(snapshot)

    evaluated = _parse_timestamp(evaluated_at)
    observed = _parse_timestamp(snapshot['observed_at'])
    snapshot_age_seconds = int((evaluated - observed).total_seconds())
    findings: list[dict[str, Any]] = []

    def add(code: str, **details: Any) -> None:
        findings.append({'severity': 'BLOCKING', 'code': code, **details})

    if request['repository'] != graph['repository']:
        add('REQUEST_REPOSITORY_DIFFERS_FROM_GRAPH', expected=request['repository'], observed=graph['repository'])
    if request['repository'] != snapshot['repository']:
        add('REQUEST_REPOSITORY_DIFFERS_FROM_SNAPSHOT', expected=request['repository'], observed=snapshot['repository'])
    if request['graph_id'] != graph['graph_id']:
        add('REQUEST_GRAPH_ID_CHANGED', expected=request['graph_id'], observed=graph['graph_id'])
    if request['allowed_source'] != snapshot['source']:
        add('SNAPSHOT_SOURCE_NOT_ALLOWED', expected=request['allowed_source'], observed=snapshot['source'])
    if graph['current_main_revision'] != snapshot['current_main_revision']:
        add(
            'SNAPSHOT_MAIN_DIFFERS_FROM_GRAPH',
            expected=graph['current_main_revision'],
            observed=snapshot['current_main_revision'],
        )

    if snapshot_age_seconds < 0:
        add('EVALUATION_PRECEDES_OBSERVATION', field='snapshot_age_seconds')
    elif snapshot_age_seconds > request['maximum_snapshot_age_seconds']:
        add(
            'SNAPSHOT_TOO_OLD',
            field='snapshot_age_seconds',
            expected=request['maximum_snapshot_age_seconds'],
        )

    required_pr_fields = set(request['required_pull_request_fields'])
    allowed_pr_states = set(request['include_pull_request_states'])
    for pull_request in snapshot['pull_requests']:
        missing = sorted(required_pr_fields - set(pull_request))
        for field in missing:
            add('PULL_REQUEST_FIELD_MISSING', change_id=pull_request.get('change_id', '<unknown>'), field=field)
        if pull_request.get('state') not in allowed_pr_states:
            add(
                'PULL_REQUEST_STATE_NOT_REQUESTED',
                change_id=pull_request.get('change_id', '<unknown>'),
                expected=sorted(allowed_pr_states),
                observed=pull_request.get('state'),
            )

    required_gate_fields = set(request['required_decision_gate_fields'])
    observed_gate_ids = {gate['change_id'] for gate in snapshot['decision_gates']}
    for gate in snapshot['decision_gates']:
        missing = sorted(required_gate_fields - set(gate))
        for field in missing:
            add('DECISION_GATE_FIELD_MISSING', change_id=gate.get('change_id', '<unknown>'), field=field)
    for change_id in request['required_decision_gates']:
        if change_id not in observed_gate_ids:
            add('REQUIRED_DECISION_GATE_MISSING', change_id=change_id)

    exclusion_policy = request['exclusion_policy']
    exclusions = snapshot['excluded_changes']
    if len(exclusions) > exclusion_policy['maximum_exclusions']:
        add(
            'EXCLUSION_LIMIT_EXCEEDED',
            expected=exclusion_policy['maximum_exclusions'],
            observed=len(exclusions),
        )
    allowed_reasons = set(exclusion_policy['allowed_reasons'])
    for exclusion in exclusions:
        if exclusion['reason'] not in allowed_reasons:
            add(
                'EXCLUSION_REASON_NOT_ALLOWED',
                change_id=exclusion['change_id'],
                expected=sorted(allowed_reasons),
                observed=exclusion['reason'],
            )
        if exclusion_policy['require_notes'] and not exclusion['notes'].strip():
            add('EXCLUSION_NOTES_MISSING', change_id=exclusion['change_id'])

    graph_ids = {node['change_id'] for node in graph['nodes']}
    platform_ids = {
        change['change_id']
        for change in list(snapshot['pull_requests']) + list(snapshot['decision_gates'])
    }
    exclusion_ids = {entry['change_id'] for entry in exclusions}
    for change_id in sorted(graph_ids - platform_ids):
        add('GRAPH_CHANGE_MISSING_FROM_SNAPSHOT', change_id=change_id)
    for change_id in sorted(platform_ids - graph_ids - exclusion_ids):
        add('UNDECLARED_PLATFORM_CHANGE', change_id=change_id)

    conclusion = 'INCOMPLETE' if findings else 'COMPLETE'
    payload = {
        'request_id': request['request_id'],
        'request_digest': sha256(_canonical(request)).hexdigest(),
        'graph_id': graph['graph_id'],
        'graph_digest': sha256(_canonical(graph)).hexdigest(),
        'platform_snapshot_id': snapshot['snapshot_id'],
        'platform_snapshot_digest': sha256(_canonical(snapshot)).hexdigest(),
        'evaluated_at': _format_timestamp(evaluated),
        'observed_at': _format_timestamp(observed),
        'snapshot_age_seconds': snapshot_age_seconds,
        'maximum_snapshot_age_seconds': request['maximum_snapshot_age_seconds'],
        'pull_request_count': len(snapshot['pull_requests']),
        'decision_gate_count': len(snapshot['decision_gates']),
        'excluded_change_count': len(exclusions),
        'finding_count': len(findings),
        'findings': findings,
        'conclusion': conclusion,
        'operator_review_required': True,
        'automatic_mutation_allowed': False,
        'external_action_performed': False,
    }
    identity_payload = {
        key: value
        for key, value in payload.items()
        if key not in {'evaluated_at', 'snapshot_age_seconds'}
    }
    identity = sha256(_canonical(identity_payload)).hexdigest().upper()[:16]
    return {'receipt_id': f'AIGC-PR-SNAPSHOT-REQUEST-{identity}', **payload}


def evaluate_repository_snapshot_request(
    project_root: str | Path,
    request_path: str | Path = REQUEST_PATH,
    snapshot_path: str | Path = SNAPSHOT_PATH,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    request = load_snapshot_request(root, request_path)
    graph = load_graph(root)
    snapshot = load_platform_snapshot(root, snapshot_path)
    timestamp = evaluated_at or _format_timestamp(datetime.now(timezone.utc))
    receipt = evaluate_snapshot_request(request, graph, snapshot, timestamp)
    validate_request_receipt(root, receipt)
    return receipt


def write_receipt(receipt: Mapping[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
