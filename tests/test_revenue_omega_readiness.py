import pytest

from src.revenue_omega.readiness import (
    COMMERCIAL_READINESS_WEIGHTS,
    ReadinessDimension,
    evaluate_commercial_readiness,
)


def test_missing_dimensions_fail_closed_to_zero_credit():
    report = evaluate_commercial_readiness({})
    assert report.weighted_score == 0
    assert report.strict_score == 0
    assert report.is_complete is False
    assert len(report.dimensions) == len(COMMERCIAL_READINESS_WEIGHTS)


def test_verified_dimension_requires_evidence():
    with pytest.raises(ValueError, match="requires evidence"):
        ReadinessDimension(
            dimension="jurisdiction_licensing",
            weight=15,
            state="VERIFIED",
            evidence_refs=(),
        )


def test_missing_dimension_requires_blocker():
    with pytest.raises(ValueError, match="requires blocker"):
        ReadinessDimension(
            dimension="jurisdiction_licensing",
            weight=15,
            state="MISSING",
            evidence_refs=(),
            blocker="",
        )


def test_design_and_implementation_do_not_receive_strict_credit():
    states = {
        dimension: ("DESIGNED", (), "")
        for dimension in COMMERCIAL_READINESS_WEIGHTS
    }
    states["pricing_commission"] = ("IMPLEMENTED", ("PR-182",), "")
    report = evaluate_commercial_readiness(states)
    assert report.strict_score == 0
    assert report.weighted_score < 100
    assert report.is_complete is False


def test_all_verified_is_exactly_one_hundred():
    states = {
        dimension: ("VERIFIED", (f"EVIDENCE-{dimension}",), "")
        for dimension in COMMERCIAL_READINESS_WEIGHTS
    }
    report = evaluate_commercial_readiness(states)
    assert report.weighted_score == 100
    assert report.strict_score == 100
    assert report.is_complete is True


def test_unknown_dimension_is_rejected():
    with pytest.raises(ValueError, match="unknown readiness"):
        evaluate_commercial_readiness({"invented_dimension": ("VERIFIED", ("x",), "")})
