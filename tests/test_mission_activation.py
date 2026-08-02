import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.mission_os.activation import build_activation_projection
from src.mission_os.api import create_mission_app


def _write_fixture(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    (root / "data/phase2_processed").mkdir(parents=True)
    (root / "data/phase3_processed").mkdir(parents=True)
    (root / "config/mission_os_offer_catalog.json").write_text(json.dumps({
        "offers": [{
            "offer_id": "offer-test", "name": "Test Blueprint", "status": "INTERNAL_DRAFT_ONLY",
            "deliverables": ["Blueprint"], "exclusions": ["Deployment"], "acceptance_criteria": ["Reviewed"],
            "fit_taxonomy": ["automation", "documentation"],
            "tiers": [{"tier_id": "standard", "price": 500, "delivery_business_days": 3, "operator_minutes_estimate": 120}],
            "external_action_authorized": False
        }], "external_action_authorized": False
    }), encoding="utf-8")
    (root / "data/phase2_processed/aigc_phase2_opportunity_queue.json").write_text("", encoding="utf-8")
    (root / "data/phase3_processed/aigc_phase3_assessment_dossiers.json").write_text(json.dumps([
        {"dossier_id": "d1", "opportunity_id": "opp-1", "title": "Automate documentation", "employer": "Example", "radar_score": 90, "discovered_taxonomy": ["automation", "documentation"]},
        {"dossier_id": "d2", "opportunity_id": "opp-2", "title": "Unrelated task", "employer": "Example 2", "radar_score": 40, "discovered_taxonomy": ["other"]}
    ]), encoding="utf-8")


def test_activation_is_ranked_bounded_and_non_executing(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    result = build_activation_projection(tmp_path)
    assert result["source_status"]["ranking_source"] == "PHASE_3_FALLBACK"
    assert result["ranked_opportunities"][0]["opportunity_id"] == "opp-1"
    assert result["internal_proposal_packets"][0]["status"] == "INTERNAL_DRAFT_ONLY"
    assert result["exact_action_approval_queue"][0]["status"] == "NOT_REQUESTED"
    assert result["daily_operator_brief"]["scheduled_minutes"] <= 120
    assert result["daily_operator_brief"]["external_actions_included"] is False
    assert result["external_action_authorized"] is False
    assert result["external_action_performed"] is False
    assert result["canonical_state_mutated"] is False


def test_evidence_chain_does_not_claim_revenue(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    chain = build_activation_projection(tmp_path)["revenue_evidence_chains"][0]
    states = {item["stage"]: item["state"] for item in chain["links"]}
    assert states["PROPOSAL"] == "INTERNAL_DRAFT"
    assert states["AUTHORIZATION"] == "NOT_REQUESTED"
    assert states["COLLECTION_RECEIPT"] == "BLOCKED"
    assert chain["verified_collected_cad"] == 0


def test_activation_api_is_get_only_and_loopback_bound(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    mission = tmp_path / "config/mission.json"
    mission.write_text(json.dumps({
        "schema_version":"1.0.0","mission_id":"mission_test_123456","title":"Test","objective":"Test.","accountable_owner":"ACCOUNTABLE_OPERATOR","state":"ACTIVE","confidence":0.5,"start_at":"2026-08-02T00:00:00Z","deadline_at":"2026-08-31T23:59:59Z","resource_envelope":{"currency":"CAD","spend_ceiling":0,"operator_minutes_per_day":120,"model_call_ceiling":10,"external_action_ceiling":0},"allowed_actions":["read"],"forbidden_actions":["write"],"objectives":[{"objective_id":"obj_test_123456","description":"Test","measurement":"count","target":1,"status":"IN_PROGRESS"}],"tasks":[],"dependencies":[],"approvals":[],"kpis":[],"evidence_requirements":[],"stop_conditions":["cancelled"],"created_at":"2026-08-02T00:00:00Z","updated_at":"2026-08-02T00:00:00Z","external_action_authorized":False
    }), encoding="utf-8")
    app = create_mission_app(tmp_path, mission, tmp_path / "missing.sqlite3")
    route = next(route for route in app.routes if route.path == "/api/v1/revenue/activation")
    assert route.methods == {"GET"}
    response = TestClient(app).get("/api/v1/revenue/activation")
    assert response.status_code == 200
    assert response.json()["external_action_performed"] is False
