from dataclasses import dataclass

import pytest

from src.core.omega_worker_connector_arena import SyntheticMultiConnectorArena
from src.core.omega_worker_connector_registry import ConnectorRegistry
from src.core.omega_worker_connector_sdk import ConnectorCapabilities, ConnectorReadResult
from src.core.omega_worker_external_evidence_reconciliation import (
    ExternalEvidenceReconciliationError,
    ExternalEvidenceReconciler,
)
from src.core.omega_worker_connector_trust import ConnectorTrustObservation


@dataclass
class Adapter:
    connector_id: str
    payload: dict[str, object]

    @property
    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(self.connector_id, "test-1")

    def read(self, evidence_reference: str) -> ConnectorReadResult:
        return ConnectorReadResult(
            self.connector_id,
            f"evidence-{self.connector_id}",
            "status",
            evidence_reference,
            self.payload,
            "2026-10-08T00:00:00Z",
        )


def setup_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register(Adapter("connector-a", {"status": "ok"}))
    registry.register(Adapter("connector-b", {"status": "ok"}))
    return registry


def trust(
    connector_id: str,
    *,
    disagreement_rate: int = 0,
    conformance_score: int = 95,
) -> ConnectorTrustObservation:
    return ConnectorTrustObservation(
        connector_id=connector_id,
        conformance_score=conformance_score,
        freshness_score=95,
        provenance_score=95,
        disagreement_rate=disagreement_rate,
    )


def test_consensus_is_accepted_without_granting_authority() -> None:
    registry = setup_registry()
    reconciler = ExternalEvidenceReconciler(SyntheticMultiConnectorArena(registry))
    result = reconciler.reconcile(
        ("connector-a", "connector-b"),
        evidence_reference="sandbox://fixture/001",
        expected_kind="status",
        observations={"connector-a": trust("connector-a"), "connector-b": trust("connector-b")},
    )
    assert result.status == "ACCEPT"
    assert result.selected_connector == "connector-a"
    assert all(item.authority_granted is False for item in result.trust)


def test_conflict_escalates_instead_of_inference() -> None:
    registry = ConnectorRegistry()
    registry.register(Adapter("connector-a", {"status": "ok"}))
    registry.register(Adapter("connector-b", {"status": "degraded"}))
    reconciler = ExternalEvidenceReconciler(SyntheticMultiConnectorArena(registry))
    result = reconciler.reconcile(
        ("connector-a", "connector-b"),
        evidence_reference="sandbox://fixture/001",
        expected_kind="status",
        observations={"connector-a": trust("connector-a"), "connector-b": trust("connector-b")},
    )
    assert result.status == "ESCALATE"
    assert result.selected_connector is None


def test_low_trust_escalates_before_selection() -> None:
    registry = setup_registry()
    reconciler = ExternalEvidenceReconciler(SyntheticMultiConnectorArena(registry))
    result = reconciler.reconcile(
        ("connector-a", "connector-b"),
        evidence_reference="sandbox://fixture/001",
        expected_kind="status",
        observations={
            "connector-a": trust("connector-a"),
            "connector-b": trust("connector-b", disagreement_rate=100, conformance_score=20),
        },
    )
    assert result.status == "ESCALATE"
    assert result.selected_connector is None


def test_every_connector_requires_trust_observation() -> None:
    registry = setup_registry()
    reconciler = ExternalEvidenceReconciler(SyntheticMultiConnectorArena(registry))
    with pytest.raises(ExternalEvidenceReconciliationError):
        reconciler.reconcile(
            ("connector-a", "connector-b"),
            evidence_reference="sandbox://fixture/001",
            expected_kind="status",
            observations={"connector-a": trust("connector-a")},
        )


def test_reconciliation_has_no_execution_surface() -> None:
    registry = setup_registry()
    reconciler = ExternalEvidenceReconciler(SyntheticMultiConnectorArena(registry))
    assert not hasattr(reconciler, "execute")
    assert not hasattr(reconciler, "write")
