from __future__ import annotations

from decimal import Decimal

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.nexus.autonomy import ActionIntent, ConsequenceAssessment, ConsequenceClass


_CONSEQUENTIAL_EFFECTS = {
    "WRITE_REVERSIBLE",
    "WRITE_COMPENSATABLE",
    "WRITE_IRREVERSIBLE",
    "FINANCIAL",
    "COMMUNICATION",
    "DEPLOYMENT",
    "SECURITY_SENSITIVE",
}


def _assessment_id(intent: ActionIntent) -> str:
    return "AUTO-" + canonical_sha256(intent)[:24].upper()


def _consequence_class(intent: ActionIntent) -> ConsequenceClass:
    if intent.outcome_indeterminate:
        return "INDETERMINATE"
    if intent.physical_effect:
        return "PHYSICAL"
    if intent.legal_commitment:
        return "LEGAL"
    if intent.financial_spend_cad > Decimal("0") or intent.effect_class == "FINANCIAL":
        return "FINANCIAL"
    if intent.communication or intent.effect_class == "COMMUNICATION":
        return "COMMUNICATION"
    if intent.production_change or intent.effect_class == "DEPLOYMENT":
        return "PRODUCTION"
    if intent.destructive:
        return "DESTRUCTIVE"
    if intent.irreversible or intent.effect_class == "WRITE_IRREVERSIBLE":
        return "IRREVERSIBLE"
    if intent.security_sensitive or intent.effect_class == "SECURITY_SENSITIVE":
        return "SECURITY_SENSITIVE"
    if intent.external_mutation or (
        intent.effect_class in {"WRITE_REVERSIBLE", "WRITE_COMPENSATABLE"}
        and not intent.internal_sandbox_only
    ):
        return "EXTERNAL_MUTATION"
    if intent.persistent_internal_mutation:
        return "PERSISTENT_INTERNAL"
    if intent.effect_class == "READ_EXTERNAL":
        return "EXTERNAL_READ"
    if intent.effect_class == "WRITE_REVERSIBLE" and intent.internal_sandbox_only:
        return "REVERSIBLE_INTERNAL"
    if intent.effect_class == "READ_LOCAL":
        return "OBSERVATIONAL"
    return "PURE"


def assess_autonomy(intent: ActionIntent) -> ConsequenceAssessment:
    """Classify whether a new human/explicit authority grant is required.

    This function is pure. It never issues GovernanceDecision or ExecutionPermit
    objects and never performs the proposed action. A caller may use the result as
    deterministic policy input to the existing Nexus governance path.
    """

    consequence = _consequence_class(intent)
    reasons: list[str] = []

    if consequence == "INDETERMINATE":
        return ConsequenceAssessment(
            assessment_id=_assessment_id(intent),
            intent_id=intent.intent_id,
            consequence_class=consequence,
            material_consequence=True,
            authority_requirement="RECONCILIATION",
            disposition="READ_ONLY_RECONCILIATION",
            reason_codes=("INDETERMINATE_OUTCOME_REQUIRES_READ_ONLY_RECONCILIATION",),
            execution_may_continue_without_new_authority=False,
            automatic_retry_allowed=False,
        )

    safe_public_read = (
        consequence == "EXTERNAL_READ"
        and intent.public_read_only
        and not intent.accesses_private_data
        and not intent.credentials_required
        and intent.financial_spend_cad == Decimal("0")
    )
    safe_internal = consequence in {"PURE", "OBSERVATIONAL", "REVERSIBLE_INTERNAL"}

    material = not (safe_internal or safe_public_read)

    if intent.accesses_private_data:
        material = True
        reasons.append("PRIVATE_DATA_ACCESS")
    if intent.credentials_required:
        material = True
        reasons.append("CREDENTIAL_USE")
    if intent.financial_spend_cad > intent.authorized_spend_cad:
        material = True
        reasons.append("AUTHORIZED_SPEND_ENVELOPE_EXCEEDED")
    if intent.effect_class in _CONSEQUENTIAL_EFFECTS and not (
        intent.effect_class == "WRITE_REVERSIBLE" and intent.internal_sandbox_only
    ):
        material = True
        reasons.append("CONSEQUENTIAL_EFFECT_CLASS")

    if not material:
        reasons.append(
            "PUBLIC_READ_POLICY_PATH"
            if safe_public_read
            else "NON_CONSEQUENTIAL_POLICY_PATH"
        )
        return ConsequenceAssessment(
            assessment_id=_assessment_id(intent),
            intent_id=intent.intent_id,
            consequence_class=consequence,
            material_consequence=False,
            authority_requirement="POLICY",
            disposition="AUTONOMOUS_POLICY_PATH",
            reason_codes=tuple(sorted(set(reasons))),
            execution_may_continue_without_new_authority=True,
            automatic_retry_allowed=True,
        )

    if intent.existing_explicit_authority and intent.financial_spend_cad <= intent.authorized_spend_cad:
        reasons.append("EXISTING_EXPLICIT_AUTHORITY_PRESENT")
        return ConsequenceAssessment(
            assessment_id=_assessment_id(intent),
            intent_id=intent.intent_id,
            consequence_class=consequence,
            material_consequence=True,
            authority_requirement="EXISTING_EXPLICIT",
            disposition="AUTONOMOUS_WITHIN_EXISTING_AUTHORITY",
            reason_codes=tuple(sorted(set(reasons))),
            execution_may_continue_without_new_authority=True,
            automatic_retry_allowed=True,
        )

    reasons.append("NEW_EXPLICIT_AUTHORITY_REQUIRED")
    return ConsequenceAssessment(
        assessment_id=_assessment_id(intent),
        intent_id=intent.intent_id,
        consequence_class=consequence,
        material_consequence=True,
        authority_requirement="EXPLICIT",
        disposition="BLOCK_PENDING_EXPLICIT_AUTHORITY",
        reason_codes=tuple(sorted(set(reasons))),
        execution_may_continue_without_new_authority=False,
        automatic_retry_allowed=False,
    )
