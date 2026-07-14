from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, directory: str) -> dict[str, object]:
    return json.loads((ROOT / directory / name).read_text(encoding="utf-8"))


def validate(value: dict[str, object], schema_name: str) -> None:
    schema = load(schema_name, "schemas")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(value))
    assert not errors, [error.message for error in errors]


def test_threat_model_is_strict_and_review_pending() -> None:
    threat_model = load("production_threat_model.json", "config")
    validate(threat_model, "production_threat_model.schema.json")

    assert threat_model["status"] == "DRAFT_REVIEW_REQUIRED"
    assert threat_model["review_requirements"]["review_status"] == "PENDING"
    assert threat_model["authority"]["defensive_testing_authorized"] is True
    assert threat_model["authority"]["third_party_testing_authorized"] is False
    assert threat_model["authority"]["production_testing_authorized"] is False
    assert threat_model["external_action_performed"] is False

    threats = threat_model["threats"]
    threat_ids = [item["threat_id"] for item in threats]
    assert len(threat_ids) == len(set(threat_ids))
    assert any(item["severity"] == "critical" for item in threats)
    assert any(
        item["verification_status"] == "INDEPENDENT_REVIEW_REQUIRED"
        for item in threats
    )
    assert all(
        boundary["default_decision"] == "DENY"
        for boundary in threat_model["trust_boundaries"]
    )


def test_privacy_register_blocks_public_onboarding_and_raw_collection() -> None:
    register = load("production_privacy_impact_register.json", "config")
    validate(register, "production_privacy_impact_register.schema.json")

    assert register["status"] == "DRAFT_REVIEW_REQUIRED"
    assert register["public_onboarding_allowed"] is False
    assert register["processing_controls"]["request_body_logging"] is False
    assert register["processing_controls"]["query_value_logging"] is False
    assert register["processing_controls"]["raw_token_persistence"] is False
    assert register["processing_controls"]["raw_provider_claim_persistence"] is False
    assert register["processing_controls"]["human_review_for_external_sharing"] is True
    assert register["rights_procedures"]["status"] == "INCOMPLETE"
    assert register["legal_review"]["status"] == "PENDING"
    assert register["external_action_performed"] is False


def test_privacy_categories_are_default_deny_and_minimum_necessary() -> None:
    register = load("production_privacy_impact_register.json", "config")

    assert all(item["minimum_necessary"] is True for item in register["purposes"])
    assert all(
        item["legal_basis_status"] == "COUNSEL_REVIEW_REQUIRED"
        for item in register["purposes"]
    )
    assert all(item["raw_logging_allowed"] is False for item in register["data_categories"])
    assert all(
        item["external_sharing_default"] is False
        for item in register["data_categories"]
    )
    assert any(
        item["classification"] == "restricted"
        for item in register["data_categories"]
    )
