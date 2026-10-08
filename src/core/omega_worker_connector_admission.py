from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .omega_worker_connector_pilot import ConnectorPilotError, PilotEvidence


class ConnectorAdmissionError(PermissionError):
    pass


@dataclass(frozen=True)
class ReadOnlyAdmissionPolicy:
    policy_id: str
    connector_id: str
    sandbox_only: bool = True
    external_writes: bool = False
    financial_authority: bool = False
    credential_discovery: bool = False
    target_discovery: bool = False
    permission_inference: bool = False

    def __post_init__(self) -> None:
        if not self.policy_id or not self.connector_id:
            raise ConnectorAdmissionError("Admission identity is required.")
        if not self.sandbox_only:
            raise ConnectorAdmissionError("v0.28 admission must remain sandbox-only.")
        if any((
            self.external_writes,
            self.financial_authority,
            self.credential_discovery,
            self.target_discovery,
            self.permission_inference,
        )):
            raise ConnectorAdmissionError("v0.28 admission cannot expand authority.")


@dataclass(frozen=True)
class ConnectorAdmissionReceipt:
    policy_id: str
    connector_id: str
    evidence_reference: str
    evidence_id: str
    admitted: bool


class ReadOnlyConnectorAdapter(Protocol):
    connector_id: str

    def read(self, evidence_reference: str, credential: object) -> PilotEvidence:
        ...


class ReadOnlyConnectorAdmission:
    """Admits one explicitly configured connector without granting execution authority."""

    def __init__(
        self,
        policy: ReadOnlyAdmissionPolicy,
        *,
        allowed_references: tuple[str, ...],
    ) -> None:
        if not allowed_references:
            raise ConnectorAdmissionError("At least one fixed evidence reference is required.")
        self.policy = policy
        self.allowed_references = allowed_references

    def admit(
        self,
        adapter: ReadOnlyConnectorAdapter,
        *,
        evidence_reference: str,
        credential: object,
    ) -> tuple[PilotEvidence, ConnectorAdmissionReceipt]:
        if adapter.connector_id != self.policy.connector_id:
            raise ConnectorAdmissionError("Connector identity is outside the admission policy.")
        if evidence_reference not in self.allowed_references:
            raise ConnectorAdmissionError("Evidence reference is outside the fixed allowlist.")
        if credential is None:
            raise ConnectorAdmissionError("Credential must be explicitly injected.")
        evidence = adapter.read(evidence_reference, credential)
        if evidence.connector_id != adapter.connector_id:
            raise ConnectorAdmissionError("Evidence connector provenance mismatch.")
        if evidence.evidence_reference != evidence_reference:
            raise ConnectorAdmissionError("Evidence reference provenance mismatch.")
        receipt = ConnectorAdmissionReceipt(
            policy_id=self.policy.policy_id,
            connector_id=adapter.connector_id,
            evidence_reference=evidence_reference,
            evidence_id=evidence.evidence_id,
            admitted=True,
        )
        return evidence, receipt
