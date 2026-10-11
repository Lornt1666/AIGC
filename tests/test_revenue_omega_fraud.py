from decimal import Decimal

from src.revenue_omega.fraud import FraudAssessmentInput, assess_billing_fraud


def base(**overrides):
    values = dict(
        employer_verified=True,
        placement_verified=True,
        agreement_verified=True,
        success_event_verified=True,
        compensation_verified=True,
        duplicate_billing_event=False,
        payer_matches_agreement=True,
        evidence_integrity_valid=True,
        attribution_status="ATTRIBUTED",
        eligible_compensation=Decimal("2000"),
        expected_compensation_min=Decimal("1500"),
        expected_compensation_max=Decimal("2500"),
        compute_markup_rate=Decimal("0.10"),
        invoice_total=Decimal("102.20"),
        high_value_threshold=Decimal("10000"),
    )
    values.update(overrides)
    return FraudAssessmentInput(**values)


def test_clean_billing_assessment_passes():
    result = assess_billing_fraud(base())
    assert result.decision == "PASS"
    assert result.automatic_billing_allowed is True
    assert not result.hard_flags
    assert not result.review_flags


def test_duplicate_billing_is_hard_reject():
    result = assess_billing_fraud(base(duplicate_billing_event=True))
    assert result.decision == "REJECT"
    assert "DUPLICATE_BILLING_EVENT" in result.hard_flags
    assert result.automatic_billing_allowed is False


def test_tampered_evidence_is_hard_reject():
    result = assess_billing_fraud(base(evidence_integrity_valid=False))
    assert result.decision == "REJECT"
    assert "TAMPERED_EVIDENCE" in result.hard_flags


def test_unknown_attribution_is_rejected():
    result = assess_billing_fraud(base(attribution_status="UNKNOWN"))
    assert result.decision == "REJECT"
    assert "PLACEMENT_UNVERIFIED" in result.hard_flags


def test_shared_attribution_requires_review_not_auto_bill():
    result = assess_billing_fraud(base(attribution_status="SHARED_ATTRIBUTION"))
    assert result.decision == "REQUIRE_REVIEW"
    assert "SHARED_ATTRIBUTION" in result.review_flags
    assert result.automatic_billing_allowed is False


def test_compensation_outlier_requires_review():
    result = assess_billing_fraud(base(eligible_compensation=Decimal("5000")))
    assert result.decision == "REQUIRE_REVIEW"
    assert "COMPENSATION_OUTLIER" in result.review_flags


def test_high_value_invoice_requires_review():
    result = assess_billing_fraud(base(invoice_total=Decimal("15000")))
    assert result.decision == "REQUIRE_REVIEW"
    assert "HIGH_VALUE_INVOICE" in result.review_flags
