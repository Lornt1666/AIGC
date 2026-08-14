from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.core.nexus.research_procurement import (
    build_deep_research_plan,
    load_deep_research_policy,
)
from src.domain.nexus.research import ResearchProcurementRequest


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "aigc_deep_research_policy.v1.json"
SCHEMA_PATH = ROOT / "schemas" / "aigc_deep_research_policy.schema.json"


def test_deep_research_policy_is_closed_and_provider_dispatch_is_disabled():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert list(Draft202012Validator(schema).iter_errors(policy)) == []
    loaded = load_deep_research_policy()
    assert loaded.provider_dispatch_enabled is False
    assert loaded.grants_execution_authority is False
    assert loaded.minimum_primary_sources >= 2
    assert loaded.minimum_independent_domains >= 2


def test_deep_research_plan_is_deterministic_zero_egress_and_fail_closed():
    request = ResearchProcurementRequest(
        request_id="RESEARCH-OCCUPATION-PACKS-001",
        question="Which additional digitally performable occupation packs should AIGC evaluate next?",
        intended_decision="Prioritize the next governed occupation-pack implementation cycle.",
        jurisdictions=("Canada", "United States", "European Union"),
        maximum_sources=24,
        maximum_spend_cad="25.00",
    )
    first = build_deep_research_plan(request)
    second = build_deep_research_plan(request)
    assert first == second
    assert first["provider_call_count"] == 0
    assert first["external_action_performed"] is False
    assert first["authority_granted"] is False
    assert first["final_status"] == "BLOCKED_BEFORE_SOURCE_RETRIEVAL"
    assert first["stages"][0]["status"] == "READY_LOCAL"
    assert first["stages"][1]["status"] == "BLOCKED_EXTERNAL"
    assert first["quality_gates"]["unsupported_material_claims_maximum"] == 0
    assert first["quality_gates"]["material_claim_citation_coverage_minimum"] == 1.0


def test_research_request_rejects_raw_secrets_and_caller_authority():
    with pytest.raises(ValueError, match="credential-like"):
        build_deep_research_plan(
            ResearchProcurementRequest(
                request_id="RESEARCH-SECRET-001",
                question="Investigate this account using sk-proj-abcdefghijklmnopqrstuvwxyz123456.",
                intended_decision="Determine whether the credential can access a provider.",
            )
        )

    with pytest.raises(ValidationError):
        ResearchProcurementRequest(
            request_id="RESEARCH-AUTHORITY-001",
            question="Research safe automation boundaries for employer communication workflows.",
            intended_decision="Choose a bounded communication architecture.",
            execution_authorized=True,
        )


def test_research_question_requires_decision_relevance_and_bounded_source_count():
    with pytest.raises(ValidationError):
        ResearchProcurementRequest(
            request_id="RESEARCH-SHORT-001",
            question="Why?",
            intended_decision="Decide.",
        )
    with pytest.raises(ValidationError):
        ResearchProcurementRequest(
            request_id="RESEARCH-MANY-001",
            question="Research the governing evidence for an occupation capability admission decision.",
            intended_decision="Determine whether the capability may enter shadow evaluation.",
            maximum_sources=501,
        )
