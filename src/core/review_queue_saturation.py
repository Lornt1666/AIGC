from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.core.pr_dependency_graph import load_graph, validate_graph
from src.core.pr_dependency_graph_drift import load_platform_snapshot, validate_platform_snapshot
from src.core.pr_platform_snapshot_request import (
    evaluate_snapshot_request,
    load_snapshot_request,
    validate_request_receipt,
)

POLICY_PATH = Path('governance/evolution/review_queue_saturation_policy_v1.json')
POLICY_SCHEMA_PATH = Path('governance/schemas/evolution/review_queue_saturation_policy.schema.json')
RECEIPT_SCHEMA_PATH = Path('governance/schemas/evolution/review_queue_saturation_receipt.schema.json')


class ReviewQueueSaturationError(ValueError):
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
        raise ReviewQueueSaturationError(details)


def _timestamp(value: str | None = None) -> str:
    if value is not None:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ReviewQueueSaturationError('evaluated_at must include a timezone')
        return parsed.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def validate_policy(policy: Mapping[str, Any]) -> None:
    if policy['maximum_open_critical_path_items'] > policy['maximum_open_review_trains']:
        raise ReviewQueueSaturationError(
            'maximum_open_critical_path_items cannot exceed maximum_open_review_trains'
        )


def load_policy(
    project_root: str | Path,
    policy_path: str | Path = POLICY_PATH,
) -> dict[str, Any]:
    root = Path(project_root)
    policy = _load(root / policy_path)
    schema = _load(root / POLICY_SCHEMA_PATH)
    _validate_schema(policy, schema)
    validate_policy(policy)
    return policy


def validate_receipt(project_root: str | Path, receipt: Mapping[str, Any]) -> None:
    root = Path(project_root)
    schema = _load(root / RECEIPT_SCHEMA_PATH)
    _validate_schema(receipt, schema)

    counts = receipt['counts']
    thresholds = receipt['thresholds']
    expected_excess = {
        'critical_path_item_count': max(
            0,
            counts['open_critical_path_item_count'] - thresholds['maximum_open_critical_path_items'],
        ),
        'review_train_count': max(
            0,
            counts['open_review_train_count'] - thresholds['maximum_open_review_trains'],
        ),
    }
    if receipt['excess'] != expected_excess:
        raise ReviewQueueSaturationError('receipt excess counts do not match counts and thresholds')

    expected_reasons: list[str] = []
    if expected_excess['critical_path_item_count']:
        expected_reasons.append('CRITICAL_PATH_LIMIT_EXCEEDED')
    if expected_excess['review_train_count']:
        expected_reasons.append('REVIEW_TRAIN_LIMIT_EXCEEDED')
    if receipt['saturation_reasons'] != expected_reasons:
        raise ReviewQueueSaturationError('receipt saturation reasons do not match excess counts')

    saturated = bool(expected_reasons)
    if receipt['saturated'] is not saturated:
        raise ReviewQueueSaturationError('receipt saturated flag is inconsistent')

    expected_mode = 'REVIEW_SUPPORT_ONLY' if saturated else 'BOUNDED_IMPLEMENTATION_ALLOWED'
    if receipt['mode'] != expected_mode:
        raise ReviewQueueSaturationError('receipt mode is inconsistent with saturation state')

    expected_allowed = [
        'REVIEW_SUPPORT',
        'EVIDENCE_REFRESH',
        'DIAGNOSTIC_CORRECTION',
        'ROLLBACK_PREPARATION',
        'EXISTING_CRITICAL_TRAIN_CORRECTION',
    ]
    if not saturated:
        expected_allowed.append('ONE_BOUNDED_IMPLEMENTATION_TRAIN')
    if receipt['allowed_actions'] != expected_allowed:
        raise ReviewQueueSaturationError('receipt allowed actions are inconsistent')

    expected_prohibited = [
        'AUTOMATIC_BRANCH_REBASE',
        'AUTOMATIC_REVIEW_SUBMISSION',
        'AUTOMATIC_MERGE',
    ]
    if saturated:
        expected_prohibited.insert(0, 'NEW_INDEPENDENT_IMPLEMENTATION_TRAIN')
    if receipt['prohibited_actions'] != expected_prohibited:
        raise ReviewQueueSaturationError('receipt prohibited actions are inconsistent')

    if receipt['new_independent_implementation_train_allowed'] != (not saturated):
        raise ReviewQueueSaturationError('new implementation permission is inconsistent')


def evaluate_saturation(
    policy: Mapping[str, Any],
    request: Mapping[str, Any],
    graph: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    validate_policy(policy)
    validate_graph(graph)
    validate_platform_snapshot(snapshot)

    if policy['repository'] != graph['repository'] or policy['repository'] != snapshot['repository']:
        raise ReviewQueueSaturationError('policy, graph, and snapshot repositories differ')

    timestamp = _timestamp(evaluated_at)
    completeness = evaluate_snapshot_request(request, graph, snapshot, timestamp)
    if completeness['conclusion'] != 'COMPLETE':
        codes = ', '.join(finding['code'] for finding in completeness['findings'])
        raise ReviewQueueSaturationError(
            f'platform snapshot is not complete enough for saturation evaluation: {codes}'
        )

    open_review_trains = sorted(
        item['change_id']
        for item in snapshot['pull_requests']
        if item['state'] == 'OPEN'
    )
    open_decision_gates = sorted(
        item['change_id']
        for item in snapshot['decision_gates']
        if item['state'] == 'OPEN'
    )
    open_critical_path_items = sorted(
        node['change_id']
        for node in graph['nodes']
        if node['criticality'] == 'CRITICAL_PATH' and node['state'] in {'OPEN', 'OPEN_DRAFT'}
    )

    thresholds = {
        'maximum_open_critical_path_items': policy['maximum_open_critical_path_items'],
        'maximum_open_review_trains': policy['maximum_open_review_trains'],
    }
    counts = {
        'open_critical_path_item_count': len(open_critical_path_items),
        'open_review_train_count': len(open_review_trains),
        'open_decision_gate_count': len(open_decision_gates),
    }
    excess = {
        'critical_path_item_count': max(
            0,
            counts['open_critical_path_item_count'] - thresholds['maximum_open_critical_path_items'],
        ),
        'review_train_count': max(
            0,
            counts['open_review_train_count'] - thresholds['maximum_open_review_trains'],
        ),
    }
    reasons: list[str] = []
    if excess['critical_path_item_count']:
        reasons.append('CRITICAL_PATH_LIMIT_EXCEEDED')
    if excess['review_train_count']:
        reasons.append('REVIEW_TRAIN_LIMIT_EXCEEDED')
    saturated = bool(reasons)

    allowed_actions = [
        'REVIEW_SUPPORT',
        'EVIDENCE_REFRESH',
        'DIAGNOSTIC_CORRECTION',
        'ROLLBACK_PREPARATION',
        'EXISTING_CRITICAL_TRAIN_CORRECTION',
    ]
    if not saturated:
        allowed_actions.append('ONE_BOUNDED_IMPLEMENTATION_TRAIN')

    prohibited_actions = [
        'AUTOMATIC_BRANCH_REBASE',
        'AUTOMATIC_REVIEW_SUBMISSION',
        'AUTOMATIC_MERGE',
    ]
    if saturated:
        prohibited_actions.insert(0, 'NEW_INDEPENDENT_IMPLEMENTATION_TRAIN')

    stable_completeness = {
        key: value
        for key, value in completeness.items()
        if key not in {'evaluated_at', 'snapshot_age_seconds'}
    }
    payload = {
        'schema_version': '1.0.0',
        'repository': policy['repository'],
        'policy_id': policy['policy_id'],
        'graph_id': graph['graph_id'],
        'platform_snapshot_id': snapshot['snapshot_id'],
        'policy_digest': sha256(_canonical(policy)).hexdigest(),
        'graph_digest': sha256(_canonical(graph)).hexdigest(),
        'platform_snapshot_digest': sha256(_canonical(snapshot)).hexdigest(),
        'snapshot_completeness_receipt_id': completeness['receipt_id'],
        'snapshot_completeness_receipt_digest': sha256(_canonical(stable_completeness)).hexdigest(),
        'snapshot_completeness_conclusion': completeness['conclusion'],
        'snapshot_age_seconds': completeness['snapshot_age_seconds'],
        'open_critical_path_items': open_critical_path_items,
        'open_review_trains': open_review_trains,
        'open_decision_gates': open_decision_gates,
        'counts': counts,
        'thresholds': thresholds,
        'excess': excess,
        'saturation_reasons': reasons,
        'saturated': saturated,
        'mode': policy['saturated_mode'] if saturated else policy['normal_mode'],
        'new_independent_implementation_train_allowed': not saturated,
        'allowed_actions': allowed_actions,
        'prohibited_actions': prohibited_actions,
        'operator_override_required': policy['operator_override_required'],
        'operator_review_required': policy['operator_review_required'],
        'automatic_mutation_allowed': policy['automatic_mutation_allowed'],
        'external_action_performed': policy['external_action_performed'],
    }
    identity_payload = {
        key: value
        for key, value in payload.items()
        if key != 'snapshot_age_seconds'
    }
    identity = sha256(_canonical(identity_payload)).hexdigest().upper()[:16]
    receipt = {
        'receipt_id': f'AIGC-REVIEW-QUEUE-SATURATION-{identity}',
        'evaluated_at': timestamp,
        **payload,
    }
    return receipt


def evaluate_repository_saturation(
    project_root: str | Path,
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    request = load_snapshot_request(root)
    graph = load_graph(root)
    snapshot = load_platform_snapshot(root)
    timestamp = _timestamp(evaluated_at)
    completeness = evaluate_snapshot_request(request, graph, snapshot, timestamp)
    validate_request_receipt(root, completeness)
    receipt = evaluate_saturation(
        load_policy(root),
        request,
        graph,
        snapshot,
        evaluated_at=timestamp,
    )
    validate_receipt(root, receipt)
    return receipt


def write_receipt(receipt: Mapping[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
