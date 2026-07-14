from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.security.production_http_security import (
    ProductionSecurityPolicyError,
    evaluate_security_policy,
    load_security_policy,
    redact_security_event,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "production_security_privacy_baseline.json"
SCHEMA_PATH = ROOT / "schemas" / "production_security_privacy_baseline.schema.json"


def policy() -> dict[str, object]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def test_security_baseline_is_implemented_internal_not_production_complete() -> None:
    value = load_security_policy(POLICY_PATH, SCHEMA_PATH)
    evaluation = evaluate_security_policy(value)

    assert evaluation.implemented_internal is True
    assert evaluation.production_complete is False
    assert evaluation.status == "implemented_internal"
    assert set(evaluation.blocking_evidence) == {
        "staging_tls_observed",
        "edge_rate_limit_observed",
        "sbom_generated",
        "vulnerability_scan_passed",
        "incident_exercise_passed",
        "independent_review_passed",
    }
    assert set(evaluation.provisional_controls) == {
        "data_classification_register",
        "deletion_export_policy",
        "secret_rotation_procedure",
    }
    assert evaluation.enabled_production_connectors == ()
    assert evaluation.external_action_performed is False


def test_security_baseline_preserves_default_deny_and_retention_decisions() -> None:
    value = load_security_policy(POLICY_PATH, SCHEMA_PATH)

    assert value["http_security"]["cors_allowed_origins"] == []
    assert value["http_security"]["production_domain_required"] is True
    assert value["privacy"]["request_body_logging"] is False
    assert value["privacy"]["query_value_logging"] is False
    assert value["privacy"]["application_logs_online_days"] == 30
    assert value["privacy"]["identity_authorization_receipts_min_days"] == 90
    assert value["privacy"]["deployment_incident_receipts_min_days"] == 365
    assert value["secrets"]["provider"] == "google_secret_manager"
    assert value["secrets"]["raw_values_in_repository"] is False
    assert value["secrets"]["raw_values_in_logs"] is False
    assert value["identity"]["public_self_registration"] is False
    assert value["identity"]["cross_tenant_default_deny"] is True
    assert value["authority"]["secret_access_authorized"] is False
    assert value["authority"]["production_resource_changes_authorized"] is False
    assert value["authority"]["production_deployment_authorized"] is False


def test_data_classification_register_has_four_distinct_default_deny_classes() -> None:
    value = load_security_policy(POLICY_PATH, SCHEMA_PATH)
    classes = value["data_classification"]["classes"]
    names = [item["classification"] for item in classes]

    assert names == ["public", "internal", "confidential", "restricted"]
    assert len(set(names)) == 4
    assert all(item["external_sharing_default"] is False for item in classes)
    confidential = next(item for item in classes if item["classification"] == "confidential")
    restricted = next(item for item in classes if item["classification"] == "restricted")
    assert confidential["application_logging_allowed"] is False
    assert restricted["application_logging_allowed"] is False
    assert restricted["encryption_required"] is True


def test_unknown_policy_field_fails_full_schema_validation(tmp_path: Path) -> None:
    value = policy()
    value["claimed_production_complete"] = True
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ProductionSecurityPolicyError):
        load_security_policy(policy_path, SCHEMA_PATH)


def test_structured_security_event_redaction_is_recursive() -> None:
    redacted = redact_security_event(
        {
            "authorization": "Bearer must-not-survive",
            "nested": {
                "password": "must-not-survive",
                "message": "token=must-not-survive",
            },
            "safe": "kept",
        }
    )

    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert "must-not-survive" not in redacted["nested"]["message"]
    assert redacted["safe"] == "kept"
