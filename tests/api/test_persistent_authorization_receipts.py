from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app


def test_authorization_receipt_survives_application_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "operator.sqlite3"

    first_client = TestClient(create_app(database_path=database_path))
    bundle = first_client.get("/api/v1/identity/example").json()
    authorization = first_client.post("/api/v1/identity/authorize", json=bundle)

    assert authorization.status_code == 200
    receipt_id = authorization.json()["receipt_id"]
    first_receipt = first_client.get(f"/api/v1/audit/receipts/{receipt_id}")
    assert first_receipt.status_code == 200
    assert first_receipt.json()["external_action_performed"] is False

    restarted_client = TestClient(create_app(database_path=database_path))
    restarted_receipt = restarted_client.get(f"/api/v1/audit/receipts/{receipt_id}")

    assert restarted_receipt.status_code == 200
    assert restarted_receipt.json() == first_receipt.json()


def test_same_authority_bundle_is_idempotent_across_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "operator.sqlite3"
    bundle_client = TestClient(create_app(database_path=database_path))
    bundle = bundle_client.get("/api/v1/identity/example").json()

    first = bundle_client.post("/api/v1/identity/authorize", json=bundle)
    restarted_client = TestClient(create_app(database_path=database_path))
    replay = restarted_client.post("/api/v1/identity/authorize", json=bundle)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["receipt_id"] == first.json()["receipt_id"]
    assert replay.json()["receipt"] == first.json()["receipt"]


def test_changed_authority_context_does_not_replay_prior_permit(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "operator.sqlite3"))
    valid_bundle = client.get("/api/v1/identity/example").json()
    valid = client.post("/api/v1/identity/authorize", json=valid_bundle)

    substituted_bundle = deepcopy(valid_bundle)
    substituted_bundle["sessions"][0]["principal_id"] = "principal-b"
    substituted = client.post("/api/v1/identity/authorize", json=substituted_bundle)

    assert valid.status_code == 200
    assert valid.json()["result"] in {"PERMIT", "REVIEW_REQUIRED"}
    assert substituted.status_code == 200
    assert substituted.json()["result"] == "DENY"
    assert "SESSION_PRINCIPAL_MISMATCH" in substituted.json()["reason_codes"]
    assert substituted.json()["receipt_id"] != valid.json()["receipt_id"]


def test_runtime_status_reports_local_sqlite_without_relaxing_blockers(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "operator.sqlite3"))

    health = client.get("/health").json()
    status = client.get("/api/v1/system/status").json()
    readiness = client.get("/api/v1/readiness").json()

    assert health["persistence"] == "sqlite"
    assert status["authorization_receipt_persistence"] == "sqlite_local"
    assert status["production_identity_access"] == "blocking"
    assert status["deployment_authorized"] is False
    assert readiness["production_ready"] is False
    assert readiness["authorization_receipt_persistence"]["state"] == "implemented_internal"
    assert readiness["external_action_performed"] is False
