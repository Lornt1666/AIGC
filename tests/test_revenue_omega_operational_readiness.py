import pytest

from src.revenue_omega.operational_readiness import (
    OPERATIONAL_READINESS_WEIGHTS,
    OperationalReadinessDimension,
    evaluate_operational_readiness,
)


def test_weights_sum_to_one_hundred():
    assert sum(OPERATIONAL_READINESS_WEIGHTS.values()) == 100


def test_missing_dimensions_receive_zero_credit():
    report = evaluate_operational_readiness({})
    assert report.weighted_score == 0
    assert report.strict_score == 0
    assert report.complete is False
    assert set(report.missing_dimensions) == set(OPERATIONAL_READINESS_WEIGHTS)


def test_verified_requires_evidence():
    with pytest.raises(ValueError, match="requires evidence"):
        OperationalReadinessDimension(
            dimension="commission_engine",
            weight=8,
            state="VERIFIED",
            evidence_refs=(),
        )


def test_implemented_is_not_strictly_verified():
    states = {
        dimension: ("IMPLEMENTED", (f"CODE-{dimension}",), "")
        for dimension in OPERATIONAL_READINESS_WEIGHTS
    }
    report = evaluate_operational_readiness(states)
    assert report.strict_score == 0
    assert 0 < report.weighted_score < 100
    assert report.complete is False


def test_all_verified_is_exactly_one_hundred():
    states = {
        dimension: ("VERIFIED", (f"RECEIPT-{dimension}",), "")
        for dimension in OPERATIONAL_READINESS_WEIGHTS
    }
    report = evaluate_operational_readiness(states)
    assert report.weighted_score == 100
    assert report.strict_score == 100
    assert report.complete is True


def test_unknown_dimension_is_rejected():
    with pytest.raises(ValueError, match="unknown operational"):
        evaluate_operational_readiness({"magic_payments": ("VERIFIED", ("x",), "")})
