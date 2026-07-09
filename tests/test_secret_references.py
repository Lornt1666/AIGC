from __future__ import annotations

from src.core.contract_validator import ContractValidationError
from src.core.work_order import SecretReference, is_raw_secret_value, validate_secret_references


def test_reference_only_secret_uri_is_allowed() -> None:
    reference = SecretReference(
        reference_id="AIGC-SECRET-REF-TEST",
        provider="google_secret_manager",
        reference="gcp_secret://aigc/test-reference",
        purpose="Reference-only test fixture.",
        raw_secret_present=False,
    )

    validate_secret_references([reference])


def test_raw_secret_prefix_is_rejected_without_committing_a_real_secret() -> None:
    raw_shape = "sk" + "-" + "A" * 48
    assert is_raw_secret_value(raw_shape) is True

    reference = SecretReference(
        reference_id="AIGC-SECRET-REF-RAW",
        provider="env_var",
        reference=raw_shape,
        purpose="Rejected raw secret-shaped test value.",
        raw_secret_present=False,
    )

    try:
        validate_secret_references([reference])
    except ContractValidationError as exc:
        assert "raw secret" in str(exc)
    else:
        raise AssertionError("Raw secret-shaped values must be rejected.")


def test_secret_reference_cannot_mark_raw_secret_present() -> None:
    reference = SecretReference(
        reference_id="AIGC-SECRET-REF-FLAGGED",
        provider="env_var",
        reference="env:AIGC_REFERENCE_ONLY",
        purpose="Flagged bad fixture.",
        raw_secret_present=True,
    )

    try:
        validate_secret_references([reference])
    except ContractValidationError as exc:
        assert "raw secret" in str(exc)
    else:
        raise AssertionError("raw_secret_present=true must be blocked.")
