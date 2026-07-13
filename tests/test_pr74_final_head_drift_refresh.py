from __future__ import annotations

from pathlib import Path

from src.core.pr_dependency_graph import load_graph
from src.core.pr_dependency_graph_drift import evaluate_drift, load_platform_snapshot
from src.core.pr_platform_snapshot_refresh import build_refresh_bundle
from src.core.pr_platform_snapshot_request import load_snapshot_request
from src.core.review_queue_saturation import evaluate_saturation, load_policy


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = Path(
    'governance/evolution/pr_platform_snapshot_2026_07_13T142507Z.json'
)
EVALUATED_AT = '2026-07-13T14:25:08Z'
FINAL_PR74_HEAD = 'db59f635cdab05b43c49dde828ee720e5bc61bea'


def _evidence() -> tuple[dict, dict]:
    return load_graph(ROOT), load_platform_snapshot(ROOT, SNAPSHOT_PATH)


def test_fresh_snapshot_detects_pr74_final_head_drift() -> None:
    graph, snapshot = _evidence()
    observed_pr74 = next(
        item for item in snapshot['pull_requests']
        if item['change_id'] == 'AIGC-PR-74'
    )

    assert observed_pr74['head_revision'] == FINAL_PR74_HEAD

    receipt = evaluate_drift(graph, snapshot)

    assert receipt['conclusion'] == 'DRIFT_DETECTED'
    assert receipt['blocking_finding_count'] == 1
    assert receipt['advisory_finding_count'] == 1
    assert any(
        finding['change_id'] == 'AIGC-PR-74'
        and finding['code'] == 'HEAD_REVISION_CHANGED'
        and finding['observed'] == FINAL_PR74_HEAD
        for finding in receipt['findings']
    )
    assert any(
        finding['change_id'] == 'AIGC-PR-75'
        and finding['code'] == 'SELF_CHANGE_TRACKED_EXTERNALLY'
        for finding in receipt['findings']
    )


def test_fresh_snapshot_builds_complete_drift_bundle() -> None:
    result = build_refresh_bundle(
        ROOT,
        SNAPSHOT_PATH,
        evaluated_at=EVALUATED_AT,
    )

    bundle = result['bundle']
    request_receipt = result['snapshot_request_receipt']
    drift_receipt = result['graph_drift_receipt']

    assert request_receipt['conclusion'] == 'COMPLETE'
    assert request_receipt['snapshot_age_seconds'] == 1
    assert request_receipt['coordination_gate_count'] == 0
    assert request_receipt['governance_gate_count'] == 1
    assert drift_receipt is not None
    assert drift_receipt['conclusion'] == 'DRIFT_DETECTED'
    assert bundle['bundle_conclusion'] == 'DRIFT_DETECTED'
    assert bundle['artifacts']['platform_snapshot']['present'] is True
    assert bundle['artifacts']['snapshot_request_receipt']['present'] is True
    assert bundle['artifacts']['graph_drift_receipt']['present'] is True
    assert bundle['automatic_mutation_allowed'] is False
    assert bundle['external_action_performed'] is False


def test_fresh_snapshot_keeps_review_queue_in_support_only_mode() -> None:
    graph, snapshot = _evidence()
    receipt = evaluate_saturation(
        load_policy(ROOT),
        load_snapshot_request(ROOT),
        graph,
        snapshot,
        evaluated_at=EVALUATED_AT,
    )

    assert receipt['counts'] == {
        'open_critical_path_item_count': 4,
        'open_review_train_count': 13,
        'open_decision_gate_count': 1,
        'open_coordination_gate_count': 0,
        'open_governance_gate_count': 1,
    }
    assert receipt['mode'] == 'REVIEW_SUPPORT_ONLY'
    assert receipt['new_independent_implementation_train_allowed'] is False
    assert 'EVIDENCE_REFRESH' in receipt['allowed_actions']
    assert 'NEW_INDEPENDENT_IMPLEMENTATION_TRAIN' in receipt['prohibited_actions']
    assert receipt['automatic_mutation_allowed'] is False
    assert receipt['external_action_performed'] is False
