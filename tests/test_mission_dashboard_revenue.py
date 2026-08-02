import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.mission_os.api import create_mission_app
from src.mission_os.dashboard import build_dashboard_payload, render_dashboard_html
from src.mission_os.revenue import project_revenue_pipeline


def test_revenue_adapter_separates_estimates_from_evidenced_cash(tmp_path: Path) -> None:
    finance = tmp_path / "data/phase15_finance"
    finance.mkdir(parents=True)
    (finance / "aigc_phase15_finance_ledger.json").write_text(json.dumps([
        {"estimated_revenue": 900, "currency": "CAD"},
        {"collected_revenue": 250, "currency": "CAD"},
        {"collected_revenue": 300, "currency": "CAD", "receipt_id": "receipt-1"},
    ]), encoding="utf-8")
    payload = project_revenue_pipeline(tmp_path)
    assert payload["financials"]["estimated_pipeline"] == 900
    assert payload["financials"]["verified_collected"] == 300
    assert payload["external_action_performed"] is False
    assert payload["canonical_state_mutated"] is False


def test_dashboard_payload_and_html_preserve_read_only_boundary() -> None:
    snapshot = {
        "mission": {"title": "Revenue mission", "state": "ACTIVE"},
        "summary": {"mission_progress_percent": 25, "sources_available": 2, "sources_missing": 1, "sources_invalid": 0},
        "highest_impact_next_action": "Review proposal.",
        "approvals_waiting": ["approval-1"], "blockers": [], "quests": [], "phase_registry": [], "warnings": [],
    }
    revenue = {"financials": {"verified_collected": 0, "estimated_pipeline": 500, "verification_rule": "Evidence required."}, "funnel": {"proposals": 2}}
    payload = build_dashboard_payload(snapshot, revenue)
    html = render_dashboard_html(payload)
    assert payload["mode"] == "READ_ONLY"
    assert payload["external_action_performed"] is False
    assert "Read-only projection" in html
    assert "CAD 500.00" in html


def test_mission_api_registers_only_get_routes_for_dashboard(tmp_path: Path) -> None:
    mission = tmp_path / "mission.json"
    mission.write_text(json.dumps({
        "schema_version":"1.0.0","mission_id":"mission_test_123456","title":"Test","objective":"Test read only projection.","accountable_owner":"ACCOUNTABLE_OPERATOR","state":"ACTIVE","confidence":0.5,"start_at":"2026-08-02T00:00:00Z","deadline_at":"2026-08-31T23:59:59Z","resource_envelope":{"currency":"CAD","spend_ceiling":0,"operator_minutes_per_day":120,"model_call_ceiling":10,"external_action_ceiling":0},"allowed_actions":["read"],"forbidden_actions":["write"],"objectives":[{"objective_id":"obj_test_123456","description":"Test","measurement":"count","target":1,"status":"IN_PROGRESS"}],"tasks":[],"dependencies":[],"approvals":[],"kpis":[],"evidence_requirements":[],"stop_conditions":["cancelled"],"created_at":"2026-08-02T00:00:00Z","updated_at":"2026-08-02T00:00:00Z","external_action_authorized":False
    }), encoding="utf-8")
    app = create_mission_app(tmp_path, mission, tmp_path / "missing.sqlite3")
    methods = {method for route in app.routes for method in getattr(route, "methods", set()) if route.path in {"/dashboard", "/api/v1/dashboard", "/api/v1/revenue/pipeline"}}
    assert methods == {"GET"}
    response = TestClient(app).get("/api/v1/revenue/pipeline")
    assert response.status_code == 200
    assert response.json()["external_action_performed"] is False
