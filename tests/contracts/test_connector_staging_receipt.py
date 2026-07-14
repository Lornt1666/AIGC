from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]


def validator() -> Draft202012Validator:
    schema = json.loads(
        (ROOT / "schemas" / "connector_staging_receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def passing_receipt() -> dict[str, object]:
    return {
        "contract_id": "AIGC-CONNECTOR-STAGING-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "CSR-" + "A" * 24,
        "environment": "isolated_staging",
        "exact_revision": "a" * 40,
        "connector_id": "github",
        "platform": "GitHub",
        "official_api_verified": True,
        "terms_review_approved": True,
        "authentication_mode": "github_app",
        "least_privilege_scopes": ["metadata:read", "issues:write"],
        "secret_reference": (
            "gcp_secret://approved-project/aigc-github-app/1"
        ),
        "secret_access_audit_observed": True,
        "approved_test_destination": "github-test://owner/repository",
        "checks": {
            "read_only_operation": True,
            "dry_run_write_preparation": True,
            "approval_gated_test_write": True,
            "destination_allowlist": True,
            "duplicate_prevention": True,
            "idempotency_conflict_denial": True,
            "rate_limit_behavior": True,
            "credential_revocation": True,
            "credential_rotation": True,
            "adapter_disable": True,
            "provider_outage_fail_closed": True,
            "redaction_review": True,
        },
        "production_account_used": False,
        "raw_secret_logged": False,
        "raw_secret_persisted": False,
        "result": "PASS",
        "reason_codes": [],
        "operator_review_required": True,
        "created_at": "2026-07-14T06:00:00+00:00",
        "external_action_performed": False,
    }


def test_complete_connector_staging_receipt_can_pass() -> None:
    assert not list(validator().iter_errors(passing_receipt()))


def test_missing_terms_secret_audit_or_check_fails() -> None:
    terms = passing_receipt()
    terms["terms_review_approved"] = False
    audit = passing_receipt()
    audit["secret_access_audit_observed"] = False
    check = passing_receipt()
    check["checks"]["credential_revocation"] = False

    assert list(validator().iter_errors(terms))
    assert list(validator().iter_errors(audit))
    assert list(validator().iter_errors(check))


def test_failed_receipt_requires_reason_and_unknown_fields_fail() -> None:
    failed = passing_receipt()
    failed["result"] = "FAIL"
    failed["checks"]["provider_outage_fail_closed"] = False
    failed["reason_codes"] = []
    injected = passing_receipt()
    injected["claimed_production_ready"] = True

    assert list(validator().iter_errors(failed))
    assert list(validator().iter_errors(injected))
