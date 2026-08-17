from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.mission_os.evidence_analytics_contracts import (
    AnalyticsContractError,
    canonical_bytes,
    canonical_sha256,
    derive_aggregate_state,
    load_json,
    validate_catalog,
    validate_document,
    validate_fixture_manifest,
    validate_observation_set,
    validate_repository,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "analytics"
FIXED_NOW = datetime(2026, 8, 4, 4, 0, tzinfo=timezone.utc)


def test_repository_contract_set_validates() -> None:
    receipt = validate_repository(ROOT)
    assert receipt["schema_count"] == 6
    assert receipt["metric_count"] == 3
    assert receipt["valid_fixtures"] == 6
    assert receipt["negative_fixtures"] >= 16
    assert receipt["external_action_performed"] is False
    assert receipt["canonical_state_mutated"] is False
    assert receipt["production_activation_authorized"] is False


def test_fixture_manifest_proves_positive_and_negative_cases() -> None:
    receipt = validate_fixture_manifest(ROOT)
    assert receipt["valid_fixtures"] == 6
    assert receipt["negative_fixtures"] >= 16


def test_canonical_json_is_order_independent_and_stable() -> None:
    left = {"b": [3, 2, 1], "a": {"y": False, "x": "Ω"}}
    right = {"a": {"x": "Ω", "y": False}, "b": [3, 2, 1]}
    assert canonical_bytes(left) == canonical_bytes(right)
    assert canonical_sha256(left) == canonical_sha256(right)


def test_catalog_digest_and_unique_metric_identity_are_enforced() -> None:
    catalog = load_json(ROOT / "config" / "analytics_metric_catalog.json")
    validate_catalog(ROOT, catalog)
    duplicate = copy.deepcopy(catalog)
    duplicate["metrics"].append(copy.deepcopy(duplicate["metrics"][0]))
    digest_input = dict(duplicate)
    digest_input.pop("catalog_content_sha256")
    duplicate["catalog_content_sha256"] = canonical_sha256(digest_input)
    with pytest.raises(AnalyticsContractError, match="DUPLICATE_METRIC_ID_VERSION"):
        validate_catalog(ROOT, duplicate)


def test_every_metric_has_explicit_grain_and_denominator() -> None:
    catalog = load_json(ROOT / "config" / "analytics_metric_catalog.json")
    for metric in catalog["metrics"]:
        assert metric["grain"].strip()
        assert metric["denominator"]["expression"].strip()
        assert metric["denominator"]["eligibility"].strip()
        assert metric["binding"]["exact_repository_revision_required"] is True
        assert metric["binding"]["source_sha256_required"] is True


def test_decision_quality_calibration_remains_inactive() -> None:
    catalog = load_json(ROOT / "config" / "analytics_metric_catalog.json")
    metric = next(item for item in catalog["metrics"] if item["metric_id"] == "AIGC-METRIC-DQC")
    assert metric["activation_state"] == "INACTIVE_SAMPLE_INSUFFICIENT"
    assert metric["minimum_sample_size"] == 100
    assert metric["outcome_claim_allowed"] is False
    assert metric["autonomous_behavior_change_allowed"] is False


def test_observation_binds_definition_revision_catalog_and_source_digest() -> None:
    observation = load_json(FIXTURES / "valid_metric_observation.json")
    validate_document(ROOT, "metric_observation", observation, now=FIXED_NOW)
    assert observation["metric_version"] == "1.0.0"
    assert len(observation["exact_repository_revision"]) == 40
    assert observation["source_digests"] == [observation["source_lineage"][0]["source_sha256"]]


def test_duplicate_declared_grain_fails_closed() -> None:
    payload = load_json(FIXTURES / "duplicate_metric_observations.json")
    with pytest.raises(AnalyticsContractError, match="DUPLICATE_DECLARED_GRAIN"):
        validate_observation_set(ROOT, payload["observations"], now=FIXED_NOW)


def test_unavailable_or_stale_evidence_cannot_pass() -> None:
    for name, kind, code in [
        ("unavailable_source_healthy.json", "run_envelope", "UNAVAILABLE_SOURCE_REPORTED_HEALTHY"),
        ("stale_source_fresh.json", "lineage_reference", "STALE_SOURCE_REPORTED_FRESH"),
    ]:
        with pytest.raises(AnalyticsContractError, match=code):
            validate_document(ROOT, kind, load_json(FIXTURES / name), now=FIXED_NOW)


def test_expired_authorization_cannot_be_active_pending() -> None:
    with pytest.raises(AnalyticsContractError, match="EXPIRED_AUTHORIZATION_ACTIVE"):
        validate_document(
            ROOT,
            "entity_transition",
            load_json(FIXTURES / "expired_approval_active.json"),
            now=FIXED_NOW,
        )


def test_blocking_findings_dominate_aggregate() -> None:
    payload = load_json(FIXTURES / "blocking_finding_averaged_pass.json")
    assert derive_aggregate_state(payload["findings"]) == "FAIL"


def test_structural_evidence_cannot_be_production_proof() -> None:
    with pytest.raises(AnalyticsContractError, match="STRUCTURAL_EVIDENCE_OVERCLAIM"):
        validate_document(
            ROOT,
            "metric_observation",
            load_json(FIXTURES / "structural_evidence_as_production.json"),
            now=FIXED_NOW,
        )


def test_secret_like_and_unnecessary_personal_fields_fail_closed() -> None:
    for name, kind in [
        ("raw_secret_like_field.json", "lineage_reference"),
        ("unnecessary_personal_payload.json", "data_quality_finding"),
    ]:
        with pytest.raises(AnalyticsContractError, match="PRIVACY_FORBIDDEN_KEY"):
            validate_document(ROOT, kind, load_json(FIXTURES / name), now=FIXED_NOW)


def test_authority_invariants_are_hard_false() -> None:
    catalog = load_json(ROOT / "config" / "analytics_metric_catalog.json")
    assert catalog["production_activation_authorized"] is False
    assert catalog["external_provider_action_authorized"] is False
    assert catalog["autonomous_behavior_change_allowed"] is False
    run = load_json(FIXTURES / "valid_run_envelope.json")
    assert run["external_action_performed"] is False
    assert run["canonical_state_mutated"] is False
    assert run["production_activation_authorized"] is False
