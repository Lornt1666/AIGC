from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.core.pr_dependency_graph import load_graph
from src.core.pr_dependency_graph_drift import (
    evaluate_drift,
    load_platform_snapshot,
)
from src.core.pr_platform_snapshot_request import (
    evaluate_snapshot_request,
    load_snapshot_request,
    validate_request_receipt,
)

BUNDLE_SCHEMA_PATH = Path(
    'governance/schemas/evolution/pr_platform_snapshot_refresh_bundle.schema.json'
)
DEFAULT_OUTPUT_ROOT = Path('reports/artifacts/pr_platform_snapshot_refresh')


class PlatformSnapshotRefreshError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')


def _render(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n'
    ).encode('utf-8')


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _validate_schema(instance: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = '; '.join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f'{error.message}'
            for error in errors
        )
        raise PlatformSnapshotRefreshError(details)


def validate_refresh_bundle(
    project_root: str | Path,
    bundle: Mapping[str, Any],
) -> None:
    schema = _load(Path(project_root) / BUNDLE_SCHEMA_PATH)
    _validate_schema(bundle, schema)

    incomplete = bundle['bundle_conclusion'] == 'SNAPSHOT_INCOMPLETE'
    drift_artifact = bundle['artifacts']['graph_drift_receipt']

    if incomplete:
        if bundle['request_receipt_conclusion'] != 'INCOMPLETE':
            raise PlatformSnapshotRefreshError(
                'incomplete bundle must contain an INCOMPLETE request receipt'
            )
        if bundle['drift_receipt_id'] is not None or bundle['drift_conclusion'] is not None:
            raise PlatformSnapshotRefreshError(
                'incomplete bundle must not contain drift evidence'
            )
        if drift_artifact['present'] or drift_artifact['sha256'] is not None:
            raise PlatformSnapshotRefreshError(
                'incomplete bundle must mark the drift artifact absent'
            )
    else:
        if bundle['request_receipt_conclusion'] != 'COMPLETE':
            raise PlatformSnapshotRefreshError(
                'drift evaluation requires a COMPLETE request receipt'
            )
        if bundle['drift_receipt_id'] is None or bundle['drift_conclusion'] is None:
            raise PlatformSnapshotRefreshError(
                'complete acquisition must include drift evidence'
            )
        if not drift_artifact['present'] or drift_artifact['sha256'] is None:
            raise PlatformSnapshotRefreshError(
                'complete acquisition must include the drift artifact'
            )
        if bundle['bundle_conclusion'] != bundle['drift_conclusion']:
            raise PlatformSnapshotRefreshError(
                'bundle and drift conclusions must agree'
            )


def build_refresh_bundle(
    project_root: str | Path,
    snapshot_path: str | Path,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    request = load_snapshot_request(root)
    graph = load_graph(root)
    snapshot = load_platform_snapshot(root, snapshot_path)

    timestamp = evaluated_at or _format_timestamp(datetime.now(timezone.utc))
    request_receipt = evaluate_snapshot_request(
        request,
        graph,
        snapshot,
        timestamp,
    )
    validate_request_receipt(root, request_receipt)

    drift_receipt: dict[str, Any] | None = None
    if request_receipt['conclusion'] == 'COMPLETE':
        drift_receipt = evaluate_drift(graph, snapshot)
        bundle_conclusion = drift_receipt['conclusion']
    else:
        bundle_conclusion = 'SNAPSHOT_INCOMPLETE'

    snapshot_bytes = _render(snapshot)
    request_receipt_bytes = _render(request_receipt)
    drift_receipt_bytes = (
        _render(drift_receipt)
        if drift_receipt is not None
        else None
    )

    artifact_records = {
        'platform_snapshot': {
            'path': 'platform_snapshot.json',
            'present': True,
            'sha256': sha256(snapshot_bytes).hexdigest(),
        },
        'snapshot_request_receipt': {
            'path': 'snapshot_request_receipt.json',
            'present': True,
            'sha256': sha256(request_receipt_bytes).hexdigest(),
        },
        'graph_drift_receipt': {
            'path': 'graph_drift_receipt.json',
            'present': drift_receipt_bytes is not None,
            'sha256': (
                sha256(drift_receipt_bytes).hexdigest()
                if drift_receipt_bytes is not None
                else None
            ),
        },
    }

    identity_payload = {
        'repository': request['repository'],
        'current_main_revision': snapshot['current_main_revision'],
        'request_receipt_id': request_receipt['receipt_id'],
        'graph_id': graph['graph_id'],
        'platform_snapshot_id': snapshot['snapshot_id'],
        'platform_snapshot_digest': sha256(_canonical(snapshot)).hexdigest(),
        'drift_receipt_id': (
            drift_receipt['receipt_id']
            if drift_receipt is not None
            else None
        ),
        'bundle_conclusion': bundle_conclusion,
    }
    identity = sha256(_canonical(identity_payload)).hexdigest().upper()[:16]

    bundle = {
        'bundle_id': f'AIGC-PR-SNAPSHOT-REFRESH-{identity}',
        'schema_version': '1.0.0',
        'created_at': request_receipt['evaluated_at'],
        'repository': request['repository'],
        'current_main_revision': snapshot['current_main_revision'],
        'request_id': request['request_id'],
        'request_receipt_id': request_receipt['receipt_id'],
        'request_receipt_conclusion': request_receipt['conclusion'],
        'graph_id': graph['graph_id'],
        'platform_snapshot_id': snapshot['snapshot_id'],
        'platform_snapshot_digest': sha256(_canonical(snapshot)).hexdigest(),
        'drift_receipt_id': (
            drift_receipt['receipt_id']
            if drift_receipt is not None
            else None
        ),
        'drift_conclusion': (
            drift_receipt['conclusion']
            if drift_receipt is not None
            else None
        ),
        'bundle_conclusion': bundle_conclusion,
        'artifacts': artifact_records,
        'operator_review_required': True,
        'automatic_mutation_allowed': False,
        'external_action_performed': False,
    }
    validate_refresh_bundle(root, bundle)

    return {
        'bundle': bundle,
        'platform_snapshot': snapshot,
        'snapshot_request_receipt': request_receipt,
        'graph_drift_receipt': drift_receipt,
    }


def write_refresh_bundle(
    result: Mapping[str, Any],
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> Path:
    bundle = result['bundle']
    output_directory = Path(output_root) / bundle['bundle_id']
    output_directory.mkdir(parents=True, exist_ok=False)

    files = {
        'platform_snapshot.json': result['platform_snapshot'],
        'snapshot_request_receipt.json': result['snapshot_request_receipt'],
        'refresh_bundle.json': bundle,
    }
    if result['graph_drift_receipt'] is not None:
        files['graph_drift_receipt.json'] = result['graph_drift_receipt']

    for name, value in files.items():
        (output_directory / name).write_bytes(_render(value))

    return output_directory
