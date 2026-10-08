from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping

from .omega_worker_connector_pilot import ConnectorPilotError, PilotEvidence, ReadOnlyConnectorPilot


class ConnectorPilotVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class VerificationCase:
    case_id: str
    description: str
    expected_exception: type[Exception] | None = None


@dataclass(frozen=True)
class VerificationResult:
    case_id: str
    passed: bool
    observed: str


class ConnectorEvidenceValidator:
    """Validates evidence quality without granting authority."""

    def __init__(self, *, observed_after: str) -> None:
        self.observed_after = self._parse_time(observed_after)

    def validate(self, evidence: PilotEvidence) -> None:
        if not evidence.connector_id or not evidence.evidence_reference or not evidence.evidence_id:
            raise ConnectorPilotVerificationError("Evidence identity is incomplete.")
        if not isinstance(evidence.payload, Mapping) or not evidence.payload:
            raise ConnectorPilotVerificationError("Evidence payload must be a non-empty mapping.")
        observed_at = self._parse_time(evidence.observed_at)
        if observed_at < self.observed_after:
            raise ConnectorPilotVerificationError("Evidence is stale.")
        if evidence.connector_id == "":
            raise ConnectorPilotVerificationError("Evidence connector identity is missing.")

    @staticmethod
    def _parse_time(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ConnectorPilotVerificationError("Evidence timestamp is malformed.") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed


class ConnectorPilotVerificationHarness:
    """Adversarial synthetic harness for the v0.26 read-only pilot boundary."""

    def __init__(
        self,
        pilot: ReadOnlyConnectorPilot,
        *,
        validator: ConnectorEvidenceValidator,
    ) -> None:
        self.pilot = pilot
        self.validator = validator

    def read_and_validate(
        self,
        adapter: object,
        *,
        evidence_reference: str,
        credential: object,
    ) -> PilotEvidence:
        evidence = self.pilot.read(
            adapter, evidence_reference=evidence_reference, credential=credential
        )
        self.validator.validate(evidence)
        return evidence

    def run_case(
        self,
        case: VerificationCase,
        operation: Callable[[], object],
    ) -> VerificationResult:
        if not case.case_id or not case.description:
            raise ConnectorPilotVerificationError("Verification case identity is required.")
        try:
            result = operation()
        except Exception as exc:
            if case.expected_exception is None:
                return VerificationResult(case.case_id, False, type(exc).__name__)
            return VerificationResult(
                case.case_id, isinstance(exc, case.expected_exception), type(exc).__name__
            )
        if case.expected_exception is not None:
            return VerificationResult(case.case_id, False, "NO_EXCEPTION")
        return VerificationResult(case.case_id, True, type(result).__name__)

    def run_suite(
        self,
        cases: Mapping[str, tuple[VerificationCase, Callable[[], object]]],
    ) -> tuple[VerificationResult, ...]:
        if not cases:
            raise ConnectorPilotVerificationError("At least one verification case is required.")
        results = tuple(self.run_case(case, operation) for case, operation in cases.values())
        if not all(result.passed for result in results):
            failed = tuple(result.case_id for result in results if not result.passed)
            raise ConnectorPilotVerificationError(f"Verification suite failed: {failed}")
        return results

    @staticmethod
    def expected_denial() -> type[Exception]:
        return ConnectorPilotError
