from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.domain.nexus.contracts import NexusContract

EvidenceKind = Literal[
    "repository",
    "test",
    "ci",
    "document",
    "dataset",
    "measurement",
    "simulation",
    "external_source",
    "human_attestation",
]


class EvidenceReference(NexusContract):
    evidence_id: str = Field(pattern=r"^EVD-[A-Z0-9_-]{6,64}$")
    kind: EvidenceKind
    source: str = Field(min_length=1, max_length=4000)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: datetime
    freshness_seconds: int | None = Field(default=None, ge=0)
    subject_refs: tuple[str, ...] = ()
    claim_refs: tuple[str, ...] = ()
    integrity_state: Literal["verified", "unverified", "invalid"] = "unverified"
    sensitivity: Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"] = "INTERNAL"
    provenance: str = Field(min_length=1, max_length=4000)
    grants_authority: Literal[False] = False
