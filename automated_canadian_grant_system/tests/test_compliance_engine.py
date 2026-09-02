from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from automated_canadian_grant_system.core.constitutional_guardrails import (
    ACGSGuardrailError,
    LiveIngestionBlocked,
)
from automated_canadian_grant_system.core.models import (
    GrantApplicationRequest,
)
from automated_canadian_grant_system.core.orchestrator import GrantOrchestrator
from automated_canadian_grant_system.core.vector_retrieval import (
    LocalGrantRetriever,
    RetrievalDocument,
    RetrievalPolicyError,
)
from automated_canadian_grant_system.frontend.app import create_app
from automated_canadian_grant_system.tests.test_grant_pipeline import (
    application_payload,
)


def test_live_portal_ingestion_is_blocked_before_network_use() -> None:
    with pytest.raises(LiveIngestionBlocked, match="No network request was made"):
        GrantOrchestrator().request_live_ingestion("alberta_innovates")


def test_unregistered_portal_fails_closed() -> None:
    payload = application_payload()
    grant = dict(payload["grant"])
    grant["portal_id"] = "unregistered_portal"
    payload["grant"] = grant

    with pytest.raises(ACGSGuardrailError, match="not registered"):
        GrantOrchestrator().generate(
            GrantApplicationRequest.model_validate(payload)
        )


def test_unreviewed_retrieval_material_is_not_indexed() -> None:
    retriever = LocalGrantRetriever()

    with pytest.raises(RetrievalPolicyError, match="rights review"):
        retriever.add(
            RetrievalDocument(
                document_id="historical_001",
                title="Unreviewed example",
                text="Grant application text",
                source_reference="operator-supplied",
                rights_reviewed=False,
            )
        )


def test_api_exposes_drafts_and_blocks_ingestion_and_submission() -> None:
    client = TestClient(create_app())

    root = client.get("/")
    assert root.status_code == 200
    assert "Grant application draft workspace" in root.text
    generated = client.post(
        "/api/generate_application",
        json=application_payload(),
    )
    assert generated.status_code == 200, generated.text
    generated_body = generated.json()
    assert generated_body["external_action_performed"] is False

    ingestion = client.post("/api/ingestion/alberta_innovates")
    assert ingestion.status_code == 409
    assert ingestion.json()["detail"]["external_action_performed"] is False

    submission = client.post(
        "/api/submit_application",
        json={"application_id": generated_body["application_id"]},
    )
    assert submission.status_code == 409
    assert (
        submission.json()["detail"]["status"]
        == "BLOCKED_PENDING_PHASE5_APPROVAL"
    )


def test_local_migration_preserves_append_only_audit_events() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = root / "database" / "migrations" / "0001_acgs_local_draft_schema.sql"
    connection = sqlite3.connect(":memory:")
    connection.executescript(migration.read_text(encoding="utf-8"))
    connection.execute(
        """
        INSERT INTO grant_applications (
            application_id, created_at, lifecycle_state, payload_json
        ) VALUES (?, ?, ?, ?)
        """,
        ("acgs_test", "2026-01-01T00:00:00Z", "AUDITED", "{}"),
    )
    connection.execute(
        """
        INSERT INTO grant_audit_events (
            event_id, application_id, created_at, event_type, payload_digest
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            "event_test",
            "acgs_test",
            "2026-01-01T00:00:00Z",
            "application.audited",
            "0" * 64,
        ),
    )

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        connection.execute(
            "UPDATE grant_audit_events SET event_type = 'changed' "
            "WHERE event_id = 'event_test'"
        )

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        connection.execute(
            """
            INSERT OR REPLACE INTO grant_audit_events (
                event_id, application_id, created_at, event_type, payload_digest
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "event_test",
                "acgs_test",
                "2026-01-01T00:00:00Z",
                "replaced",
                "1" * 64,
            ),
        )

    event_type = connection.execute(
        "SELECT event_type FROM grant_audit_events WHERE event_id = ?",
        ("event_test",),
    ).fetchone()[0]
    assert event_type == "application.audited"
