from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .omega_worker_connector_admission import ReadOnlyAdmissionPolicy
from .omega_worker_connector_admission_ledger import (
    AdmissionAuditReceipt,
    ConnectorAdmissionAuditLedger,
)
from .omega_worker_connector_sdk import ConnectorCapabilities, ConnectorReadResult
from .omega_worker_connector_registry import ConnectorRegistry
from .omega_worker_connector_arena import SyntheticMultiConnectorArena
from .omega_worker_connector_trust import (
    ConnectorTrustAssessment,
    ConnectorTrustObservation,
    ConnectorTrustScorer,
)
from .omega_worker_external_evidence_reconciliation import (
    ExternalEvidenceReconciler,
    ReconciliationResult,
)
from .omega_worker_sandbox_connector import SandboxConnector, SandboxCredential


class SandboxReconciliationError(ValueError):
    pass


@dataclass(frozen=True)
class SandboxReconciliationResult:
    evidence_reference: str
    reconciliation: ReconciliationResult
    admission_receipts: tuple[AdmissionAuditReceipt, ...]
    trust: tuple[ConnectorTrustAssessment, ...]
    audit_valid: bool


class SandboxReconciliationOrchestrator:
    """Runs admitted sandbox evidence through trust and reconciliation only."""

    def __init__(
        self,
        connectors: Mapping[str, SandboxConnector],
        *,
        audit: ConnectorAdmissionAuditLedger | None = None,
        trust_scorer: ConnectorTrustScorer | None = None,
    ) -> None:
        if not connectors:
            raise SandboxReconciliationError("At least one sandbox connector is required.")
        if set(connectors) != {connector.connector_id for connector in connectors.values()}:
            raise SandboxReconciliationError("Connector mapping keys must match connector identities.")
        self.connectors = dict(connectors)
        self.audit = audit or ConnectorAdmissionAuditLedger()
        self.trust_scorer = trust_scorer or ConnectorTrustScorer()

    def _build_arena(self, admitted: Mapping[str, ConnectorReadResult]) -> SyntheticMultiConnectorArena:
        class Adapter:
            def __init__(self, result: ConnectorReadResult):
                self.capabilities = ConnectorCapabilities(
                    connector_id=result.connector_id,
                    version="0.32-sandbox",
                )
                self._result = result

            def read(self, evidence_reference: str) -> ConnectorReadResult:
                if evidence_reference != self._result.source_reference:
                    raise SandboxReconciliationError(
                        "Arena read reference does not match admitted evidence."
                    )
                return self._result

        registry = ConnectorRegistry()
        for result in admitted.values():
            registry.register(Adapter(result))
        return SyntheticMultiConnectorArena(registry)

