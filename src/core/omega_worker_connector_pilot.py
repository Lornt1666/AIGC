from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


class ConnectorPilotError(PermissionError):
    pass


@dataclass(frozen=True)
class ReadOnlyPilotPolicy:
    policy_id: str
    connector_id: str
    allowed_references: tuple[str, ...]
    credential_injection_required: bool = True
    external_writes: bool = False
    financial_authority: bool = False
    autonomous_target_selection: bool = False

    def __post_init__(self) -> None:
        if not self.policy_id or not self.connector_id:
            raise ConnectorPilotError("Pilot identity is required.")
        if not self.allowed_references:
            raise ConnectorPilotError("An explicit reference allowlist is required.")
        if not self.credential_injection_required:
            raise ConnectorPilotError("Pilot credentials must be explicitly injected.")
        if self.external_writes or self.financial_authority or self.autonomous_target_selection:
            raise ConnectorPilotError("v0.26 pilot cannot expand authority.")


@dataclass(frozen=True)
class PilotEvidence:
    connector_id: str
    evidence_reference: str
    evidence_id: str
    payload: Mapping[str, object]
    observed_at: str


class ReadOnlyPilotAdapter(Protocol):
    connector_id: str

    def read(self, evidence_reference: str, credential: object) -> PilotEvidence:
        ...


class ReadOnlyConnectorPilot:
    """Admission-controlled pilot boundary; it never discovers credentials or targets."""

    def __init__(self, policy: ReadOnlyPilotPolicy) -> None:
        self.policy = policy

    def read(self, adapter: ReadOnlyPilotAdapter, *, evidence_reference: str, credential: object) -> PilotEvidence:
        if adapter.connector_id != self.policy.connector_id:
            raise ConnectorPilotError("Adapter is outside the pilot policy.")
        if evidence_reference not in self.policy.allowed_references:
            raise ConnectorPilotError("Evidence reference is outside the fixed allowlist.")
        if credential is None:
            raise ConnectorPilotError("Explicit credential injection is required.")
        result = adapter.read(evidence_reference, credential)
        if result.connector_id != adapter.connector_id:
            raise ConnectorPilotError("Evidence connector provenance mismatch.")
        if result.evidence_reference != evidence_reference:
            raise ConnectorPilotError("Evidence reference provenance mismatch.")
        return result
