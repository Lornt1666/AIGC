import pytest

from src.core.omega_worker_ingestion import InvalidOpportunity, OpportunityIngestor


def opportunity(decision="PENDING"):
    return {
        "contract_version": "AIGC-OMEGA-OPPORTUNITY-0.1",
        "opportunity_id": "opp-001",
        "source": {"kind": "test", "locator": "test://opportunity"},
        "title": "AI workflow implementation",
        "classification": {
            "domain": "software",
            "engagement_type": "project",
            "duration": "short",
        },
        "commercial": {
            "pay_structure": "fixed",
            "amount": 1000,
            "currency": "CAD",
            "recurring_potential": False,
        },
        "fit": {"capability_score": 80, "strategic_score": 75, "evidence": []},
        "risk": {"level": "low", "factors": []},
        "decision": decision,
    }


def test_ingestion_binds_valid_opportunity_to_discovered_evaluation():
    ingestor = OpportunityIngestor()
    result = ingestor.ingest(opportunity(), iteration_id="iter-001")

    assert result.accepted is True
    assert result.disposition == "EVALUATE"
    assert ingestor.runtime.state == "EVALUATING"
    assert ingestor.runtime.evidence[0].contract_id == "opp-001"


def test_ingestion_rejects_missing_required_data_before_runtime_transition():
    value = opportunity()
    del value["fit"]

    ingestor = OpportunityIngestor()
    with pytest.raises(InvalidOpportunity):
        ingestor.ingest(value, iteration_id="iter-002")

    assert ingestor.runtime.state == "DISCOVERED"
    assert ingestor.runtime.evidence == []


def test_ingestion_rejects_unsupported_top_level_fields():
    value = opportunity()
    value["unauthorized_action"] = "submit"

    with pytest.raises(InvalidOpportunity):
        OpportunityIngestor().ingest(value, iteration_id="iter-003")


def test_ingestion_never_promotes_pending_opportunity_to_approval():
    ingestor = OpportunityIngestor()
    result = ingestor.ingest(opportunity("PENDING"), iteration_id="iter-004")

    assert result.disposition == "EVALUATE"
    assert ingestor.runtime.state == "EVALUATING"
    assert ingestor.runtime.state != "APPROVED"
