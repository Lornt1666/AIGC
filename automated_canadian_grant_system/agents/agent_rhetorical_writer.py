from __future__ import annotations

from typing import Any

from automated_canadian_grant_system.core.models import (
    BusinessIdentity,
    GrantApplicationRequest,
)


class RhetoricalWriter:
    """Builds a reviewable narrative template without asserting unverified facts."""

    def draft(
        self,
        identity: BusinessIdentity,
        request: GrantApplicationRequest,
        research: dict[str, Any],
    ) -> dict[str, Any]:
        project = request.project
        grant = request.grant
        return {
            "status": "INTERNAL_DRAFT_ONLY",
            "executive_summary": (
                f"{identity.entity_name} proposes {project.project_title} for "
                f"consideration under {grant.grant_name}. This internal draft "
                "requires operator evidence for all technical, financial, "
                "ownership, and eligibility assertions before reuse."
            ),
            "project_description_for_review": project.project_summary,
            "claim_to_data_to_warrant": {
                "claim": (
                    f"{project.project_title} may advance the stated project "
                    "objective, subject to independently reviewed evidence."
                ),
                "data_required": [
                    "Operator-approved technical baseline and validation plan.",
                    "Traceable budget assumptions and source records.",
                    "Official program-guideline eligibility review.",
                ],
                "warrant": (
                    "The application may be considered only where reviewed "
                    "evidence supports alignment with the official program "
                    "requirements."
                ),
                "backing_required": [
                    "Official program documentation.",
                    "Business identity and ownership evidence.",
                    "Technical and financial supporting records.",
                ],
            },
            "work_breakdown_structure": [
                {
                    "period": "Months 1-3",
                    "activity": "Confirm requirements, baseline, and evidence plan.",
                    "evidence_required": "Operator-approved scope and baseline.",
                },
                {
                    "period": "Months 4-6",
                    "activity": "Develop and document the proposed prototype work.",
                    "evidence_required": "Traceable technical progress records.",
                },
                {
                    "period": "Months 7-9",
                    "activity": "Validate results against approved measures.",
                    "evidence_required": "Test method and result evidence.",
                },
                {
                    "period": "Months 10-12",
                    "activity": "Prepare final evidence and operator review package.",
                    "evidence_required": "Reviewed completion and impact records.",
                },
            ],
            "impact_metrics": [
                {
                    "metric": "Technical validation progress",
                    "baseline": "Operator evidence required.",
                    "target": "Operator-approved target required.",
                },
                {
                    "metric": "Commercialization readiness",
                    "baseline": "Operator evidence required.",
                    "target": "Operator-approved target required.",
                },
                {
                    "metric": "Environmental or operational impact",
                    "baseline": "Operator evidence required.",
                    "target": "Operator-approved target required.",
                },
            ],
            "research_state": research["eligibility_determination"],
            "ai_use_disclosure": (
                "This package is an AI-assisted internal draft and requires "
                "human review, factual verification, and any required "
                "disclosure before external use."
            ),
            "external_action_performed": False,
        }
