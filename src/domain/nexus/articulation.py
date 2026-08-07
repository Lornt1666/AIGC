from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import NexusContract


ArticulationMode = Literal[
    "PARALLEL",
    "COLLABORATIVE",
    "CRITIQUE",
    "DEBATE",
    "RED_TEAM",
]

ArticulationResponseType = Literal[
    "PROPOSAL",
    "CRITIQUE",
    "COUNTERARGUMENT",
    "SYNTHESIS",
    "QUESTION",
    "EVIDENCE_REQUEST",
    "RISK_FINDING",
    "ALTERNATIVE",
    "FINAL_RECOMMENDATION",
]

ContentClassification = Literal[
    "UNTRUSTED_MODEL_OUTPUT",
    "DERIVED_UNTRUSTED_SYNTHESIS",
]

ResolutionStatus = Literal["OPEN", "RESOLVED", "HUMAN_REVIEW_REQUIRED"]
SessionStatus = Literal["OPEN", "COMPLETE", "SYNTHESIZED"]


class ArticulationBudget(NexusContract):
    maximum_rounds: int = Field(ge=1, le=100)
    maximum_contributions: int = Field(ge=1, le=1000)
    maximum_tokens: int = Field(ge=0)
    maximum_cost_cad: Decimal = Field(ge=Decimal("0"))
    maximum_elapsed_seconds: int = Field(gt=0)
    live_calls_allowed: bool = False


class ArticulationMessage(NexusContract):
    message_id: str = Field(pattern=r"^ARTMSG-[A-F0-9]{24}$")
    session_id: str = Field(pattern=r"^ART-[A-Z0-9_-]{6,64}$")
    round_id: int = Field(ge=1)
    provider_id: str = Field(min_length=1, max_length=100)
    model_label: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=64)
    response_type: ArticulationResponseType
    parent_message_ids: tuple[str, ...] = ()
    content: str = Field(min_length=1, max_length=100000)
    claim_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    repository_context_id: str | None = None
    uncertainty: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    accounted_tokens: int = Field(ge=0)
    cost_cad: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    content_classification: ContentClassification = "UNTRUSTED_MODEL_OUTPUT"
    canonical_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority_granted: Literal[False] = False
    external_action_performed: Literal[False] = False
    live_provider_call_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_message(self) -> "ArticulationMessage":
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("ArticulationMessage created_at must be timezone-aware")
        if self.message_id in self.parent_message_ids:
            raise ValueError("ArticulationMessage cannot parent itself")
        if len(self.parent_message_ids) != len(set(self.parent_message_ids)):
            raise ValueError("ArticulationMessage contains duplicate parent IDs")
        return self


class DisagreementRecord(NexusContract):
    disagreement_id: str = Field(pattern=r"^DIS-[A-F0-9]{24}$")
    message_a: str = Field(pattern=r"^ARTMSG-[A-F0-9]{24}$")
    message_b: str = Field(pattern=r"^ARTMSG-[A-F0-9]{24}$")
    claim_a: str = Field(min_length=1, max_length=20000)
    claim_b: str = Field(min_length=1, max_length=20000)
    evidence_refs_a: tuple[str, ...] = ()
    evidence_refs_b: tuple[str, ...] = ()
    uncertainty: float = Field(ge=0.0, le=1.0)
    resolution_status: ResolutionStatus = "OPEN"
    human_decision_required: bool = False


class DialogueLedger(NexusContract):
    session_id: str = Field(pattern=r"^ART-[A-Z0-9_-]{6,64}$")
    messages: tuple[ArticulationMessage, ...]
    canonical_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority_granted: Literal[False] = False
    external_action_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_ledger(self) -> "DialogueLedger":
        if not self.messages:
            raise ValueError("DialogueLedger requires at least one message")
        seen: set[str] = set()
        previous_round = 0
        for message in self.messages:
            if message.session_id != self.session_id:
                raise ValueError("DialogueLedger contains a cross-session message")
            if message.message_id in seen:
                raise ValueError("DialogueLedger contains duplicate message IDs")
            if message.round_id < previous_round:
                raise ValueError("DialogueLedger message rounds must be nondecreasing")
            for parent_id in message.parent_message_ids:
                if parent_id not in seen:
                    raise ValueError("DialogueLedger parent must reference an earlier message")
            seen.add(message.message_id)
            previous_round = message.round_id
        return self


class ArticulationSession(NexusContract):
    session_id: str = Field(pattern=r"^ART-[A-Z0-9_-]{6,64}$")
    work_order_id: str = Field(pattern=r"^WO-[A-Z0-9_-]{6,64}$")
    context_envelope_id: str = Field(pattern=r"^CTX-[A-Z0-9_-]{6,64}$")
    mode: ArticulationMode
    budget: ArticulationBudget
    messages: tuple[ArticulationMessage, ...]
    disagreements: tuple[DisagreementRecord, ...] = ()
    status: SessionStatus
    canonical_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority_granted: Literal[False] = False

    @model_validator(mode="after")
    def validate_session(self) -> "ArticulationSession":
        if len(self.messages) > self.budget.maximum_contributions:
            raise ValueError("ArticulationSession contribution budget exceeded")
        if self.messages and max(message.round_id for message in self.messages) > self.budget.maximum_rounds:
            raise ValueError("ArticulationSession round budget exceeded")
        if sum(message.accounted_tokens for message in self.messages) > self.budget.maximum_tokens:
            raise ValueError("ArticulationSession token budget exceeded")
        if sum((message.cost_cad for message in self.messages), Decimal("0")) > self.budget.maximum_cost_cad:
            raise ValueError("ArticulationSession cost budget exceeded")

        message_ids = {message.message_id for message in self.messages}
        if len(message_ids) != len(self.messages):
            raise ValueError("ArticulationSession contains duplicate message IDs")
        for message in self.messages:
            if message.session_id != self.session_id:
                raise ValueError("ArticulationSession contains a cross-session message")

        disagreement_ids: set[str] = set()
        for disagreement in self.disagreements:
            if disagreement.disagreement_id in disagreement_ids:
                raise ValueError("ArticulationSession contains duplicate disagreement IDs")
            if disagreement.message_a not in message_ids or disagreement.message_b not in message_ids:
                raise ValueError("DisagreementRecord references a message outside the session")
            disagreement_ids.add(disagreement.disagreement_id)
        return self
