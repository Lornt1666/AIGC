from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import EffectClass, NexusContract


WealthAction = Literal[
    "RESEARCH_OPPORTUNITIES",
    "PRODUCE_DELIVERABLE",
    "DRAFT_APPLICATION",
    "DRAFT_SALES_OUTREACH",
    "PREPARE_INVOICE",
    "PREPARE_TRANSACTION",
    "ANALYZE_REVENUE",
    "RECORD_REVENUE",
    "SUBMIT_APPLICATION",
    "SEND_SALES_OUTREACH",
    "SEND_INVOICE",
    "ACCEPT_CONTRACT",
    "EXECUTE_TRANSACTION",
    "SPEND_FUNDS",
    "TRANSFER_FUNDS",
    "PLACE_TRADE",
]

WealthPhase = Literal["RESEARCH", "PRODUCE", "PREPARE", "TRACK", "EXECUTE"]


class WealthActionPolicy(NexusContract):
    action: WealthAction
    phase: WealthPhase
    effect_class: EffectClass
    approval_required: bool
    target_required: bool = False
    evidence_required: bool = False
    public_read_only: bool = False
    internal_sandbox_only: bool = False
    persistent_internal_mutation: bool = False
    external_mutation: bool = False
    communication: bool = False
    legal_commitment: bool = False
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def enforce_safe_action_shape(self) -> "WealthActionPolicy":
        materially_consequential = (
            self.persistent_internal_mutation
            or self.external_mutation
            or self.communication
            or self.legal_commitment
            or self.effect_class
            in {
                "WRITE_COMPENSATABLE",
                "WRITE_IRREVERSIBLE",
                "FINANCIAL",
                "COMMUNICATION",
                "DEPLOYMENT",
                "SECURITY_SENSITIVE",
            }
        )
        if materially_consequential and not self.approval_required:
            raise ValueError("materially consequential wealth actions require explicit approval")
        if self.approval_required and self.internal_sandbox_only:
            raise ValueError("approval-gated actions cannot be labelled internal-sandbox-only")
        if self.public_read_only and self.effect_class != "READ_EXTERNAL":
            raise ValueError("public_read_only requires READ_EXTERNAL")
        if self.phase == "EXECUTE" and not self.approval_required:
            raise ValueError("execution actions must require explicit approval")
        if self.phase == "EXECUTE" and not self.target_required:
            raise ValueError("execution actions require an exact target")
        if self.persistent_internal_mutation and not self.evidence_required:
            raise ValueError("persistent wealth records require evidence")
        return self


class WealthOperatorPolicy(NexusContract):
    schema_version: Literal["aigc.wealth-operator-policy.v1"]
    policy_id: str = Field(pattern=r"^AIGC-WEALTH-[A-Z0-9_-]{3,64}$")
    owner: str = Field(min_length=1)
    base_currency: Literal["CAD"] = "CAD"
    mission: str = Field(min_length=1)
    consequential_financial_actions_require_explicit_authority: Literal[True] = True
    guaranteed_profit_claims_allowed: Literal[False] = False
    raw_credentials_allowed: Literal[False] = False
    actions: tuple[WealthActionPolicy, ...]

    @model_validator(mode="after")
    def require_closed_action_registry(self) -> "WealthOperatorPolicy":
        action_ids = [item.action for item in self.actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("wealth policy contains duplicate actions")
        expected = set(WealthAction.__args__)
        actual = set(action_ids)
        if actual != expected:
            missing = sorted(expected.difference(actual))
            extra = sorted(actual.difference(expected))
            raise ValueError(f"wealth policy action registry mismatch: missing={missing}, extra={extra}")
        return self

    @property
    def autonomous_actions(self) -> tuple[WealthAction, ...]:
        return tuple(item.action for item in self.actions if not item.approval_required)

    @property
    def approval_gated_actions(self) -> tuple[WealthAction, ...]:
        return tuple(item.action for item in self.actions if item.approval_required)

    def policy_for(self, action: WealthAction) -> WealthActionPolicy:
        return next(item for item in self.actions if item.action == action)


class WealthWorkRequest(NexusContract):
    """A non-authoritative request to plan wealth-producing work."""

    request_id: str = Field(pattern=r"^WREQ-[A-Z0-9_-]{6,64}$")
    action: WealthAction
    objective: str = Field(min_length=1, max_length=2000)
    target_ref: str | None = Field(default=None, min_length=1, max_length=500)
    financial_amount_cad: Decimal = Field(default=Decimal("0.00"), ge=0)
    evidence_refs: tuple[str, ...] = Field(default=(), max_length=20)
