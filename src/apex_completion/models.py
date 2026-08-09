from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


GATE_IDS = tuple(f"G{i}" for i in range(2, 10))
GATE_STATES = {
    "UNKNOWN",
    "BLOCKED",
    "PARTIAL",
    "AWAITING_AUTHORIZATION",
    "IMPLEMENTED",
    "VERIFIED_COMPLETE",
    "NOT_APPLICABLE",
}
EVIDENCE_STATES = {"PRESENT", "MISSING", "STALE", "INVALID"}


@dataclass(frozen=True)
class EvidenceBinding:
    evidence_id: str
    evidence_type: str
    state: str
    subject: str
    exact_revision: str = ""
    digest: str = ""
    external_action_performed: bool = False

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.evidence_type or not self.subject:
            raise ValueError("evidence identity, type and subject are required")
        if self.state not in EVIDENCE_STATES:
            raise ValueError(f"unsupported evidence state: {self.state}")
        if self.digest and len(self.digest) != 64:
            raise ValueError("evidence digest must be SHA-256 length when supplied")


@dataclass(frozen=True)
class GateRecord:
    gate_id: str
    state: str
    required_evidence_types: tuple[str, ...]
    evidence: tuple[EvidenceBinding, ...] = field(default_factory=tuple)
    blocker: str = ""
    candidate_revision: str = ""

    def __post_init__(self) -> None:
        if self.gate_id not in GATE_IDS:
            raise ValueError(f"unsupported gate: {self.gate_id}")
        if self.state not in GATE_STATES:
            raise ValueError(f"unsupported gate state: {self.state}")
        if self.state in {"BLOCKED", "AWAITING_AUTHORIZATION"} and not self.blocker:
            raise ValueError("blocked/authorization gates require an explicit blocker")


@dataclass(frozen=True)
class ProgramSnapshot:
    snapshot_id: str
    repository: str
    canonical_branch: str
    canonical_revision: str
    integration_pr: int
    integration_branch: str
    integration_revision: str
    gates: tuple[GateRecord, ...]
    underlying_facts_weighted: float
    underlying_facts_strict: float
    authorization_completed: int
    authorization_total: int
    revenue_commercial_readiness: float
    revenue_operational_readiness: float
    critical_blockers: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.snapshot_id or not self.repository:
            raise ValueError("snapshot_id and repository are required")
        if not 0 <= self.underlying_facts_weighted <= 100:
            raise ValueError("weighted facts score must be 0..100")
        if not 0 <= self.underlying_facts_strict <= 100:
            raise ValueError("strict facts score must be 0..100")
        if not 0 <= self.revenue_commercial_readiness <= 100:
            raise ValueError("commercial readiness must be 0..100")
        if not 0 <= self.revenue_operational_readiness <= 100:
            raise ValueError("operational readiness must be 0..100")
        if self.authorization_total <= 0 or not 0 <= self.authorization_completed <= self.authorization_total:
            raise ValueError("authorization counts are invalid")
        gate_ids = [gate.gate_id for gate in self.gates]
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("duplicate gate IDs are prohibited")

    @property
    def gate_map(self) -> Mapping[str, GateRecord]:
        return {gate.gate_id: gate for gate in self.gates}
