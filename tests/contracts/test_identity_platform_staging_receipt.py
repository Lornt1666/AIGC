from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]


def validator() -> Draft202012Validator:
    schema = json.loads(
        (
            ROOT
            / "schemas"
            / "identity_platform_staging_receipt.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def passing_receipt() -> dict[str, object]:
    return {
        "contract_id": "AIGC-IDENTITY-PLATFORM-STAGING-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "IPR-" + "A" * 24,
        "environment": "isolated_staging",
        "exact_revision": "a" * 40,
        "provider_service": "google_cloud_identity_platform",
        "project_reference": "gcp_project://aigc-staging-example",
        "tenant_model": "single_accountable_tenant",
        "test_subject_reference": "staging_subject://operator-test-001",
        "checks": {
            "google_sign_in": True,
            "valid_signature": True,
            "wrong_signature_denied": True,
            "wrong_audience_denied": True,
            "wrong_issuer_denied": True,
            "expired_assertion_denied": True,
            "replayed_assertion_denied": True,
            "public_key_rotation": True,
            "subject_mapping": True,
            "revocation": True,
            "session_issue": True,
            "session_rotation": True,
            "logout_revocation": True,
            "restart_persistence": True,
            "cross_tenant_denied": True,
            "cross_project_denied": True,
            "provider_outage_fail_closed": True,
            "redaction_review": True,
        },
        "raw_tokens_persisted": False,
        "raw_tokens_logged": False,
        "public_self_registration_enabled": False,
        "production_users_used": False,
        "result": "PASS",
        "reason_codes": [],
        "operator_review_required": True,
        "created_at": "2026-07-14T05:00:00+00:00",
        "external_action_performed": False,
    }


def test_complete_staging_receipt_can_pass_contract() -> None:
    assert not list(validator().iter_errors(passing_receipt()))


def test_missing_check_or_production_user_fails_contract() -> None:
    missing_check = passing_receipt()
    del missing_check["checks"]["revocation"]
    production_user = passing_receipt()
    production_user["production_users_used"] = True

    assert list(validator().iter_errors(missing_check))
    assert list(validator().iter_errors(production_user))


def test_failed_receipt_requires_reason_and_unknown_fields_are_rejected() -> None:
    failed = passing_receipt()
    failed["result"] = "FAIL"
    failed["checks"]["provider_outage_fail_closed"] = False
    failed["reason_codes"] = []
    injected = passing_receipt()
    injected["claimed_production_ready"] = True

    assert list(validator().iter_errors(failed))
    assert list(validator().iter_errors(injected))
