from src.core.omega_worker_connector_trust import (
    ConnectorTrustObservation,
    ConnectorTrustScorer,
    ConnectorTrustError,
)


def test_high_quality_is_evidence_trusted_only():
    result = ConnectorTrustScorer().assess(
        ConnectorTrustObservation("a", 100, 100, 100, 0)
    )
    assert result.status == "TRUSTED_FOR_EVIDENCE"
    assert result.authority_granted is False


def test_degraded_quality_is_not_authority():
    result = ConnectorTrustScorer().assess(
        ConnectorTrustObservation("a", 70, 60, 70, 20)
    )
    assert result.status == "DEGRADED_EVIDENCE"
    assert result.authority_granted is False


def test_low_quality_escalates():
    result = ConnectorTrustScorer().assess(
        ConnectorTrustObservation("a", 20, 20, 20, 90)
    )
    assert result.status == "ESCALATE"
    assert result.authority_granted is False


def test_metrics_are_bounded():
    try:
        ConnectorTrustObservation("a", 101, 50, 50, 0)
    except ConnectorTrustError:
        return
    assert False, "out-of-range trust metric was accepted"


def test_ranking_is_deterministic_with_connector_tie_break():
    scorer = ConnectorTrustScorer()
    assessments = [
        scorer.assess(ConnectorTrustObservation("b", 100, 80, 100, 0)),
        scorer.assess(ConnectorTrustObservation("a", 100, 80, 100, 0)),
    ]
    ranked = scorer.rank(assessments)
    assert tuple(item.connector_id for item in ranked) == ("a", "b")
