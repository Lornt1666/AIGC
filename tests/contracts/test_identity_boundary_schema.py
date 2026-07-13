from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]


def validator(name: str) -> Draft202012Validator:
    schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def valid_context() -> dict[str, object]:
    return {
        "contract_id": "AIGC-PIBC-001",
        "contract_version": "1.0.0",
        "principal_id": "principal-a",
        "provider_class": "LOCAL_DEVELOPMENT",
        "provider_binding_id": "aigc-local-development-fixture-v1",
        "membership_id": "membership-a",
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "roles": ["operator"],
        "granted_scopes": ["project:read"],
        "session_id": "session-a",
        "session_state": "ACTIVE",
        "identity_assurance": "IAL0",
        "authentication_assurance": "AAL0",
        "federation_assurance": "FAL0",
        "evidence_maturity": "EA1_SCHEMA_VALID",
        "runtime_authority": "LOCAL_SIMULATION",
        "exact_revision": "LOCAL_UNVERIFIED",
        "issued_at": "2026-07-11T18:00:00+00:00",
        "expires_at": "2027-07-11T00:00:00+00:00",
        "evidence_ids": [
            "EVID-PRINCIPAL-A",
            "EVID-MEMBERSHIP-A",
            "EVID-LOCAL-SESSION-0000000000000000",
        ],
        "verified": True,
        "external_action_performed": False,
    }


def valid_denial_receipt() -> dict[str, object]:
    return {
        "contract_id": "AIGC-PIBC-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "IDR-" + "A" * 24,
        "request_digest": "b" * 64,
        "replay_key_digest": "c" * 64,
        "result": "DENY",
        "reason_codes": ["LOCAL_PROVIDER_PROHIBITED"],
        "provider_class": "LOCAL_DEVELOPMENT",
        "provider_binding_id": "aigc-local-development-fixture-v1",
        "assertion_id": "assertion-a",
        "principal_id": "principal-a",
        "membership_id": "membership-a",
        "session_id": "session-a",
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "identity_assurance": "IAL0",
        "authentication_assurance": "AAL0",
        "federation_assurance": "FAL0",
        "evidence_maturity": "EA1_SCHEMA_VALID",
        "runtime_authority": "LOCAL_SIMULATION",
        "exact_revision": "a" * 40,
        "evidence_ids": ["EVID-PRINCIPAL-A"],
        "production_mode": True,
        "created_at": "2026-07-13T20:00:00+00:00",
        "expires_at": "2027-07-11T00:00:00+00:00",
        "retention_class": "IDENTITY_EVIDENCE_90D",
        "operator_review_required": True,
        "state_changed": False,
        "external_action_performed": False,
    }


def test_normalized_context_schema_accepts_minimum_necessary_context() -> None:
    assert not list(
        validator("identity_boundary.schema.json").iter_errors(valid_context())
    )


def test_normalized_context_schema_rejects_unknown_and_raw_sensitive_fields() -> None:
    value = valid_context()
    value["access_token"] = "must-not-enter-domain"
    assert list(
        validator("identity_boundary.schema.json").iter_errors(value)
    )


def test_receipt_schema_accepts_redacted_denial() -> None:
    assert not list(
        validator("identity_evidence_receipt.schema.json").iter_errors(
            valid_denial_receipt()
        )
    )


def test_receipt_schema_requires_reason_for_denial() -> None:
    value = valid_denial_receipt()
    value["reason_codes"] = []
    assert list(
        validator("identity_evidence_receipt.schema.json").iter_errors(value)
    )


def test_permit_receipt_prohibits_denial_reasons() -> None:
    value = valid_denial_receipt()
    value["result"] = "PERMIT"
    assert list(
        validator("identity_evidence_receipt.schema.json").iter_errors(value)
    )
