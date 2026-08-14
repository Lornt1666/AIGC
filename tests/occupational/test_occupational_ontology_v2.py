from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.occupational.ontology import (
    CommissionEconomics,
    CompetencyLevel,
    CompetencyRecord,
    CredentialRecord,
    CredentialStatus,
    ExperienceNode,
    ScopeOfPractice,
    action_permitted,
)


def test_verified_competency_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="requires evidence"):
        CompetencyRecord(
            competency_id="C1",
            domain="repository engineering",
            level=CompetencyLevel.VERIFIED,
            confidence=0.9,
        )

    record = CompetencyRecord(
        competency_id="C2",
        domain="repository engineering",
        level=CompetencyLevel.VERIFIED,
        evidence_receipt_ids=("ER-1",),
        confidence=0.9,
    )
    assert record.level is CompetencyLevel.VERIFIED


def test_accepted_experience_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="evidence-backed"):
        ExperienceNode(
            experience_id="E1",
            commission_id="WC1",
            discipline_id="REPOSITORY_ENGINEERING",
            difficulty="HIGH",
            outcome="ACCEPTED",
            human_review_required=True,
            rework_cycles=0,
        )


def test_credentials_do_not_imply_authority() -> None:
    credential = CredentialRecord(
        credential_id="CR1",
        holder="AIGC",
        issuer="example",
        credential_type="training",
        verification_status=CredentialStatus.VERIFIED,
        scope_granted=("course completion",),
    )
    assert credential.verification_status is CredentialStatus.VERIFIED
    assert not action_permitted(
        capability_present=True,
        competency_sufficient=True,
        scope_permits=True,
        authority_valid=False,
        jurisdiction_valid=True,
    )


def test_scope_and_authority_are_both_required() -> None:
    scope = ScopeOfPractice(
        independently_permitted=("repository analysis",),
        prohibited=("unauthorized system access",),
    )
    assert "repository analysis" in scope.independently_permitted
    assert action_permitted(
        capability_present=True,
        competency_sufficient=True,
        scope_permits=True,
        authority_valid=True,
        jurisdiction_valid=True,
    )
    assert not action_permitted(
        capability_present=True,
        competency_sufficient=True,
        scope_permits=False,
        authority_valid=True,
        jurisdiction_valid=True,
    )


def test_commission_economics_is_advisory_only() -> None:
    economics = CommissionEconomics(
        commission_id="WC1",
        expected_compensation=100,
        estimated_execution_cost=10,
        model_api_cost=5,
        compute_cost=5,
        human_review_cost=5,
        opportunity_cost=5,
        risk_cost=10,
        portfolio_value=20,
        learning_value=10,
        strategic_value=5,
    )
    assert economics.expected_utility == 95
    assert not action_permitted(
        capability_present=True,
        competency_sufficient=True,
        scope_permits=True,
        authority_valid=False,
        jurisdiction_valid=True,
    )
