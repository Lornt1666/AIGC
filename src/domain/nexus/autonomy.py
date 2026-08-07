from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import EffectClass, NexusContract


ConsequenceClass = Literal[
    "PURE",
    "OBSERVATIONAL",
    "REVERSIBLE_INTERNAL",
    "PERSISTENT_INTERNAL",
    "EXTERNAL_READ",
    "EXTERNAL_MUTATION",
    "COMMUNICATION",
    "FINANCIAL",
    "LEGAL",
    "SECURITY_SENSITIVE",
    "PRODUCTION",
    "PHYSICAL",
    "DESTRUCTIVE",
    "IRREVERSIBLE",
    "INDETERMINATE",
]

AutonomyDisposition = Literal[
    "AUTONOMOUS_POLICY_PATH",
    "AUTONOMOUS_WITHIN_EXISTING_AUTHORITY",
    "BLOCK_PENDING_EXPLICIT_AUTHORITY",
    "READ_ONLY_RECONCILIATION",
]

AuthorityRequirement = Literal[
    "POLICY",
    "EXPLICIT",
    "EXISTING_EXPLICIT",
    "RECONCILIATION",
]


class ActionIntent(NexusContract):
    """Non-authoritative description of a proposed action for consequence classification."""

    intent_id: str = Field(pattern=r"^ACT-[A-Z0-9_-]{6,64}$")
    effect_class: EffectClass
    public_read_only: bool = False
    internal_sandbox_only: bool = False
    accesses_private_data: bool = False
    credentials_required: bool = False
    persistent_internal_mutation: bool = False
    external_mutation: bool = False
    communication: bool = False
    financial_spend_cad: Decimal = Field(default=Decimal("0.00"), ge=0)
    authorized_spend_cad: Decimal = Field(default=Decimal("0.00"), ge=0)
    legal_commitment: bool = False
    security_sensitive: bool = False
    production_change: bool = False
    physical_effect: bool = False
    destructive: bool = False
    irreversible: bool = False
    outcome_indeterminate: bool = False
    existing_explicit_authority: bool = False
    permit_id: str | None = Field(default=None, pattern=r"^PERMIT-[A-Z0-9_-]{6,64}$")

    @model_validator(mode="after")
    def validate_authority_reference(self) -> "ActionIntent":
        if self.existing_explicit_authority and self.permit_id is None:
            raise ValueError("existing_explicit_authority requires permit_id")
        if self.permit_id is not None and not self.existing_explicit_authority:
            raise ValueError("permit_id requires existing_explicit_authority=true")
        if self.public_read_only and self.effect_class != "READ_EXTERNAL":
            raise ValueError("public_read_only is valid only for READ_EXTERNAL")
        if self.internal_sandbox_only and self.effect_class not in {"PURE", "READ_LOCAL", "WRITE_REVERSIBLE"}:
            raise ValueError("internal_sandbox_only is incompatible with the requested effect class")
        return self


class ConsequenceAssessment(NexusContract):
    """Policy input only. This assessment does not grant or consume authority."""

    assessment_id: str = Field(pattern=r"^AUTO-[A-Z0-9_-]{6,64}$")
    intent_id: str
    consequence_class: ConsequenceClass
    material_consequence: bool
    authority_requirement: AuthorityRequirement
    disposition: AutonomyDisposition
    reason_codes: tuple[str, ...] = ()
    reasoning_may_continue: Literal[True] = True
    preparation_may_continue: Literal[True] = True
    execution_may_continue_without_new_authority: bool = False
    automatic_retry_allowed: bool = False
    authority_granted: Literal[False] = False
    external_action_performed: Literal[False] = False
