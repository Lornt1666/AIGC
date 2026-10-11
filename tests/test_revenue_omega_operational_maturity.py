import pytest

from src.revenue_omega.operational_maturity import (
    OPERATIONAL_DIMENSIONS,
    OperationalMaturityDimension,
    evaluate_operational_maturity,
)


def test_dimension_weights_sum_to_one_hundred():
    assert sum(weight for weight, _ in OPERATIONAL_DIMENSIONS.values()) == 100


def test_all_ci_verified_does_not_falsely_mean_runtime_ready():
    observed = {
        name: ("CI_VERIFIED", (f"CI-{name}",), "")
        for name in OPERATIONAL_DIMENSIONS
    }
    report = evaluate_operational_maturity(observed)
    assert report.weighted_score == 65
    assert report.strict_score < 100
    assert report.complete is False
    assert any("email_delivery" in blocker for blocker in report.blockers)
    assert any("payment_provider_adapter" in blocker for blocker in report.blockers)


def test_sandbox_payment_proof_still_does_not_equal_live_payment_runtime():
    observed = {
        name: ("CI_VERIFIED", (f"CI-{name}",), "")
        for name in OPERATIONAL_DIMENSIONS
    }
    observed["email_delivery"] = ("SANDBOX_VERIFIED", ("SANDBOX-EMAIL",), "")
    observed["payment_provider_adapter"] = ("SANDBOX_VERIFIED", ("SANDBOX-PAYMENT",), "")
    observed["payment_webhooks_reconciliation"] = ("SANDBOX_VERIFIED", ("SANDBOX-WEBHOOK",), "")
    report = evaluate_operational_maturity(observed)
    assert report.complete is False
    assert any("requires RUNTIME_VERIFIED" in blocker for blocker in report.blockers)


def test_ci_is_sufficient_for_pure_commission_engine():
    dimension = OperationalMaturityDimension(
        dimension="commission_engine",
        weight=8,
        required_level="CI_VERIFIED",
        observed_level="CI_VERIFIED",
        evidence_refs=("CI-RECEIPT",),
    )
    assert dimension.strict_complete is True
    assert dimension.strict_credit == 8


def test_runtime_verified_everywhere_is_exactly_complete():
    observed = {
        name: ("RUNTIME_VERIFIED", (f"RUNTIME-{name}",), "")
        for name in OPERATIONAL_DIMENSIONS
    }
    report = evaluate_operational_maturity(observed)
    assert report.weighted_score == 100
    assert report.strict_score == 100
    assert report.complete is True
    assert report.blockers == ()


def test_missing_dimension_requires_blocker():
    with pytest.raises(ValueError, match="requires blocker"):
        OperationalMaturityDimension(
            dimension="compute_metering",
            weight=10,
            required_level="RUNTIME_VERIFIED",
            observed_level="MISSING",
            evidence_refs=(),
            blocker="",
        )
