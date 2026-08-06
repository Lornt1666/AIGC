from __future__ import annotations

from copy import deepcopy

import pytest

from src.core.contract_validator import ContractValidationError, validate_artifact


DIGEST = "a" * 64


def valid_activation_record() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "activation_id": "activation-001",
        "connector_id": "github",
        "connector_version": "1.0.0",
        "environment": "TEST",
        "requested_capabilities": ["commit.read"],
        "manifest_sha256": DIGEST,
        "approval_digest": DIGEST,
        "policy_digest": DIGEST,
        "dependency_digest": DIGEST,
        "lifecycle_state": "READY_FOR_ACTIVATION",
        "actor_id": "operator",
        "created_at": "2026-08-06T12:00:00+00:00",
        "production_activation_authorized": False,
        "external_send_authorized": False,
        "github_mutation_authorized": False,
        "activation_sha256": DIGEST,
    }


def assert_rejected(payload: dict[str, object], expected_fragment: str) -> None:
    with pytest.raises(ContractValidationError) as exc_info:
        validate_artifact("connector_activation_record", payload)
    assert expected_fragment in str(exc_info.value)


def test_connector_activation_schema_accepts_valid_record() -> None:
    payload = valid_activation_record()
    assert validate_artifact("connector_activation_record", payload) is payload


def test_const_false_authority_flag_is_enforced() -> None:
    payload = valid_activation_record()
    payload["production_activation_authorized"] = True
    assert_rejected(payload, "False was expected")


def test_additional_properties_are_rejected() -> None:
    payload = valid_activation_record()
    payload["unexpected_authority"] = "allow"
    assert_rejected(payload, "Additional properties are not allowed")


def test_sha256_pattern_is_enforced() -> None:
    payload = valid_activation_record()
    payload["manifest_sha256"] = "not-a-digest"
    assert_rejected(payload, "does not match")


def test_unique_capabilities_are_enforced() -> None:
    payload = valid_activation_record()
    payload["requested_capabilities"] = ["commit.read", "commit.read"]
    assert_rejected(payload, "has non-unique elements")


def test_date_time_format_is_enforced() -> None:
    payload = valid_activation_record()
    payload["created_at"] = "definitely-not-a-date"
    assert_rejected(payload, "is not a 'date-time'")


def test_identifier_length_is_enforced() -> None:
    payload = valid_activation_record()
    payload["activation_id"] = "short"
    assert_rejected(payload, "is too short")


def test_validation_does_not_mutate_artifact() -> None:
    payload = valid_activation_record()
    original = deepcopy(payload)
    validate_artifact("connector_activation_record", payload)
    assert payload == original
