from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .omega_worker_connector_arena import ConnectorArenaError, SyntheticMultiConnectorArena
from .omega_worker_connector_trust import ConnectorTrustAssessment, ConnectorTrustObservation, ConnectorTrustScorer


class ExternalEvidenceReconciliationError(ValueError):
    pass


@dataclass(frozen=True)
class ReconciliationResult:
    evidence_reference: str
    status: str
    selected_connector: str | None
    candidates: tuple[str, ...]
    trust: tuple[ConnectorTrustAssessment, ...]
    reason: str


class ExternalEvidenceReconciler:
    """Reconciles admitted evidence without turning evidence quality into authority."""

    def __init__(
        self,
        arena: SyntheticMultiConnectorArena,
        *,
        trust_scorer: ConnectorTrustScorer | None = None,
    ) -> None:
        self.arena = arena
        self.trust_scorer = trust_scorer or ConnectorTrustScorer()

    def reconcile(
        self,
        connector_ids: Iterable[str],
        *,
        evidence_reference: str,
        expected_kind: str,
        observations: Mapping[str, ConnectorTrustObservation],
        observed_after: str | None = None,
    ) -> ReconciliationResult:
        ids = tuple(connector_ids)
        if not ids or not evidence_reference or not expected_kind:
            raise ExternalEvidenceReconciliationError(
                "Connectors, evidence reference, and evidence kind are required."
            )
        missing = tuple(connector_id for connector_id in ids if connector_id not in observations)
        if missing:
            raise ExternalEvidenceReconciliationError(
                f"Trust observations are required for every connector: {missing}"
            )

        trust = tuple(
            self.trust_scorer.assess(observations[connector_id])
            for connector_id in ids
        )
        if any(item.status == "ESCALATE" for item in trust):
            return ReconciliationResult(
                evidence_reference,
                "ESCALATE",
                None,
                tuple(sorted(ids)),
                trust,
                "At least one admitted evidence source has insufficient trust quality.",
            )

        decision = self.arena.evaluate(
            ids,
            evidence_reference=evidence_reference,
            expected_kind=expected_kind,
            observed_after=observed_after,
        )
        return ReconciliationResult(
            evidence_reference,
            decision.status,
            decision.selected_connector,
            decision.candidates,
            trust,
            decision.reason,
        )
