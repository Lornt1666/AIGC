from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .omega_worker_connector_admission import (
    ConnectorAdmissionReceipt,
    ReadOnlyAdmissionPolicy,
    ReadOnlyConnectorAdmission,
)
from .omega_worker_connector_admission_ledger import (
    AdmissionAuditReceipt,
    ConnectorAdmissionAuditLedger,
)
from .omega_worker_connector_pilot import PilotEvidence


class SandboxConnectorError(PermissionError):
    pass


@dataclass(frozen=True)
class SandboxCredential:
    credential_id: str
    sandbox: bool = True

    def __post_init__(self) -> None:
        if not self.credential_id:
            raise SandboxConnectorError("Explicit sandbox credential identity is required.")
        if not self.sandbox:
            raise SandboxConnectorError("v0.31 accepts sandbox credentials only.")


class SandboxConnector:
    """Deterministic read-only connector backed by caller-supplied sandbox fixtures."""

    def __init__(
        self,
        connector_id: str,
        fixtures: Mapping[str, Mapping[str, object]],
    ) -> None:
        if not connector_id or not fixtures:
            raise SandboxConnectorError("Connector identity and fixtures are required.")
        self.connector_id = connector_id
        self._fixtures = dict(fixtures)
        for reference, fixture in self._fixtures.items():
            if not reference or not isinstance(fixture, Mapping):
                raise SandboxConnectorError("Sandbox fixture identity is incomplete.")
            if not fixture.get("evidence_id") or not fixture.get("observed_at") or not isinstance(fixture.get("payload"), Mapping):
                raise SandboxConnectorError("Sandbox fixture provenance is incomplete.")

    def read(
        self,
        evidence_reference: str,
        credential: SandboxCredential,
    ) -> PilotEvidence:
        if not isinstance(credential, SandboxCredential):
            raise SandboxConnectorError("A SandboxCredential must be explicitly injected.")
        if evidence_reference not in self._fixtures:
            raise SandboxConnectorError("Evidence reference is outside the sandbox fixture set.")
        fixture = self._fixtures[evidence_reference]
        evidence_id = str(fixture.get("evidence_id", ""))
        observed_at = str(fixture.get("observed_at", ""))
        payload = fixture.get("payload")
        if not evidence_id or not observed_at or not isinstance(payload, Mapping):
            raise SandboxConnectorError("Sandbox fixture provenance is incomplete.")
        return PilotEvidence(
            connector_id=self.connector_id,
            evidence_reference=evidence_reference,
            evidence_id=evidence_id,
            payload=dict(payload),
            observed_at=observed_at,
        )

    def admit(
        self,
        policy: ReadOnlyAdmissionPolicy,
        *,
        evidence_reference: str,
        credential: SandboxCredential,
        audit: ConnectorAdmissionAuditLedger,
        receipt_id: str,
    ) -> tuple[PilotEvidence, ConnectorAdmissionReceipt, AdmissionAuditReceipt]:
        admission = ReadOnlyConnectorAdmission(
            policy,
            allowed_references=tuple(self._fixtures),
        )
        evidence, receipt = admission.admit(
            self,
            evidence_reference=evidence_reference,
            credential=credential,
        )
        audit_receipt = audit.record(
            receipt_id=receipt_id,
            policy_id=receipt.policy_id,
            connector_id=receipt.connector_id,
            evidence_reference=receipt.evidence_reference,
            evidence_id=receipt.evidence_id,
            admitted=receipt.admitted,
            policy={
                "policy_id": policy.policy_id,
                "connector_id": policy.connector_id,
                "sandbox_only": policy.sandbox_only,
            },
            evidence={
                "evidence_id": evidence.evidence_id,
                "observed_at": evidence.observed_at,
                "payload": dict(evidence.payload),
            },
        )
        return evidence, receipt, audit_receipt
