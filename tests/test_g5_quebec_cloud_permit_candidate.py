from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from scripts.validate_quebec_cloud_authorization import AuthorizationError, validate
from scripts.verify_quebec_resource_locations import verify


ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "config" / "quebec_staging_authorization.candidate.json"
MANIFEST = ROOT / "config" / "quebec_resource_manifest.candidate.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_candidate_resource_manifest_is_quebec_customer_content_only():
    receipt = verify(load(MANIFEST))
    assert receipt["verified"] is True
    assert receipt["project_id"] == "oceanic-base-485407-i7"
    assert receipt["customer_content_quebec_region_verified"] is True
    assert receipt["strict_quebec_data_residency_verified"] is False
    assert receipt["manifest_sha256"] == "837e3337e4b80b4221976b96fb60714d46862ee702a01de93913e497c1c13335"


def test_candidate_is_valid_for_plan_gate_only():
    payload = load(AUTH)
    receipt = validate(payload, gate="plan")
    assert receipt["valid"] is True
    assert receipt["gate"] == "plan"
    assert receipt["project_id"] == "oceanic-base-485407-i7"
    assert receipt["release_sha"] == "18e886d48c57b85d8ab8115a6fb765fa6e655fc9"
    assert receipt["release_tree_sha"] == "0835d1ec8c57a279c9839bfa207038042e22ed23"
    assert receipt["resource_creation_performed"] is False
    assert receipt["deployment_performed"] is False
    assert receipt["live_model_call_performed"] is False


def test_candidate_does_not_authorize_any_consequential_action():
    authority = load(AUTH)["authority"]
    assert authority["configuration_reviewed"] is False
    assert authority["resource_creation_authorized"] is False
    assert authority["staging_deployment_authorized"] is False
    assert authority["production_activation_authorized"] is False
    assert authority["public_access_authorized"] is False
    assert authority["live_model_call_authorized"] is False
    assert authority["financial_action_authorized"] is False
    assert authority["devpost_submission_authorized"] is False


def test_staging_gate_fails_before_provider_discovery_and_cost_review():
    payload = load(AUTH)
    manifest = load(MANIFEST)
    with pytest.raises(AuthorizationError, match="reviewed monthly cost estimate"):
        validate(
            payload,
            gate="staging",
            manifest=manifest,
            now=datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc),
        )


def test_candidate_secret_versions_remain_unresolved_not_fabricated():
    refs = load(AUTH)["exact_secret_version_refs"]
    assert set(refs) == {
        "runtime_control_dsn",
        "operator_token",
        "operator_binding_key",
        "runtime_admin_token",
        "runtime_admin_binding_key",
        "judge_token",
        "judge_binding_key",
    }
    assert all(value == "" for value in refs.values())
