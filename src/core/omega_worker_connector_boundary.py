from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .omega_worker_evidence_ledger import EvidenceLedger


class ConnectorBoundaryError(PermissionError):
    pass


@dataclass(frozen=True)
class ConnectorEvidence:
    evidence_id: str
    connector_id: str
    evidence_kind: str
    source_reference: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not all((self.evidence_id, self.connector_id, self.evidence_kind, self.source_reference)):
            raise ConnectorBoundaryError("Connector evidence requires complete provenance.")
        if not isinstance(self.payload, Mapping):
            raise ConnectorBoundaryError("Connector payload must be a mapping.")


class ReadOnlyEvidenceSource(Protocol):
    connector_id: str

    def read_evidence(self, evidence_reference: str) -> ConnectorEvidence:
        ...


@dataclass(frozen=True)
class ConnectorPolicy:
    policy_id: str
    allowed_connectors: tuple[str, ...]
    read_only: bool = True
    allow_external_writes: bool = False
    allow_credential_discovery: bool = False
    allow_target_discovery: bool = False
    allow_recipient_inference: bool = False
    allow_permission_inference: bool = False
    allow_financial_authority: bool = False

    def __post_init__(self) -> None:
        if not self.policy_id or not self.allowed_connectors:
            raise ConnectorBoundaryError("Connector policy requires identity and an allowlist.")
        if len(set(self.allowed_connectors)) != len(self.allowed_connectors):
            raise ConnectorBoundaryError("Connector allowlist must be unique.")
        if not self.read_only:
            raise ConnectorBoundaryError("v0.21 connector boundary is read-only.")
        if self.allow_external_writes:
            raise ConnectorBoundaryError("External writes are prohibited.")
        if any((
            self.allow_credential_discovery,
            self.allow_target_discovery,
            self.allow_recipient_inference,
            self.allow_permission_inference,
            self.allow_financial_authority,
        )):
            raise ConnectorBoundaryError("v0.21 prohibits authority expansion.")


class ReadOnlyConnectorBoundary:
    """Ingests evidence from an explicitly allowlisted read-only source.

    This boundary records evidence only. It cannot write to the source, discover
    credentials/targets/recipients, infer permissions, or exercise financial authority.
    """

    def __init__(self, policy: ConnectorPolicy, ledger: EvidenceLedger | None = None) -> None:
        self.policy = policy
        self.ledger = ledger or EvidenceLedger()

    def ingest(self, source: ReadOnlyEvidenceSource, *, evidence_reference: str) -> ConnectorEvidence:
        if source.connector_id not in self.policy.allowed_connectors:
            raise ConnectorBoundaryError("Connector is outside the configured allowlist.")
        if not evidence_reference:
            raise ConnectorBoundaryError("An explicit evidence reference is required.")
        evidence = source.read_evidence(evidence_reference)
        if evidence.connector_id != source.connector_id:
            raise ConnectorBoundaryError("Evidence provenance does not match the connector.")
        self.ledger.append(
            f"{evidence.connector_id}:{evidence.evidence_id}",
            {
                "connector_id": evidence.connector_id,
                "evidence_kind": evidence.evidence_kind,
                "source_reference": evidence.source_reference,
            },
        )
        return evidence
