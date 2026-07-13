from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from src.core.pr_dependency_graph_drift import load_platform_snapshot
from src.core.pr_platform_snapshot_refresh import (
    PlatformSnapshotRefreshError,
    build_refresh_bundle,
    validate_refresh_bundle,
    write_refresh_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = Path(
    'governance/evolution/pr_platform_snapshot_2026_07_12T142738Z.json'
)


def test_complete_snapshot_writes_one_review_bundle(tmp_path: Path) -> None:
    result = build_refresh_bundle(
        ROOT,
        SNAPSHOT_PATH,
        evaluated_at='2026-07-12T16:00:00Z',
    )
    bundle = result['bundle']
    validate_refresh_bundle(ROOT, bundle)

    assert bundle['request_receipt_conclusion'] == 'COMPLETE'
    assert bundle['bundle_conclusion'] == 'CURRENT_WITH_DECLARED_EXCLUSIONS'
    assert bundle['drift_receipt_id'] is not None
    assert bundle['artifacts']['graph_drift_receipt']['present'] is True

    output = write_refresh_bundle(result, tmp_path)
    expected = {
        'platform_snapshot.json',
        'snapshot_request_receipt.json',
        'graph_drift_receipt.json',
        'refresh_bundle.json',
    }
    assert {path.name for path in output.iterdir()} == expected

    for artifact in bundle['artifacts'].values():
        if artifact['present']:
            content = (output / artifact['path']).read_bytes()
            assert sha256(content).hexdigest() == artifact['sha256']

    persisted = json.loads(
        (output / 'refresh_bundle.json').read_text(encoding='utf-8')
    )
    assert persisted == bundle


def test_bundle_identity_is_stable_inside_freshness_window() -> None:
    first = build_refresh_bundle(
        ROOT,
        SNAPSHOT_PATH,
        evaluated_at='2026-07-12T15:30:00Z',
    )
    second = build_refresh_bundle(
        ROOT,
        SNAPSHOT_PATH,
        evaluated_at='2026-07-12T16:00:00Z',
    )

    assert first['bundle']['bundle_id'] == second['bundle']['bundle_id']
    assert first['bundle']['created_at'] != second['bundle']['created_at']
    assert (
        first['bundle']['artifacts']['snapshot_request_receipt']['sha256']
        != second['bundle']['artifacts']['snapshot_request_receipt']['sha256']
    )


def test_stale_snapshot_blocks_drift_evaluation(tmp_path: Path) -> None:
    result = build_refresh_bundle(
        ROOT,
        SNAPSHOT_PATH,
        evaluated_at='2026-07-12T16:40:00Z',
    )
    bundle = result['bundle']
    validate_refresh_bundle(ROOT, bundle)

    assert bundle['request_receipt_conclusion'] == 'INCOMPLETE'
    assert bundle['bundle_conclusion'] == 'SNAPSHOT_INCOMPLETE'
    assert bundle['drift_receipt_id'] is None
    assert result['graph_drift_receipt'] is None

    output = write_refresh_bundle(result, tmp_path)
    assert not (output / 'graph_drift_receipt.json').exists()
    assert (output / 'snapshot_request_receipt.json').exists()


def test_complete_snapshot_with_head_change_reports_drift(tmp_path: Path) -> None:
    snapshot = deepcopy(load_platform_snapshot(ROOT, SNAPSHOT_PATH))
    pr_74 = next(
        pr for pr in snapshot['pull_requests']
        if pr['change_id'] == 'AIGC-PR-74'
    )
    pr_74['head_revision'] = '0' * 40
    changed_path = tmp_path / 'changed-snapshot.json'
    changed_path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )

    result = build_refresh_bundle(
        ROOT,
        changed_path,
        evaluated_at='2026-07-12T16:00:00Z',
    )

    assert result['bundle']['request_receipt_conclusion'] == 'COMPLETE'
    assert result['bundle']['bundle_conclusion'] == 'DRIFT_DETECTED'
    assert any(
        finding['code'] == 'HEAD_REVISION_CHANGED'
        and finding['change_id'] == 'AIGC-PR-74'
        for finding in result['graph_drift_receipt']['findings']
    )


def test_incomplete_bundle_cannot_claim_drift_artifact() -> None:
    result = build_refresh_bundle(
        ROOT,
        SNAPSHOT_PATH,
        evaluated_at='2026-07-12T16:40:00Z',
    )
    invalid = deepcopy(result['bundle'])
    invalid['artifacts']['graph_drift_receipt'] = {
        'path': 'graph_drift_receipt.json',
        'present': True,
        'sha256': '0' * 64,
    }

    with pytest.raises(PlatformSnapshotRefreshError):
        validate_refresh_bundle(ROOT, invalid)
