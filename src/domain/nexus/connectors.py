from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import NexusContract


ConnectorStage = Literal["OBSERVE", "DRAFT", "SIMULATE", "EXECUTE", "VERIFY", "RECONCILE"]
ConnectorStatus = Literal[
    "CERTIFIED",
    "READ_ONLY",
    "DRAFT_ONLY",
    "HUMAN_HANDOFF",
    "BLOCKED_PERMISSION",
    "NOT_IMPLEMENTED",
    "EXPIRED",
    "REVOKED",
]


class ConnectorCapability(NexusContract):
    action: str = Field(min_length=1)
    stage: ConnectorStage
    status: ConnectorStatus
    reason: str = Field(min_length=1)
    live_mutation_allowed: bool = False

    @model_validator(mode="after")
    def validate_mutation_boundary(self) -> "ConnectorCapability":
        if self.live_mutation_allowed and not (
            self.status == "CERTIFIED" and self.stage == "EXECUTE"
        ):
            raise ValueError("live mutation requires a certified EXECUTE capability")
        return self


class ConnectorPassport(NexusContract):
    connector_id: str = Field(pattern=r"^PASSPORT_[A-Z0-9_-]{3,80}$")
    name: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    certification_status: ConnectorStatus
    identity_binding: str = Field(min_length=1)
    terms_binding: str = Field(min_length=1)
    capabilities: tuple[ConnectorCapability, ...]

    @model_validator(mode="after")
    def validate_capabilities(self) -> "ConnectorPassport":
        if not self.capabilities:
            raise ValueError("connector passport requires at least one capability")
        keys = [(item.action, item.stage) for item in self.capabilities]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate connector capability")
        if self.certification_status != "CERTIFIED" and any(
            item.live_mutation_allowed for item in self.capabilities
        ):
            raise ValueError("uncertified connector cannot enable live mutation")
        return self


class ConnectorActionDecision(NexusContract):
    connector_id: str
    action: str
    stage: ConnectorStage
    connector_status: ConnectorStatus
    capability_status: ConnectorStatus
    disposition: Literal[
        "PROCEED_TO_AUTHORITY_GATE",
        "LOCAL_PREPARATION_ONLY",
        "HUMAN_HANDOFF_REQUIRED",
        "BLOCKED",
    ]
    reason: str
    capability_admitted: bool = False
    live_mutation_possible: bool = False
    separate_execution_permit_required: bool = True
    authority_granted: Literal[False] = False
    external_action_performed: Literal[False] = False

