from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.core.github_actions_account_remediation import (
    GitHubActionsRemediationError,
    build_account_remediation_receipt,
    remediation_attestation,
    validate_account_remediation_receipt,
)


HEAD = "a" * 40
NOW = datetime(2026, 7, 16, 1, 0, tzinfo=timezone.utc)


def valid_receipt() -> dict[str, object]:
    return build_account_remediation_receipt(
        exact_head=HEAD,
        operator_name="Justice Gray Maciocha",
        observed_banner="GitHub Actions usage is blocked until the spending limit is raised.",
        restriction_category="SPENDING_LIMIT",
        remediation_summary=(
            "Raised the GitHub Actions monthly budget and confirmed hosted runners are enabled."
        ),
        billing_ui_evidence_reference=(
            "GitHub Billing and licensing > Budgets and alerts; screenshot retained privately."
        ),
        remediation_completed_at=NOW - timedelta(minutes=2),
        hosted_rerun_id=123456789,
        created_at=NOW,
    )


def test_remediation_receipt_is_exact_head_bound_and_non_authorizing() -> None:
    receipt = valid_receipt()

    assert receipt["contract_id"] == "AIGC-GITHUB-ACTIONS-ACCOUNT-REMEDIATION-001"
    assert receipt["receipt_id"].startswith("GAR-")
    assert receipt["repository"] == "Lornt1666/AIGC"
    assert receipt["issue_number"] == 124
    assert receipt["pull_request_number"] == 123
    assert receipt["exact_head"] == HEAD
    assert receipt["hosted_rerun_requested"] is True
    assert receipt["hosted_rerun_id"] == 123456789
    assert receipt["attestation"] == remediation_attestation("Justice Gray Maciocha")
    assert receipt["operator_review_required"] is True
    assert receipt["hosted_ci_replacement"] is False
    assert receipt["merge_authorized"] is False
    assert receipt["terraform_apply_authorized"] is False
    assert receipt["provider_mutation_authorized"] is False
    assert receipt["external_action_performed"] is False


def test_remediation_receipt_rejects_placeholder_observation() -> None:
    with pytest.raises(GitHubActionsRemediationError, match="placeholder"):
        build_account_remediation_receipt(
            exact_head=HEAD,
            operator_name="Justice Gray Maciocha",
            observed_banner="<EXACT_BANNER_TEXT>",
            restriction_category="OTHER",
            remediation_summary="Confirmed the actual restriction and corrected it in GitHub.",
            billing_ui_evidence_reference="Private screenshot reference 001.",
            remediation_completed_at=NOW,
            created_at=NOW,
        )


def test_remediation_receipt_rejects_raw_payment_details() -> None:
    with pytest.raises(GitHubActionsRemediationError, match="card numbers"):
        build_account_remediation_receipt(
            exact_head=HEAD,
            operator_name="Justice Gray Maciocha",
            observed_banner="Payment method required.",
            restriction_category="BILLING_PAYMENT",
            remediation_summary="Updated card number 4111 1111 1111 1111 in GitHub billing.",
            billing_ui_evidence_reference="GitHub billing page.",
            remediation_completed_at=NOW,
            created_at=NOW,
        )


def test_remediation_receipt_rejects_attestation_tampering() -> None:
    receipt = valid_receipt()
    receipt["attestation"] = "Approved for merge."

    with pytest.raises(GitHubActionsRemediationError, match="attestation mismatch"):
        validate_account_remediation_receipt(
            receipt,
            expected_head=HEAD,
            evaluated_at=NOW,
        )


def test_remediation_receipt_rejects_head_mismatch() -> None:
    receipt = valid_receipt()

    with pytest.raises(GitHubActionsRemediationError, match="different PR head"):
        validate_account_remediation_receipt(
            receipt,
            expected_head="b" * 40,
            evaluated_at=NOW,
        )
