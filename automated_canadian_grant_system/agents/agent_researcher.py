from __future__ import annotations

import re
from typing import Any

from automated_canadian_grant_system.core.models import (
    BusinessIdentity,
    GrantApplicationRequest,
)
from automated_canadian_grant_system.core.vector_retrieval import (
    LocalGrantRetriever,
)


TRL_PATTERN = re.compile(r"\bTRL\s*([1-9])\b", re.IGNORECASE)


class GrantResearcher:
    """Matches operator-supplied criteria without deciding eligibility."""

    def assess(
        self,
        identity: BusinessIdentity,
        request: GrantApplicationRequest,
        retriever: LocalGrantRetriever,
    ) -> dict[str, Any]:
        criteria = request.grant.eligibility
        checks: list[dict[str, str]] = []
        score_inputs: list[bool] = []
        profile_regions = (
            f"{identity.headquarters} {identity.operational_region}".lower()
        )

        if criteria.eligible_regions:
            region_match = any(
                region.lower() in profile_regions
                for region in criteria.eligible_regions
            )
            checks.append(
                self._check(
                    "region",
                    region_match,
                    "Working-profile location compared with operator-supplied regions.",
                )
            )
            score_inputs.append(region_match)

        trl = self._extract_trl(identity.technology_readiness_level)
        if criteria.min_trl is not None:
            match = trl is not None and trl >= criteria.min_trl
            checks.append(
                self._check(
                    "minimum_trl",
                    match,
                    "Working-profile TRL compared with the supplied minimum.",
                )
            )
            score_inputs.append(match)
        if criteria.max_trl is not None:
            match = trl is not None and trl <= criteria.max_trl
            checks.append(
                self._check(
                    "maximum_trl",
                    match,
                    "Working-profile TRL compared with the supplied maximum.",
                )
            )
            score_inputs.append(match)

        if criteria.min_headcount is not None:
            match = identity.headcount >= criteria.min_headcount
            checks.append(
                self._check(
                    "minimum_headcount",
                    match,
                    "Working-profile headcount compared with the supplied minimum.",
                )
            )
            score_inputs.append(match)
        if criteria.max_headcount is not None:
            match = identity.headcount <= criteria.max_headcount
            checks.append(
                self._check(
                    "maximum_headcount",
                    match,
                    "Working-profile headcount compared with the supplied maximum.",
                )
            )
            score_inputs.append(match)

        if criteria.requires_ccpc is not None:
            match = (
                identity.canadian_controlled_private_corporation
                == criteria.requires_ccpc
            )
            checks.append(
                self._check(
                    "ccpc_status",
                    match,
                    "Working-profile CCPC field compared with the supplied criterion.",
                )
            )
            score_inputs.append(match)

        if criteria.minimum_annual_rd_spend_cad is not None:
            match = (
                identity.annual_rd_spend_cad
                >= criteria.minimum_annual_rd_spend_cad
            )
            checks.append(
                self._check(
                    "minimum_rd_spend",
                    match,
                    "Working-profile R&D spend compared with the supplied threshold.",
                )
            )
            score_inputs.append(match)

        checks.append(
            {
                "criterion": "official_guideline_review",
                "status": "REVIEW_REQUIRED",
                "detail": (
                    "ACGS did not fetch or verify the program guideline. "
                    "An accountable operator must review the official source."
                ),
            }
        )
        has_mismatch = any(check["status"] == "NO_MATCH" for check in checks)
        query = f"{request.grant.grant_name} {request.project.project_title}"
        historical_matches = [
            {
                "document_id": match.document_id,
                "title": match.title,
                "source_reference": match.source_reference,
                "score": match.score,
            }
            for match in retriever.search(query)
        ]
        return {
            "eligibility_determination": (
                "INELIGIBLE_BY_SUPPLIED_CRITERIA"
                if has_mismatch
                else "REVIEW_REQUIRED"
            ),
            "heuristic_match_score": self._score(score_inputs),
            "score_disclaimer": (
                "This is a deterministic comparison of operator-supplied "
                "fields, not a grant eligibility decision."
            ),
            "criteria_checks": checks,
            "historical_retrieval_matches": historical_matches,
            "historical_retrieval_note": (
                "No historical material is included unless it has passed a "
                "separate rights review."
            ),
            "external_action_performed": False,
        }

    @staticmethod
    def _extract_trl(value: str) -> int | None:
        match = TRL_PATTERN.search(value)
        return int(match.group(1)) if match else None

    @staticmethod
    def _check(criterion: str, matches: bool, detail: str) -> dict[str, str]:
        return {
            "criterion": criterion,
            "status": "MATCH" if matches else "NO_MATCH",
            "detail": detail,
        }

    @staticmethod
    def _score(inputs: list[bool]) -> int:
        if not inputs:
            return 0
        return round(sum(inputs) * 100 / len(inputs))
