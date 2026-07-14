from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "identity_staging_configuration_decision.schema.json"
CONFIG_PATH = ROOT / "config" / "identity_staging_configuration_decision.json"


def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def canonical_decision() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def review_ready_decision() -> dict[str, object]:
    value = canonical_decision()
    value["decision_status"] = "READY_FOR_OPERATOR_REVIEW"
    value["provider"]["project_reference"] = "gcp_project://aigc-stage-12345"
    value["provider"]["authorized_origins"] = [
        "https://staging.aigc.example"
    ]
    value["provider"]["authorized_redirect_uris"] = [
        "https://staging.aigc.example/auth/callback"
    ]
    value["workload_identity"]["service_account_reference"] = (
        "gcp_service_account://aigc-stage-12345/"
        "aigc-identity-staging@aigc-stage-12345.iam.gserviceaccount.com"
    )
    value["session_pepper"]["secret_reference"] = (
        "gcp_secret://aigc-stage-12345/aigc-session-pepper/1"
    )
    value["test_subject"]["subject_reference"] = (
        "staging_subject://operator-controlled-identity-001"
    )
    value["unresolved_identifiers"] = []
    return value


def errors(value: dict[str, object]) -> list[object]:
    return list(validator().iter_errors(value))


def test_canonical_decision_is_deferred_and_default_deny() -> None:
    value = canonical_decision()

    assert errors(value) == []
    assert value["decision_status"] == "DEFERRED_IDENTIFIERS"
    assert value["unresolved_identifiers"]
    assert value["operator_review_required"] is True
    assert value["automatic_apply_allowed"] is False
    assert value["external_action_performed"] is False

    authority = value["authority"]
    assert authority["contract_implementation_authorized"] is True
    assert authority["offline_validation_authorized"] is True
    assert all(
        granted is False
        for key, granted in authority.items()
        if key
        not in {
            "contract_implementation_authorized",
            "offline_validation_authorized",
        }
    )


def test_fully_resolved_packet_can_be_review_ready_without_authority() -> None:
    value = review_ready_decision()

    assert errors(value) == []
    assert value["decision_status"] == "READY_FOR_OPERATOR_REVIEW"
    assert value["unresolved_identifiers"] == []
    assert value["automatic_apply_allowed"] is False
    assert value["authority"]["identity_platform_configuration_authorized"] is False
    assert value["authority"]["session_pepper_access_authorized"] is False
    assert value["authority"]["test_subject_onboarding_authorized"] is False
    assert value["authority"]["staging_sign_in_authorized"] is False
    assert value["authority"]["production_identity_activation_authorized"] is False


def test_review_ready_requires_every_identifier_and_redirect_boundary() -> None:
    fields = (
        ("provider", "project_reference", None),
        ("provider", "authorized_origins", []),
        ("provider", "authorized_redirect_uris", []),
        ("workload_identity", "service_account_reference", None),
        ("session_pepper", "secret_reference", None),
        ("test_subject", "subject_reference", None),
    )

    for section, field, missing_value in fields:
        value = review_ready_decision()
        value[section][field] = missing_value
        assert errors(value), f"{section}.{field} unexpectedly remained valid"

    unresolved = review_ready_decision()
    unresolved["unresolved_identifiers"] = ["staging_project_reference"]
    assert errors(unresolved)


def test_live_authority_cannot_be_granted_by_this_contract() -> None:
    live_authorities = (
        "staging_configuration_review_authorized",
        "identity_platform_configuration_authorized",
        "workload_identity_creation_authorized",
        "session_pepper_creation_authorized",
        "session_pepper_access_authorized",
        "test_subject_onboarding_authorized",
        "staging_sign_in_authorized",
        "production_identity_activation_authorized",
        "production_deployment_authorized",
    )

    for authority_name in live_authorities:
        value = review_ready_decision()
        value["authority"][authority_name] = True
        assert errors(value), f"{authority_name} unexpectedly became valid"


def test_secret_and_workload_identity_boundaries_are_immutable() -> None:
    symbolic_secret = review_ready_decision()
    symbolic_secret["session_pepper"]["secret_reference"] = (
        "gcp_secret://aigc-stage-12345/aigc-session-pepper/latest"
    )
    long_lived_key = review_ready_decision()
    long_lived_key["workload_identity"]["long_lived_key_allowed"] = True
    exported_key = review_ready_decision()
    exported_key["workload_identity"]["service_account_key_export_allowed"] = True

    assert errors(symbolic_secret)
    assert errors(long_lived_key)
    assert errors(exported_key)


def test_test_subject_and_origin_boundaries_fail_closed() -> None:
    production_user = review_ready_decision()
    production_user["test_subject"]["production_user_allowed"] = True
    public_registration = review_ready_decision()
    public_registration["test_subject"]["public_registration_allowed"] = True
    profile_persistence = review_ready_decision()
    profile_persistence["test_subject"]["profile_data_persistence_allowed"] = True
    wildcard = review_ready_decision()
    wildcard["provider"]["wildcard_origins_allowed"] = True
    insecure_origin = review_ready_decision()
    insecure_origin["provider"]["authorized_origins"] = ["http://staging.invalid"]

    assert errors(production_user)
    assert errors(public_registration)
    assert errors(profile_persistence)
    assert errors(wildcard)
    assert errors(insecure_origin)


def test_deferred_state_requires_unresolved_identifiers_and_unknown_fields_fail() -> None:
    empty_deferred = canonical_decision()
    empty_deferred["unresolved_identifiers"] = []
    injected = canonical_decision()
    injected["provider"]["configuration_applied"] = True
    mutated = copy.deepcopy(canonical_decision())
    mutated["automatic_apply_allowed"] = True

    assert errors(empty_deferred)
    assert errors(injected)
    assert errors(mutated)
