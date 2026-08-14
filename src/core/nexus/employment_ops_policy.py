from __future__ import annotations

from decimal import Decimal

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.autonomy_policy import assess_autonomy
from src.domain.nexus.autonomy import ActionIntent, ConsequenceAssessment
from src.domain.nexus.employment_ops import EmploymentActionType


_SAFE_ACTIONS = {
    "DISCOVER_JOBS",
    "NORMALIZE_JOB",
    "SCAM_ANALYSIS",
    "ELIGIBILITY_ANALYSIS",
    "FIT_SCORING",
    "EMPLOYER_RESEARCH",
    "TAILOR_RESUME",
    "DRAFT_COVER_LETTER",
    "DRAFT_APPLICATION_ANSWERS",
    "ATS_NAVIGATE",
    "ATS_PREFILL_SAFE_FIELDS",
}

_COMMUNICATION_ACTIONS = {
    "SEND_RECRUITER_MESSAGE",
    "ANSWER_CALL",
    "SPEAK_TO_CALLER",
    "NEGOTIATE",
    "INTERVIEW_DIALOGUE",
    "ASK_RECRUITER_QUESTION",
}


def _intent_id(action: EmploymentActionType, subject_ref: str) -> str:
    return "ACT-" + canonical_sha256({"action": action, "subject_ref": subject_ref})[:24].upper()


def employment_action_intent(
    *,
    action: EmploymentActionType,
    subject_ref: str,
    existing_permit_id: str | None = None,
    requested_cost_cad: Decimal = Decimal("0.00"),
    authorized_cost_cad: Decimal = Decimal("0.00"),
) -> ActionIntent:
    """Compile employment operations into the existing Nexus consequence model."""

    if action in _SAFE_ACTIONS:
        return ActionIntent(
            intent_id=_intent_id(action, subject_ref),
            effect_class="PURE" if action != "ATS_NAVIGATE" else "READ_LOCAL",
            internal_sandbox_only=action == "ATS_PREFILL_SAFE_FIELDS",
        )

    has_authority = existing_permit_id is not None
    common = {
        "intent_id": _intent_id(action, subject_ref),
        "financial_spend_cad": requested_cost_cad,
        "authorized_spend_cad": authorized_cost_cad,
        "existing_explicit_authority": has_authority,
        "permit_id": existing_permit_id,
    }

    if action == "SUBMIT_APPLICATION":
        return ActionIntent(
            **common,
            effect_class="WRITE_COMPENSATABLE",
            external_mutation=True,
        )
    if action in _COMMUNICATION_ACTIONS:
        return ActionIntent(
            **common,
            effect_class="COMMUNICATION",
            communication=True,
        )
    if action == "DISCLOSE_SENSITIVE_IDENTITY":
        return ActionIntent(
            **common,
            effect_class="SECURITY_SENSITIVE",
            accesses_private_data=True,
            security_sensitive=True,
        )
    raise ValueError(f"unsupported employment action: {action}")


def assess_employment_action(**kwargs: object) -> ConsequenceAssessment:
    return assess_autonomy(employment_action_intent(**kwargs))
