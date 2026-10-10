from __future__ import annotations

from .models import GeminiAssessment, OpportunityIntake, PolicyEvaluation


def evaluate_policy(
    opportunity: OpportunityIntake,
    assessment: GeminiAssessment,
) -> PolicyEvaluation:
    reasons: list[str] = []
    if not opportunity.ai_assistance_permitted:
        return PolicyEvaluation(
            outcome="blocked",
            reasons=["The intake does not permit AI assistance."],
        )
    if assessment.human_review_required is not True:
        return PolicyEvaluation(
            outcome="blocked",
            reasons=["The assessment attempted to remove mandatory human review."],
        )
    if opportunity.ai_disclosure_required and not assessment.ai_use_disclosure.strip():
        return PolicyEvaluation(
            outcome="blocked",
            reasons=["Required AI-use disclosure is missing."],
        )
    allowed_pointers = {
        "/title",
        "/description",
        *{
            f"/constraints/{index}"
            for index, _value in enumerate(opportunity.constraints)
        },
    }
    invalid_pointers = sorted(
        {
            item.input_pointer
            for item in assessment.evidence_basis
            if item.input_pointer not in allowed_pointers
        }
    )
    if invalid_pointers:
        return PolicyEvaluation(
            outcome="blocked",
            reasons=[
                "The assessment cited input evidence that does not exist: "
                + ", ".join(invalid_pointers)
            ],
        )
    untrusted_text = " ".join(
        [opportunity.title, opportunity.description, *opportunity.constraints]
    ).lower()
    injection_signals = (
        "ignore previous instructions",
        "ignore all instructions",
        "reveal the system prompt",
        "show your system prompt",
        "exfiltrate",
    )
    if any(signal in untrusted_text for signal in injection_signals):
        reasons.append(
            "The supplied brief contains an instruction-injection signal and "
            "requires clarification."
        )
    severe = [
        risk for risk in assessment.risks if risk.severity in {"high", "critical"}
    ]
    if severe:
        reasons.append("High or critical risks require clarification before approval.")
    if assessment.fit_score < 50 and assessment.recommendation == "pursue":
        reasons.append("A pursue recommendation conflicts with the low fit score.")
    if assessment.recommendation == "clarify":
        reasons.append("Gemini recommends clarification.")
    if reasons:
        return PolicyEvaluation(
            outcome="clarification_required",
            reasons=reasons,
        )
    if assessment.recommendation == "decline":
        return PolicyEvaluation(
            outcome="blocked",
            reasons=["Gemini recommends declining the opportunity."],
        )
    return PolicyEvaluation(
        outcome="allow_internal_draft",
        reasons=[
            "The structured assessment passed deterministic internal-draft checks.",
            "Human approval remains mandatory and no external business action "
            "is authorized.",
        ],
    )
