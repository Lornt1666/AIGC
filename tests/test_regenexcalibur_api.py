from __future__ import annotations

from fastapi.testclient import TestClient

from src.webapp.regenexcalibur_api import create_regenexcalibur_app


def coordination_request() -> dict[str, object]:
    return {
        "request_id": "COORD-REQ-API001",
        "objective": "Coordinate a bounded local design and verification pass.",
        "state": {
            "state_id": "COORD-STATE-API001",
            "revision": 0,
            "artifact_refs": [],
            "values": {"phase": "design"},
        },
        "tools": [
            {
                "tool_id": "TOOL-LOCAL-VERIFY",
                "function_name": "verification.run",
                "purpose": "Run deterministic local verification.",
                "effect_class": "PURE",
            }
        ],
        "agents": [
            {
                "agent_id": "AGT-ENGINEER",
                "role": "AUTO_ENGINEER",
                "mandate": "Engineer the bounded candidate implementation.",
                "assigned_tool_ids": ["TOOL-LOCAL-VERIFY"],
                "output_contract": "candidate and verification receipt",
                "verification_function": "verification.run",
            }
        ],
        "acceptance_criteria": ["receipt proves zero egress"],
    }


def test_health_and_planning_api_are_local_non_authorizing_surfaces():
    client = TestClient(create_regenexcalibur_app())
    health = client.get("/health")
    planned = client.post(
        "/v1/coordinator/plan",
        json={
            "request_id": "RXREQ-API001",
            "workflow": "APPLY_JOBS",
            "objective": "Prepare a truthful application packet.",
            "artifact_refs": [],
        },
    )

    assert health.status_code == 200
    assert health.json()["status"] == "PASS"
    assert planned.status_code == 200
    assert planned.json()["terminal_status"] == "BLOCKED"
    assert planned.json()["external_actions_performed"] == 0


def test_diagnostics_api_runs_all_six_isolated_scenarios():
    response = TestClient(create_regenexcalibur_app()).post("/v1/diagnostics/run")
    assert response.status_code == 200
    assert response.json()["detected_count"] == 6
    assert response.json()["terminal_status"] == "PASS"


def test_coordination_engineering_endpoint_exposes_a_closed_zero_egress_contract():
    client = TestClient(create_regenexcalibur_app())
    response = client.post("/v1/coordination/engineer", json=coordination_request())

    assert response.status_code == 200
    assert response.json()["terminal_status"] == "PASS"
    assert response.json()["tool_dispatches_performed"] == 0
    assert response.json()["authority_granted"] is False

    openapi = client.get("/openapi.json").json()
    operation = openapi["paths"]["/v1/coordination/engineer"]["post"]
    assert operation["summary"] == "Engineer a deterministic AIGC coordination plan"
    request_schema = openapi["components"]["schemas"]["CoordinationEngineeringRequest"]
    assert request_schema["additionalProperties"] is False
    serialized = str(request_schema)
    assert "permit_id" not in serialized
    assert "authority_granted" not in serialized


def test_coordination_endpoint_rejects_caller_secret_material_with_422():
    payload = coordination_request()
    payload["tools"][0]["parameters"] = {"token": "not-accepted"}
    response = TestClient(create_regenexcalibur_app()).post(
        "/v1/coordination/engineer", json=payload
    )

    assert response.status_code == 422
