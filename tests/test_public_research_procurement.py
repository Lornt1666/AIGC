from __future__ import annotations

from src.core.contract_validator import validate_artifact
from src.core.public_research_procurement import (
    FORBIDDEN_PROCUREMENT_TARGETS,
    build_public_research_procurement_catalog,
    validate_public_research_procurement_catalog,
)


def test_public_research_procurement_catalog_validates() -> None:
    catalog = build_public_research_procurement_catalog()

    assert validate_artifact("public_research_procurement_catalog", catalog) == catalog
    assert validate_public_research_procurement_catalog(catalog) == catalog
    assert catalog["external_action_performed"] is False
    assert catalog["procurement_boundary"]["credentials_read"] is False
    assert catalog["procurement_boundary"]["live_actions_executed"] is False


def test_sources_are_public_https_and_high_credibility() -> None:
    catalog = build_public_research_procurement_catalog()

    source_types = {source["source_type"] for source in catalog["sources"]}
    assert "official_standard" in source_types
    assert "official_security_project" in source_types
    assert "official_product_documentation" in source_types
    for source in catalog["sources"]:
        assert source["url"].startswith("https://")
        assert source["credibility_score"] >= 4
        assert source["applicability_score"] >= 3
        assert source["safe_borrow"]
        assert source["avoid"]


def test_every_procured_layer_has_sources_tests_and_forbidden_blocks() -> None:
    catalog = build_public_research_procurement_catalog()
    source_ids = {source["source_id"] for source in catalog["sources"]}

    for layer in catalog["procured_layers"]:
        assert set(layer["source_ids"]).issubset(source_ids)
        assert layer["missing_reason"]
        assert layer["procurement_action"]
        assert layer["acceptance_tests"]
        assert layer["risk_controls"]
        assert layer["human_review_required"] is True
        assert layer["external_action_performed"] is False
        assert set(FORBIDDEN_PROCUREMENT_TARGETS).issubset(set(layer["forbidden_targets_blocked"]))


def test_catalog_identifies_required_missing_layers() -> None:
    catalog = build_public_research_procurement_catalog()
    layer_ids = {layer["layer_id"] for layer in catalog["procured_layers"]}

    expected = {
        "layer_public_research_provenance",
        "layer_ai_rmf_govern_map_measure_manage",
        "layer_tool_guardrail_mesh",
        "layer_human_interrupt_resume",
        "layer_durable_workflow_readiness",
        "layer_data_workflow_observability",
        "layer_supply_chain_provenance",
        "layer_prompt_injection_red_team",
        "layer_privacy_retention_classification",
        "layer_cost_rate_limit_budget",
        "layer_post_quantum_crypto_provider",
        "layer_buyer_tenant_isolation",
    }
    assert expected.issubset(layer_ids)


def test_procurement_catalog_does_not_procure_forbidden_capabilities() -> None:
    catalog = build_public_research_procurement_catalog()
    serialized = str(catalog).lower()

    assert "procurement_boundary" in serialized
    for forbidden in FORBIDDEN_PROCUREMENT_TARGETS:
        assert forbidden in catalog["forbidden_procurement_targets"]
    assert catalog["procurement_boundary"]["external_services_installed"] is False
    assert catalog["procurement_boundary"]["accounts_configured"] is False
