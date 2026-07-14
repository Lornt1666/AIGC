from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from src.core.identity_operational_evidence import (
    IdentityOperationalEvidenceError,
    evaluate_identity_operational_evidence,
    load_identity_platform_baseline,
)


REVISION = "a" * 40
PROJECT_REFERENCE = "gcp_project://aigc-staging-example"
NOW = datetime(2026, 7, 14, 15, 0, tzinfo=timezone.utc)


def passing_staging_receipt(
    *,
    exact_revision: str = REVISION,
    project_reference: str = PROJECT_REFERENCE,
    created_at: str = "2026-07-14T14:30:00+00:00",
) -> dict[str, object]:
    return {
        "contract_id": "AIGC-IDENTITY-PLATFORM-STAGING-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "IPR-" + "A" * 24,
        "environment": "isolated_staging",
        "exact_revision": exact_revision,
        "provider_service": "google_cloud_identity_platform",
        "project_reference": project_reference,
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
        "created_at": created_at,
        "external_action_performed": False,
    }


def test_current_baseline_reports_exact_operational_and_authority_blockers() -> None:
    evaluation = evaluate_identity_operational_evidence(
        policy=load_identity_platform_baseline(),
        exact_revision=REVISION,
        now=NOW,
    )
    receipt = evaluation.receipt

    assert receipt["status"] == "INTERNAL_ONLY"
    assert receipt["implemented_internal"] is True
    assert receipt["staging_evidence_accepted"] is False
    assert receipt["readiness_review_eligible"] is False
    assert receipt["production_complete"] is False
    assert receipt["production_activation_authorized"] is False
    assert receipt["project_reference"] is None
    assert receipt["staging_receipt_id"] is None
    assert set(receipt["unresolved_configuration"]) == {
        "IDENTITY_PLATFORM_BASELINE_PROJECT_UNBOUND",
        "IDENTITY_PLATFORM_PROJECT_REFERENCE_MISSING",
        "SESSION_PEPPER_PROJECT_UNRESOLVED",
    }
    assert "GOOGLE_SIGN_IN_OBSERVED" in receipt["missing_operational_evidence"]
    assert "JWKS_ROTATION_OBSERVED" in receipt["missing_operational_evidence"]
    assert "STAGING_RECEIPT_MISSING" in receipt["reason_codes"]
    assert set(receipt["authority_blockers"]) == {
        "PROVIDER_CONFIGURATION_UNAUTHORIZED",
        "SECRET_ACCESS_UNAUTHORIZED",
        "USER_ONBOARDING_UNAUTHORIZED",
        "PRODUCTION_IDENTITY_ACTIVATION_UNAUTHORIZED",
    }
    assert receipt["operator_review_required"] is True
    assert receipt["external_action_performed"] is False


def test_valid_receipt_can_be_accepted_without_claiming_readiness_or_activation() -> None:
    evaluation = evaluate_identity_operational_evidence(
        policy=load_identity_platform_baseline(),
        exact_revision=REVISION,
        staging_receipt=passing_staging_receipt(),
        expected_project_reference=PROJECT_REFERENCE,
        now=NOW,
    )
    receipt = evaluation.receipt

    assert receipt["status"] == "STAGING_EVIDENCE_ACCEPTED_PENDING_OPERATOR_REVIEW"
    assert receipt["staging_evidence_accepted"] is True
    assert receipt["staging_receipt_id"] == "IPR-" + "A" * 24
    assert receipt["project_reference"] == PROJECT_REFERENCE
    assert receipt["missing_operational_evidence"] == []
    assert receipt["readiness_review_eligible"] is False
    assert receipt["production_complete"] is False
    assert receipt["production_activation_authorized"] is False
    assert set(receipt["unresolved_configuration"]) == {
        "IDENTITY_PLATFORM_BASELINE_PROJECT_UNBOUND",
        "SESSION_PEPPER_PROJECT_UNRESOLVED",
    }


def test_revision_and_project_mismatch_fail_closed() -> None:
    evaluation = evaluate_identity_operational_evidence(
        policy=load_identity_platform_baseline(),
        exact_revision=REVISION,
        staging_receipt=passing_staging_receipt(
            exact_revision="b" * 40,
            project_reference="gcp_project://other-staging-project",
        ),
        expected_project_reference=PROJECT_REFERENCE,
        now=NOW,
    )

    assert evaluation.receipt["status"] == "STAGING_EVIDENCE_REJECTED"
    assert evaluation.receipt["staging_evidence_accepted"] is False
    assert "STAGING_RECEIPT_REVISION_MISMATCH" in evaluation.receipt["reason_codes"]
    assert "STAGING_RECEIPT_PROJECT_MISMATCH" in evaluation.receipt["reason_codes"]


def test_invalid_or_future_dated_receipts_fail_closed() -> None:
    invalid = passing_staging_receipt()
    invalid["production_users_used"] = True
    invalid_evaluation = evaluate_identity_operational_evidence(
        policy=load_identity_platform_baseline(),
        exact_revision=REVISION,
        staging_receipt=invalid,
        expected_project_reference=PROJECT_REFERENCE,
        now=NOW,
    )
    assert invalid_evaluation.receipt["status"] == "STAGING_EVIDENCE_REJECTED"
    assert "STAGING_RECEIPT_INVALID" in invalid_evaluation.receipt["reason_codes"]

    future_evaluation = evaluate_identity_operational_evidence(
        policy=load_identity_platform_baseline(),
        exact_revision=REVISION,
        staging_receipt=passing_staging_receipt(
            created_at="2026-07-14T15:00:01+00:00"
        ),
        expected_project_reference=PROJECT_REFERENCE,
        now=NOW,
    )
    assert future_evaluation.receipt["status"] == "STAGING_EVIDENCE_REJECTED"
    assert "STAGING_RECEIPT_FUTURE_DATED" in future_evaluation.receipt["reason_codes"]


def test_unbound_revision_and_malformed_project_reference_are_rejected() -> None:
    unbound = evaluate_identity_operational_evidence(
        policy=load_identity_platform_baseline(),
        exact_revision=None,
        staging_receipt=passing_staging_receipt(),
        expected_project_reference=PROJECT_REFERENCE,
        now=NOW,
    )
    assert unbound.receipt["exact_revision"] == "unbound"
    assert "REVISION_UNBOUND" in unbound.receipt["reason_codes"]
    assert unbound.receipt["staging_evidence_accepted"] is False

    with pytest.raises(
        IdentityOperationalEvidenceError,
        match="project reference is malformed",
    ):
        evaluate_identity_operational_evidence(
            policy=load_identity_platform_baseline(),
            exact_revision=REVISION,
            expected_project_reference="gcp_project://bad_project",
            now=NOW,
        )


def test_evaluation_identity_is_deterministic_and_input_policy_is_not_mutated() -> None:
    policy = load_identity_platform_baseline()
    original = deepcopy(policy)
    first = evaluate_identity_operational_evidence(
        policy=policy,
        exact_revision=REVISION,
        staging_receipt=passing_staging_receipt(),
        expected_project_reference=PROJECT_REFERENCE,
        now=NOW,
    )
    second = evaluate_identity_operational_evidence(
        policy=policy,
        exact_revision=REVISION,
        staging_receipt=passing_staging_receipt(),
        expected_project_reference=PROJECT_REFERENCE,
        now=NOW,
    )

    assert first.receipt["evaluation_id"] == second.receipt["evaluation_id"]
    assert policy == original
