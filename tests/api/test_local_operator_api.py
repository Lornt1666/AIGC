from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def example() -> dict:
    response = client.get("/api/v1/identity/example")
    assert response.status_code == 200
    return response.json()


def refresh_digest(bundle: dict) -> None:
    from src.core.identity.principal_authority_binding import PrincipalAuthorityBindingKernel
    bundle["request"]["request_digest"] = PrincipalAuthorityBindingKernel.request_digest(bundle["request"])


def test_health_and_status_are_local_only() -> None:
    assert client.get("/health").json()["external_action_performed"] is False
    status = client.get("/api/v1/system/status").json()
    assert status["production_identity_access"] == "blocking"
    assert status["deployment_authorized"] is False


def test_readiness_remains_blocking() -> None:
    body = client.get("/api/v1/readiness").json()
    assert body["production_ready"] is False
    assert body["production_identity_access"]["blocking"] is True


def test_valid_synthetic_authorization_and_receipt_lookup() -> None:
    response = client.post("/api/v1/identity/authorize", json=example())
    assert response.status_code == 200
    body = response.json()
    assert body["result"] in {"PERMIT", "REVIEW_REQUIRED"}
    receipt = client.get(f"/api/v1/audit/receipts/{body['receipt_id']}")
    assert receipt.status_code == 200
    assert receipt.json()["external_action_performed"] is False


def test_tenant_substitution_denies() -> None:
    bundle = deepcopy(example())
    bundle["request"]["tenant_id"] = "tenant-b"
    bundle["request"]["resource"]["tenant_id"] = "tenant-b"
    refresh_digest(bundle)
    body = client.post("/api/v1/identity/authorize", json=bundle).json()
    assert body["result"] == "DENY"
    assert "TENANT_MEMBERSHIP_MISSING" in body["reason_codes"]


def test_session_principal_substitution_denies() -> None:
    bundle = deepcopy(example())
    bundle["sessions"][0]["principal_id"] = "principal-b"
    body = client.post("/api/v1/identity/authorize", json=bundle).json()
    assert body["result"] == "DENY"
    assert "SESSION_PRINCIPAL_MISMATCH" in body["reason_codes"]


def test_policy_subject_substitution_denies() -> None:
    bundle = deepcopy(example())
    bundle["policies"][0]["subject_selectors"] = {
        "principal_ids": ["principal-b"],
        "role_ids": [],
    }
    body = client.post("/api/v1/identity/authorize", json=bundle).json()
    assert body["result"] == "DENY"
    assert "POLICY_SUBJECT_MISMATCH" in body["reason_codes"]


def test_unknown_fields_fail_contract_boundary() -> None:
    bundle = example()
    bundle["unexpected"] = True
    response = client.post("/api/v1/identity/authorize", json=bundle)
    assert response.status_code == 422
