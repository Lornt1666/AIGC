from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import NexusContract


OccupationPackStatus = Literal[
    "DRAFT",
    "SHADOW_ONLY",
    "SUPERVISED",
    "CERTIFIED",
    "EXPIRED",
    "REVOKED",
]


class OccupationClassificationMapping(NexusContract):
    taxonomy: Literal["O*NET-SOC", "ESCO", "NOC"]
    code: str | None = Field(default=None, min_length=1)
    title: str = Field(min_length=1)
    mapping_status: Literal["EXACT", "RELATED", "PROVISIONAL", "UNRESOLVED"]
    source_url: str = Field(pattern=r"^https://")
    reviewed_at: date

    @model_validator(mode="after")
    def validate_mapping_claim(self) -> "OccupationClassificationMapping":
        if self.mapping_status == "UNRESOLVED" and self.code is not None:
            raise ValueError("unresolved classification mapping must not claim a code")
        if self.mapping_status != "UNRESOLVED" and self.code is None:
            raise ValueError("resolved classification mapping requires a code")
        return self


class OccupationEvaluationGate(NexusContract):
    metric: str = Field(min_length=1)
    comparator: Literal[">=", "<=", "=="]
    threshold: float
    unit: str = Field(min_length=1)
    hard_gate: bool = True


class OccupationCapability(NexusContract):
    capability_id: str = Field(pattern=r"^CAP-[A-Z0-9_-]{4,64}$")
    name: str = Field(min_length=1)
    allowed_outputs: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    required_supervision: Literal["HUMAN_REVIEW", "HUMAN_ON_LOOP", "NONE"]


class OccupationPack(NexusContract):
    pack_id: str = Field(pattern=r"^OCC-[A-Z0-9_-]{4,64}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: OccupationPackStatus
    jurisdiction: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    authoritative_sources: tuple[str, ...]
    classification_mappings: tuple[OccupationClassificationMapping, ...]
    autonomy_ceiling: Literal[
        "LOCAL_DRAFT_ONLY",
        "SUPERVISED_INTERNAL",
        "CERTIFIED_BOUNDED_EXECUTION",
    ]
    recertification_days: int = Field(ge=1, le=365)
    training_rights_required: bool = True
    capabilities: tuple[OccupationCapability, ...]
    evaluation_gates: tuple[OccupationEvaluationGate, ...]
    regulated_exclusions: tuple[str, ...]
    certification_issuer: str | None = None
    certified_at: date | None = None
    expires_at: date | None = None
    grants_external_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_certification(self) -> "OccupationPack":
        if self.status == "CERTIFIED":
            if not self.certification_issuer or not self.certified_at or not self.expires_at:
                raise ValueError("CERTIFIED occupation pack requires issuer and validity dates")
            if self.expires_at <= self.certified_at:
                raise ValueError("occupation certification expiry must follow certification date")
        elif any((self.certification_issuer, self.certified_at, self.expires_at)):
            raise ValueError("non-certified occupation pack cannot carry certification claims")
        if self.status in {"DRAFT", "SHADOW_ONLY"} and self.autonomy_ceiling != "LOCAL_DRAFT_ONLY":
            raise ValueError("draft or shadow occupation pack cannot exceed local draft autonomy")
        mapping_keys = [
            (item.taxonomy, item.code, item.title.casefold())
            for item in self.classification_mappings
        ]
        if not mapping_keys:
            raise ValueError("occupation pack requires at least one classification mapping")
        if len(mapping_keys) != len(set(mapping_keys)):
            raise ValueError("occupation classification mappings must be unique")
        capability_ids = [item.capability_id for item in self.capabilities]
        if len(capability_ids) != len(set(capability_ids)):
            raise ValueError("occupation capability IDs must be unique")
        return self
