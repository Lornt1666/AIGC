from __future__ import annotations

from automated_canadian_grant_system.core.models import (
    GrantApplicationRequest,
)
from automated_canadian_grant_system.core.orchestrator import GrantOrchestrator


def application_payload(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "grant": {
            "grant_id": "alberta_demo_001",
            "portal_id": "alberta_innovates",
            "grant_name": "Operator-supplied clean technology demonstration call",
            "guideline_url": "https://albertainnovates.ca/funding/",
            "summary": (
                "An operator-supplied summary for local comparison only. "
                "Official guideline review remains required."
            ),
            "eligibility": {
                "eligible_regions": ["Alberta"],
                "min_trl": 6,
                "max_trl": 7,
                "min_headcount": 1,
                "max_headcount": 10,
                "requires_ccpc": True,
                "minimum_annual_rd_spend_cad": 100000,
                "funding_ceiling_cad": 100000,
                "required_matching_ratio": 0.5,
                "source_verification_status": "operator_review_required",
            },
        },
        "project": {
            "project_title": "Solar-collecting smart siding prototype",
            "project_summary": (
                "Develop and validate a prototype through an operator-approved "
                "technical evidence plan."
            ),
            "requested_funding_cad": 100000,
            "matching_contribution_cad": 50000,
            "duration_months": 12,
        },
    }
    for key, value in overrides.items():
        payload[key] = value
    return payload


def test_pipeline_generates_a_reviewable_local_draft() -> None:
    orchestrator = GrantOrchestrator()
    package = orchestrator.generate(
        GrantApplicationRequest.model_validate(application_payload())
    )

    assert package["status"] == "AUDITED_REVIEW_REQUIRED"
    assert package["lifecycle"][-1] == "SUBMISSION_BLOCKED"
    assert len(package["applied_prompt_modules"]) == 15
    assert package["research"]["eligibility_determination"] == "REVIEW_REQUIRED"
    assert package["research"]["heuristic_match_score"] == 100
    assert (
        len(package["financial_review"]["monthly_budget"])
        == 12
    )
    assert round(
        sum(
            row["total_planned_cad"]
            for row in package["financial_review"]["monthly_budget"]
        ),
        2,
    ) == 150000
    assert package["red_team_audit"]["audit_score"] is None
    assert (
        package["submission"]["status"]
        == "BLOCKED_PENDING_PHASE5_APPROVAL"
    )
    assert package["external_action_performed"] is False


def test_pipeline_flags_a_funding_ceiling_and_matching_shortfall() -> None:
    payload = application_payload()
    project = dict(payload["project"])
    project["requested_funding_cad"] = 100001
    project["matching_contribution_cad"] = 0
    payload["project"] = project
    package = GrantOrchestrator().generate(
        GrantApplicationRequest.model_validate(payload)
    )

    findings = {
        item["code"] for item in package["financial_review"]["findings"]
    }
    assert "FUNDING_CEILING_EXCEEDED" in findings
    assert "MATCHING_CONTRIBUTION_INSUFFICIENT" in findings
    assert package["submission"]["external_submission_performed"] is False
