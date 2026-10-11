from __future__ import annotations

import re
from typing import Any

from automated_canadian_grant_system.core.models import (
    BusinessIdentity,
    GrantApplicationRequest,
)


UNSUPPORTED_CLAIM_PATTERNS = {
    "UNSUPPORTED_GUARANTEE_CLAIM": re.compile(
        r"\b(guarantee|guaranteed|will be awarded)\b",
        re.IGNORECASE,
    ),
    "UNSUPPORTED_APPROVAL_CLAIM": re.compile(
        r"\b(already approved|pre-approved|preapproved)\b",
        re.IGNORECASE,
    ),
}


class RedTeamVerifier:
    """Finds evidence and compliance gaps before an operator review."""

    def audit(
        self,
        identity: BusinessIdentity,
        request: GrantApplicationRequest,
        research: dict[str, Any],
        financial: dict[str, Any],
        draft: dict[str, Any],
    ) -> dict[str, Any]:
        findings: list[dict[str, str | bool]] = [
            self._finding(
                "IDENTITY_ATTESTATION_REQUIRED",
                "blocking",
                "The business profile is operator-supplied and has not been independently verified.",
            ),
            self._finding(
                "OFFICIAL_GUIDELINE_REVIEW_REQUIRED",
                "blocking",
                "ACGS did not verify the grant guideline, opening status, or program eligibility.",
            ),
            self._finding(
                "EXTERNAL_SUBMISSION_BLOCKED",
                "blocking",
                "The local baseline cannot submit an application or use credentials.",
            ),
        ]
        if research["eligibility_determination"] == "INELIGIBLE_BY_SUPPLIED_CRITERIA":
            findings.append(
                self._finding(
                    "SUPPLIED_ELIGIBILITY_CRITERION_MISMATCH",
                    "blocking",
                    "At least one operator-supplied criterion does not match the working profile.",
                )
            )
        for finding in financial["findings"]:
            findings.append(
                self._finding(
                    str(finding["code"]),
                    str(finding["severity"]),
                    str(finding["message"]),
                )
            )

        source_text = " ".join(
            [
                request.grant.grant_name,
                request.grant.summary,
                request.project.project_title,
                request.project.project_summary,
                draft["executive_summary"],
            ]
        )
        for code, pattern in UNSUPPORTED_CLAIM_PATTERNS.items():
            if pattern.search(source_text):
                findings.append(
                    self._finding(
                        code,
                        "review_required",
                        "Potential unsupported outcome or approval language requires operator review.",
                    )
                )

        return {
            "status": "REVIEW_REQUIRED",
            "fmea": [
                {
                    "failure_mode": "Unverified business or program eligibility",
                    "effect": "An external application could contain unsupported claims.",
                    "control": "Independent operator review and Phase 5 approval.",
                },
                {
                    "failure_mode": "Unverified financial assumptions",
                    "effect": "Budget may not comply with program requirements.",
                    "control": "Official-guideline and source-record reconciliation.",
                },
                {
                    "failure_mode": "Unapproved portal interaction",
                    "effect": "Potential violation of governance or portal conditions.",
                    "control": "No remote retrieval, credential use, or submission in this baseline.",
                },
            ],
            "findings": findings,
            "audit_score": None,
            "audit_score_note": (
                "No numeric audit score is issued because ACGS has not "
                "independently verified the underlying evidence."
            ),
            "identity_verification_status": identity.verification_status,
            "external_action_performed": False,
        }

    @staticmethod
    def _finding(
        code: str,
        severity: str,
        message: str,
    ) -> dict[str, str | bool]:
        return {
            "code": code,
            "severity": severity,
            "message": message,
            "blocking_for_submission": severity == "blocking",
        }
