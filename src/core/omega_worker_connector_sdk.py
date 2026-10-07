from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


class ConnectorContractError(ValueError):
    pass


@dataclass(frozen=True)
class ConnectorCapabilities:
    connector_id: str
    version: str
    read_evidence: bool = True
    write_external: bool = False
    credential_discovery: bool = False
    target_discovery: bool = False
    recipient_inference: bool = False
    permission_inference: bool = False
    financial_authority: bool = False

    def __post_init__(self) -> None:
        if not self.connector_id or not self.version:
            raise ConnectorContractError("Connector identity and version are required.")
        if not self.read_evidence:
            raise ConnectorContractError("v0.22 connectors must support evidence reading.")
        if any((
            self.write_external,
            self.credential_discovery,
            self.target_discovery,
            self.recipient_inference,
            self.permission_inference,
            self.financial_authority,
        )):
            raise ConnectorContractError("Connector capabilities exceed the v0.22 read-only boundary.")


@dataclass(frozen=True)
class ConnectorReadResult:
    connector_id: str
    evidence_id: str
    evidence_kind: str
    source_reference: str
    payload: Mapping[str, object]
    observed_at: str

    def __post_init__(self) -> None:
        if not all((self.connector_id, self.evidence_id, self.evidence_kind, self.source_reference, self.observed_at)):
            raise ConnectorContractError("Connector reads require complete provenance.")


class ConnectorAdapter(Protocol):
    capabilities: ConnectorCapabilities

    def read(self, evidence_reference: str) -> ConnectorReadResult:
        ...


class ConnectorConformance:
    """Admission tests for synthetic/read-only connector implementations."""

    @staticmethod
    def validate(adapter: ConnectorAdapter, *, evidence_reference: str) -> ConnectorReadResult:
        capabilities = adapter.capabilities
        if not capabilities.read_evidence:
            raise ConnectorContractError("Adapter does not provide evidence reads.")
        if not evidence_reference:
            raise ConnectorContractError("An explicit evidence reference is required.")
        result = adapter.read(evidence_reference)
        if result.connector_id != capabilities.connector_id:
            raise ConnectorContractError("Read result connector identity mismatch.")
        if result.source_reference != evidence_reference:
            raise ConnectorContractError("Read result provenance reference mismatch.")
        if not isinstance(result.payload, Mapping):
            raise ConnectorContractError("Read payload must be a mapping.")
        return result
