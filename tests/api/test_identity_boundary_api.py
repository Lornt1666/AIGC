from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.identity_boundary_app import create_identity_boundary_app


NOW = datetime(2026, 7, 13, 20, 0, tzinfo=timezone.utc)


def payload(
    *,
    assertion_id: str = "assertion-api",
    production_mode: bool = False,
    exact_revision: str = "LOCAL_UNVERIFIED",
) -> dict[str, object]:
    return {
        "provider_type": "LOCAL_DEVELOPMENT",
        "assertion": {
            "assertion_id": assertion_id,
            "principal_id": "principal-a",
            "issuer": "local-simulation",
            "audience": "aigc-local-operator",
        },
        "membership_id": "membership-a",
        "session_id": "session-a",
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "exact_revision": exact_revision,
        "production_mode": production_mode,
    }


def test_internal_preflight_api_returns_redacted_local_context(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_identity_boundary_app(
            database_path=tmp_path / "operator.sqlite3",
            evaluation_time=NOW,
        )
    )

    response = client.post(
        "/api/v1/identity/context/verify",
        json=payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["permitted"] is True
    assert body["context"]["roles"] == ["operator"]
    assert body["context"]["runtime_authority"] == "LOCAL_SIMULATION"
    assert body["receipt"]["external_action_performed"] is False
    serialized = response.text
    assert "access_token" not in serialized
    assert "provider_claims" not in serialized


def test_internal_preflight_api_denies_local_identity_in_production(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_identity_boundary_app(
            database_path=tmp_path / "operator.sqlite3",
            evaluation_time=NOW,
        )
    )

    response = client.post(
        "/api/v1/identity/context/verify",
        json=payload(
            assertion_id="assertion-production-api",
            production_mode=True,
            exact_revision="a" * 40,
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["permitted"] is False
    assert "LOCAL_PROVIDER_PROHIBITED" in body["reason_codes"]
    assert body["context"] is None


def test_identity_receipt_survives_api_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "operator.sqlite3"
    first_client = TestClient(
        create_identity_boundary_app(
            database_path=database_path,
            evaluation_time=NOW,
        )
    )
    first = first_client.post(
        "/api/v1/identity/context/verify",
        json=payload(assertion_id="assertion-restart-api"),
    )
    receipt_id = first.json()["receipt"]["receipt_id"]

    restarted = TestClient(
        create_identity_boundary_app(
            database_path=database_path,
            evaluation_time=NOW,
        )
    )
    receipt = restarted.get(
        f"/api/v1/identity/receipts/{receipt_id}"
    )

    assert receipt.status_code == 200
    assert receipt.json() == first.json()["receipt"]
