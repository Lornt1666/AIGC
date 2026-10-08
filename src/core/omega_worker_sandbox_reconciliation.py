from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .omega_worker_connector_admission import ReadOnlyAdmissionPolicy
from .omega_worker_connector_admission_ledger import (
    AdmissionAuditReceipt,
    ConnectorAdmissionAuditLedger,
)
from .omega_worker_connector_arena import SyntheticMultiConnectorArena
from .omega_worker_connector_sdk import ConnectorCapabilities, ConnectorReadResult
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

    def _build_arena(
        self, admitted: Mapping[str, ConnectorReadResult]
    ) -> SyntheticMultiConnectorArena:
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

        registry = __import__(
            "src.core.omega_worker_connector_registry",
            fromlist=["ConnectorRegistry"],
        ).ConnectorRegistry()
        for result in admitted.values():
            registry.register(Adapter(result))
        return SyntheticMultiConnectorArena(registry)

    def run(
        self,
        *,
        evidence_reference: str,
        policies: Mapping[str, ReadOnlyAdmissionPolicy],
        credentials: Mapping[str, SandboxCredential],
        trust_observations: Mapping[str, ConnectorTrustObservation],
        expected_kind: str,
        receipt_prefix: str,
        observed_after: str | None = None,
    ) -> SandboxReconciliationResult:
        connector_ids = tuple(sorted(self.connectors))
        missing = [
            cid for cid in connector_ids
            if cid not in policies or cid not in credentials
        ]
        if missing:
            raise SandboxReconciliationError(
                f"Explicit policy and credential are required for every connector: {tuple(missing)}"
            )

        receipts: list[AdmissionAuditReceipt] = []
        admitted: dict[str, ConnectorReadResult] = {}
        for connector_id in connector_ids:
            policy = policies[connector_id]
            if policy.connector_id != connector_id:
                raise SandboxReconciliationError("Policy connector identity mismatch.")
            evidence, _, audit_receipt = self.connectors[connector_id].admit(
                policy,
                evidence_reference=evidence_reference,
                credential=credentials[connector_id],
                audit=self.audit,
                receipt_id=f"{receipt_prefix}:{connector_id}",
            )
            receipts.append(audit_receipt)
            admitted[connector_id] = ConnectorReadResult(
                connector_id=connector_id,
                evidence_id=evidence.evidence_id,
                evidence_kind=str(evidence.payload.get("kind", "")),
                source_reference=evidence.evidence_reference,
                payload=dict(evidence.payload),
                observed_at=evidence.observed_at,
            )

        reconciler = ExternalEvidenceReconciler(
            self._build_arena(admitted),
            trust_scorer=self.trust_scorer,
        )
        reconciliation = reconciler.reconcile(
            connector_ids,
            evidence_reference=evidence_reference,
            expected_kind=expected_kind,
            observations=trust_observations,
            observed_after=observed_after,
        )
        return SandboxReconciliationResult(
            evidence_reference=evidence_reference,
            reconciliation=reconciliation,
            admission_receipts=tuple(receipts),
            trust=reconciliation.trust,
            audit_valid=self.audit.verify_chain(),
        )
