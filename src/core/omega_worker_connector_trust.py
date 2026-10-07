from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


class ConnectorTrustError(ValueError):
    pass


@dataclass(frozen=True)
class ConnectorTrustObservation:
    connector_id: str
    conformance_score: int
    freshness_score: int
    provenance_score: int
    disagreement_rate: int

    def __post_init__(self) -> None:
        if not self.connector_id:
            raise ConnectorTrustError("connector_id is required.")
        values = (
            self.conformance_score,
            self.freshness_score,
            self.provenance_score,
            self.disagreement_rate,
        )
        if any(value < 0 or value > 100 for value in values):
            raise ConnectorTrustError("Trust metrics must be between 0 and 100.")


@dataclass(frozen=True)
class ConnectorTrustAssessment:
    connector_id: str
    score: int
    status: str
    authority_granted: bool
    reason: str


class ConnectorTrustScorer:
    """Scores observed evidence quality; scores never grant execution authority."""

    def assess(self, observation: ConnectorTrustObservation) -> ConnectorTrustAssessment:
        score = round(
            observation.conformance_score * 0.35
            + observation.freshness_score * 0.25
            + observation.provenance_score * 0.25
            + (100 - observation.disagreement_rate) * 0.15
        )
        if score >= 80:
            status = "TRUSTED_FOR_EVIDENCE"
        elif score >= 60:
            status = "DEGRADED_EVIDENCE"
        else:
            status = "ESCALATE"
        return ConnectorTrustAssessment(
            observation.connector_id,
            score,
            status,
            False,
            "Trust score is evidentiary only; authority is never derived from score.",
        )

    @staticmethod
    def rank(assessments: list[ConnectorTrustAssessment]) -> tuple[ConnectorTrustAssessment, ...]:
        return tuple(sorted(assessments, key=lambda item: (-item.score, item.connector_id)))
