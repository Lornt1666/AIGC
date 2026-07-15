from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.readiness import build_readiness_payload


ROOT = Path(__file__).resolve().parents[2]


def test_readiness_endpoint_matches_canonical_ledger(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "operator.sqlite3"))

    response = client.get("/api/v1/readiness")

    assert response.status_code == 200, response.text
    payload = response.json()
    expected = build_readiness_payload(ROOT)

    assert payload["current"]["structural_score"] == expected["current"][
        "structural_score"
    ]
    assert payload["current"]["production_ready"] == expected["current"][
        "production_ready"
    ]
    assert payload["current"]["blocking_gaps"] == expected["current"][
        "blocking_gaps"
    ]
    assert payload["current"]["evidence_strength"] == (
        "structural_not_operational_proof"
    )


def test_readiness_top_level_aliases_remain_backward_compatible(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "operator.sqlite3"))

    payload = client.get("/api/v1/readiness").json()

    assert payload["production_ready"] == payload["current"]["production_ready"]
    assert payload["structural_score"] == payload["current"]["structural_score"]
    assert payload["blocking_gaps"] == payload["current"]["blocking_gaps"]
    assert payload["evidence_strength"] == payload["current"]["evidence_strength"]
    assert payload["production_identity_access"]["blocking"] is True
    assert payload["authorization_receipt_persistence"] == {
        "state": "implemented_internal",
        "blocking": False,
    }


def test_readiness_projection_never_grants_current_authority(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "operator.sqlite3"))

    payload = client.get("/api/v1/readiness").json()

    assert payload["projection"]["structural_score"] == 90.5
    assert payload["projection"][
        "production_ready_if_evidence_is_accepted"
    ] is True
    assert payload["projection"]["grants_authority"] is False
    assert payload["current"]["structural_score"] != payload["projection"][
        "structural_score"
    ]


def test_delivery_judgment_gate_reports_implemented_internal(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "operator.sqlite3"))

    gate = client.get("/api/v1/readiness").json()[
        "delivery_judgment_gate"
    ]

    assert gate == {
        "state": "implemented_internal",
        "review_packet_generation": True,
        "accountable_human_judgment": True,
        "accepted_for_delivery_supported": True,
        "delivery_performed": False,
        "blocking": False,
        "external_action_performed": False,
    }
