from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .omega_worker_connector_sdk import (
    ConnectorAdapter,
    ConnectorCapabilities,
    ConnectorConformance,
    ConnectorContractError,
    ConnectorReadResult,
)
from .omega_worker_evidence_ledger import EvidenceLedger


class ConnectorAdmissionError(PermissionError):
    pass


@dataclass(frozen=True)
class AdmissionRecord:
    connector_id: str
    version: str
    admitted: bool
    reason: str


class ConnectorRegistry:
    """Governed registry for read-only evidence connectors."""

    def __init__(self, ledger: EvidenceLedger | None = None) -> None:
        self.ledger = ledger or EvidenceLedger()
        self._adapters: dict[str, ConnectorAdapter] = {}
        self._admissions: dict[str, AdmissionRecord] = {}

    def register(self, adapter: ConnectorAdapter) -> AdmissionRecord:
        capabilities = adapter.capabilities
        if capabilities.connector_id in self._adapters:
            raise ConnectorAdmissionError("Connector ID is already registered.")
        try:
            self._validate_capabilities(capabilities)
        except ConnectorContractError as exc:
            record = AdmissionRecord(
                capabilities.connector_id, capabilities.version, False, str(exc)
            )
            self._admissions[capabilities.connector_id] = record
            self.ledger.append(
                f"{capabilities.connector_id}:ADMISSION_REJECTED",
                {"version": capabilities.version, "reason": str(exc)},
            )
            raise ConnectorAdmissionError(str(exc)) from exc

        self._adapters[capabilities.connector_id] = adapter
        record = AdmissionRecord(
            capabilities.connector_id, capabilities.version, True, "ADMITTED"
        )
        self._admissions[capabilities.connector_id] = record
        self.ledger.append(
            f"{capabilities.connector_id}:ADMISSION_ACCEPTED",
            {"version": capabilities.version},
        )
        return record

    def get(self, connector_id: str) -> ConnectorAdapter:
        try:
            return self._adapters[connector_id]
        except KeyError as exc:
            raise ConnectorAdmissionError("Connector is not admitted.") from exc

    def list_admitted(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def admission(self, connector_id: str) -> AdmissionRecord:
        try:
            return self._admissions[connector_id]
        except KeyError as exc:
            raise ConnectorAdmissionError("Connector has no admission record.") from exc

    @staticmethod
    def _validate_capabilities(capabilities: ConnectorCapabilities) -> None:
        # Re-run the SDK boundary explicitly at registry admission time.
        ConnectorCapabilities(**{
            "connector_id": capabilities.connector_id,
            "version": capabilities.version,
            "read_evidence": capabilities.read_evidence,
            "write_external": capabilities.write_external,
            "credential_discovery": capabilities.credential_discovery,
            "target_discovery": capabilities.target_discovery,
            "recipient_inference": capabilities.recipient_inference,
            "permission_inference": capabilities.permission_inference,
            "financial_authority": capabilities.financial_authority,
        })


class EvidenceRouter:
    """Routes reads only through admitted connectors and records provenance."""

    def __init__(self, registry: ConnectorRegistry) -> None:
        self.registry = registry

    def route(self, connector_id: str, evidence_reference: str) -> ConnectorReadResult:
        if not evidence_reference:
            raise ConnectorAdmissionError("An explicit evidence reference is required.")
        adapter = self.registry.get(connector_id)
        result = ConnectorConformance.validate(
            adapter, evidence_reference=evidence_reference
        )
        self.registry.ledger.append(
            f"{connector_id}:ROUTED:{result.evidence_id}",
            {
                "connector_id": connector_id,
                "evidence_id": result.evidence_id,
                "evidence_kind": result.evidence_kind,
                "source_reference": result.source_reference,
                "observed_at": result.observed_at,
            },
        )
        return result
