from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .omega_worker_connector_registry import ConnectorAdmissionError, ConnectorRegistry
from .omega_worker_connector_sdk import ConnectorConformance, ConnectorReadResult


class ConnectorArenaError(ValueError):
    pass


@dataclass(frozen=True)
class ArenaDecision:
    evidence_reference: str
    status: str
    selected_connector: str | None
    candidates: tuple[str, ...]
    reason: str


class SyntheticMultiConnectorArena:
    """Compares synthetic connector evidence without inventing truth."""

    def __init__(self, registry: ConnectorRegistry) -> None:
        self.registry = registry

    def evaluate(
        self,
        connector_ids: Iterable[str],
        *,
        evidence_reference: str,
        expected_kind: str,
        observed_after: str | None = None,
    ) -> ArenaDecision:
        ids = tuple(connector_ids)
        if not ids or not evidence_reference or not expected_kind:
            raise ConnectorArenaError("Connectors, evidence reference, and evidence kind are required.")

        results: list[tuple[str, ConnectorReadResult]] = []
        rejected: list[str] = []

        for connector_id in ids:
            try:
                adapter = self.registry.get(connector_id)
                result = ConnectorConformance.validate(
                    adapter, evidence_reference=evidence_reference
                )
                if result.evidence_kind != expected_kind:
                    rejected.append(connector_id)
                    continue
                if observed_after and self._is_stale(result.observed_at, observed_after):
                    rejected.append(connector_id)
                    continue
                results.append((connector_id, result))
            except (ConnectorAdmissionError, ValueError):
                rejected.append(connector_id)

        if not results:
            self._record(evidence_reference, "NO_VALID_EVIDENCE", rejected)
            return ArenaDecision(
                evidence_reference, "ESCALATE", None, tuple(), "No valid evidence remained."
            )

        fingerprints = {
            self._fingerprint(result) for _, result in results
        }
        if len(fingerprints) > 1:
            candidates = tuple(sorted(connector_id for connector_id, _ in results))
            self._record(evidence_reference, "CONFLICT", candidates)
            return ArenaDecision(
                evidence_reference, "ESCALATE", None, candidates,
                "Valid connectors disagree; truth is not inferred."
            )

        ordered = tuple(sorted(connector_id for connector_id, _ in results))
        if len(ordered) > 1:
            self._record(evidence_reference, "CONSENSUS", ordered)
        else:
            self._record(evidence_reference, "SINGLE_VALID", ordered)
        return ArenaDecision(
            evidence_reference, "ACCEPT", ordered[0], ordered,
            "Evidence is consistent across all valid candidates."
        )

    @staticmethod
    def _fingerprint(result: ConnectorReadResult) -> tuple:
        return (
            result.evidence_kind,
            tuple(sorted(result.payload.items())),
        )

    @staticmethod
    def _is_stale(observed_at: str, observed_after: str) -> bool:
        left = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        right = datetime.fromisoformat(observed_after.replace("Z", "+00:00"))
        if left.tzinfo is None:
            left = left.replace(tzinfo=timezone.utc)
        if right.tzinfo is None:
            right = right.replace(tzinfo=timezone.utc)
        return left < right

    def _record(self, reference: str, status: str, connectors: Iterable[str]) -> None:
        self.registry.ledger.append(
            f"arena:{reference}:{status}",
            {"status": status, "connectors": tuple(connectors)},
        )
