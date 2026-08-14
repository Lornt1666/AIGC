from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.validate_aigc_procurement_sandbox import (
    ProcurementValidationError,
    validate_procurement_sandbox,
)


ROOT = Path(__file__).resolve().parents[1]


def test_procurement_sandbox_validates_as_inert_and_complete() -> None:
    receipt = validate_procurement_sandbox()
    assert receipt["catalog_agent_count"] == 13
    assert receipt["scenario_count"] == 12
    assert receipt["applicable_required_checks"] == 34
    assert receipt["verified_required_checks"] == 34
    assert receipt["verified_applicable_ratio"] == 1.0
    assert receipt["simulation_result"] == "PASS_LOCAL"
    assert receipt["production_ready"] is False
    assert receipt["authority_granted"] is False
    assert receipt["deployment_performed"] is False
    assert receipt["external_action_performed"] is False
    assert len(receipt["artifact_sha256"]) == 64
    assert len(receipt["receipt_sha256"]) == 64


def test_catalog_corrects_agent_count_and_never_claims_evidence() -> None:
    catalog = json.loads(
        (ROOT / "config/procurement/agent_catalog.v1.json").read_text(encoding="utf-8")
    )
    assert catalog["agent_count"] == len(catalog["agents"]) == 13
    assert catalog["shared_assertions"] == {
        "implementation_status": "DESIGN_ONLY",
        "model_evidence_status": "UNVERIFIED",
        "dataset_evidence_status": "UNVERIFIED",
        "effect_ceiling": "LOCAL_SIMULATION_ONLY",
        "external_action_authorized": False,
        "external_action_performed": False,
    }
    assert all("auth_scope" not in agent for agent in catalog["agents"])
    schema = json.loads(
        (ROOT / "schemas/aigc_procurement_agent_catalog.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(catalog)


def test_validator_rejects_authority_if_seed_is_mutated(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.validate_aigc_procurement_sandbox as validator

    original = validator._json

    def mutated(relative: str):
        payload = original(relative)
        if relative.endswith("edge_compute_seed.v1.json"):
            payload["authority"]["spend_authorized"] = True
        return payload

    monkeypatch.setattr(validator, "_json", mutated)
    with pytest.raises(ProcurementValidationError, match="cannot grant"):
        validator.validate_procurement_sandbox()


def test_policy_modules_cover_all_material_boundaries() -> None:
    policies = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "policy/procurement").glob("*.rego"))
    )
    for term in (
        "send_payment",
        "publish_contract",
        "one_use",
        "reconciliation_required",
        "sanctions_match",
        "KYC",
        "raw PII",
    ):
        assert term in policies


def test_procurement_docs_contain_renderable_architecture_diagrams() -> None:
    sandbox = (ROOT / "docs/architecture/AIGC_PROCUREMENT_SANDBOX_V1.md").read_text(
        encoding="utf-8"
    )
    alpha = (ROOT / "docs/architecture/AIGC_ALPHA_PLAN_ORCHESTRATOR_V1.md").read_text(
        encoding="utf-8"
    )
    assert sandbox.count("```mermaid") >= 2
    assert alpha.count("```mermaid") >= 3
    assert "13 agents" in sandbox
