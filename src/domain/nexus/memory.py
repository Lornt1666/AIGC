from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import NexusContract

MemoryType = Literal["EPISODIC", "SEMANTIC", "PROJECT"]
Sensitivity = Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
MemoryDecision = Literal["ACCEPT", "REJECT", "REVISE"]


class MemoryCandidate(NexusContract):
    candidate_id: str = Field(pattern=r"^MEMC-[A-Z0-9_-]{6,64}$")
    source_run_id: str = Field(min_length=1, max_length=200)
    source_artifact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    subject_refs: tuple[str, ...] = ()
    claim_refs: tuple[str, ...] = ()
    memory_type: MemoryType
    content: str = Field(min_length=1, max_length=20000)
    evidence_refs: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    proposed_retention: str = Field(min_length=1, max_length=200)
    sensitivity: Sensitivity = "INTERNAL"
    producer: str = Field(min_length=1, max_length=200)
    created_at: datetime


class MemoryAdmissionDecision(NexusContract):
    decision_id: str = Field(pattern=r"^MEMD-[A-Z0-9_-]{6,64}$")
    candidate_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    verifier_report_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: MemoryDecision
    reason: str = Field(min_length=1, max_length=4000)
    authority_source: Literal["POLICY", "HUMAN"]
    authority_actor: str = Field(min_length=1, max_length=200)
    admitted_at: datetime
    resulting_memory_id: str | None = Field(default=None, pattern=r"^MEM-[A-Z0-9_-]{6,64}$")

    @model_validator(mode="after")
    def accepted_requires_memory_id(self) -> "MemoryAdmissionDecision":
        if self.decision == "ACCEPT" and self.resulting_memory_id is None:
            raise ValueError("accepted memory admission requires resulting_memory_id")
        if self.decision != "ACCEPT" and self.resulting_memory_id is not None:
            raise ValueError("non-accepted memory admission cannot issue resulting_memory_id")
        return self


class MemoryRecord(NexusContract):
    memory_id: str = Field(pattern=r"^MEM-[A-Z0-9_-]{6,64}$")
    canonical_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_candidate_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    admission_decision_id: str = Field(pattern=r"^MEMD-[A-Z0-9_-]{6,64}$")
    memory_type: MemoryType
    content: str = Field(min_length=1, max_length=20000)
    evidence_bindings: tuple[str, ...] = ()
    verification_state: Literal["verified", "corroborated", "unverified"]
    valid_from: datetime
    valid_until: datetime | None = None
    superseded_by: str | None = Field(default=None, pattern=r"^MEM-[A-Z0-9_-]{6,64}$")
    revoked_at: datetime | None = None
    sensitivity: Sensitivity = "INTERNAL"
    retention_policy: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def temporal_integrity(self) -> "MemoryRecord":
        for field_name, value in (
            ("valid_from", self.valid_from),
            ("valid_until", self.valid_until),
            ("revoked_at", self.revoked_at),
        ):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{field_name} must be timezone-aware")
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("valid_until cannot precede valid_from")
        return self

    @property
    def active(self) -> bool:
        return self.superseded_by is None and self.revoked_at is None

    def is_eligible_at(self, *, authoritative_now: datetime) -> bool:
        if authoritative_now.tzinfo is None or authoritative_now.utcoffset() is None:
            raise ValueError("authoritative_now must be timezone-aware")
        if not self.active:
            return False
        if self.valid_from > authoritative_now:
            return False
        if self.valid_until is not None and self.valid_until <= authoritative_now:
            return False
        return True
