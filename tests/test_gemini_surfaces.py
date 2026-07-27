from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.gemini_workflow.api import set_service_override
from src.gemini_workflow.auth import (
    authenticate_shared_credential,
    stable_shared_principal_id,
)
from src.gemini_workflow.evidence import JsonlEvidenceStore
from src.gemini_workflow.models import GeminiAssessment
from src.gemini_workflow.provider import StubGeminiProvider
from src.gemini_workflow.service import GeminiWorkflowService
from src.webapp.gemini_app import _role_credentials, create_app


def _assessment() -> GeminiAssessment:
    return GeminiAssessment(
        fit_score=82,
        recommendation="pursue",
        rationale=["The supplied scope is bounded.", "Human review is explicit."],
        evidence_basis=[
            {
                "input_pointer": "/description",
                "observation": "The description identifies a reviewable task.",
                "impact": "positive",
            }
        ],
        assumptions=[],
        risks=[],
        clarifying_questions=[],
        proposed_scope=["Prepare one internal assessment."],
        ai_use_disclosure="AI assisted; an accountable human reviews the result.",
        human_review_required=True,
    )


def _configure_roles(monkeypatch) -> None:
    monkeypatch.setenv("AIGC_ENV", "development")
    monkeypatch.setenv(
        "AIGC_OPERATOR_TOKEN",
        "operator-value-for-tests-1234567890",
    )
    monkeypatch.setenv(
        "AIGC_OPERATOR_BINDING_KEY",
        "operator-binding-value-for-tests-123456",
    )
    monkeypatch.setenv(
        "AIGC_RUNTIME_ADMIN_TOKEN",
        "runtime-admin-value-for-tests-123456",
    )
    monkeypatch.setenv(
        "AIGC_RUNTIME_ADMIN_BINDING_KEY",
        "runtime-admin-binding-for-tests-123456",
    )
    monkeypatch.setenv(
        "AIGC_JUDGE_TOKEN",
        "judge-value-for-tests-12345678901234",
    )
    monkeypatch.setenv(
        "AIGC_JUDGE_BINDING_KEY",
        "judge-binding-value-for-tests-123456789",
    )
    _role_credentials.cache_clear()


def test_shared_principal_is_stable_when_attested_label_changes() -> None:
    key = "stable-binding-key-for-tests-123456"
    first = authenticate_shared_credential(
        provided_token="operator-value-for-tests-1234567890",
        expected_token="operator-value-for-tests-1234567890",
        credential_binding_key=key,
        role="operator",
        attested_label="First Label",
    )
    second = authenticate_shared_credential(
        provided_token="operator-value-for-tests-1234567890",
        expected_token="operator-value-for-tests-1234567890",
        credential_binding_key=key,
        role="operator",
        attested_label="Changed Label",
    )

    assert first.principal_id == second.principal_id
    assert first.subject_sha256 != second.subject_sha256
    assert first.principal_id == stable_shared_principal_id(
        key,
        role="operator",
    )


def test_operator_surface_excludes_legacy_and_judge_routes(monkeypatch) -> None:
    _configure_roles(monkeypatch)
    application = create_app(
        "operator",
        readiness_check=lambda: {
            "ready": True,
            "model_api_call_performed": False,
        },
    )
    paths = set(application.openapi()["paths"])

    assert "/api/gemini/workflows" in paths
    assert "/api/gemini/runtime/emergency-stop" in paths
    assert "/api/gemini/runtime/emergency-stop/clear" in paths
    assert "/api/run" not in paths
    assert "/api/pipeline" not in paths
    assert "/api/reviews" not in paths
    assert not any(path.startswith("/api/judge/") for path in paths)


def test_judge_surface_is_read_only_and_provider_free(monkeypatch) -> None:
    _configure_roles(monkeypatch)
    application = create_app(
        "judge",
        readiness_check=lambda: {
            "ready": True,
            "model_api_call_performed": False,
        },
    )
    paths = set(application.openapi()["paths"])

    assert "/api/judge/receipts/{receipt_id}" in paths
    assert not any(path.startswith("/api/gemini/") for path in paths)
    assert "/api/run" not in paths
    assert application.state.provider_initialized is False
    assert application.state.control_writer_initialized is False


def test_emergency_stop_blocks_new_model_calls_and_admin_clear_restores(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _configure_roles(monkeypatch)
    service = GeminiWorkflowService(
        provider=StubGeminiProvider(_assessment()),
        evidence_store=JsonlEvidenceStore(tmp_path / "events.jsonl"),
    )
    set_service_override(service)
    client = TestClient(
        create_app(
            "operator",
            readiness_check=lambda: {
                "ready": True,
                "model_api_call_performed": False,
            },
        )
    )
    operator_headers = {
        "X-AIGC-Operator-Token": "operator-value-for-tests-1234567890",
        "X-AIGC-Operator-Label": "Operator One",
    }
    try:
        stopped = client.post(
            "/api/gemini/runtime/emergency-stop",
            headers=operator_headers,
            json={"reason": "Controlled test of the durable stop boundary."},
        )
        assert stopped.status_code == 200
        epoch = stopped.json()["stop_epoch"]

        blocked = client.post(
            "/api/gemini/workflows",
            headers={
                **operator_headers,
                "Idempotency-Key": "blocked-workflow-key-0001",
            },
            json={
                "title": "Blocked assessment",
                "description": "A detailed synthetic intake for the stop test.",
                "source_url": "https://example.com/opportunity",
                "constraints": [],
                "ai_assistance_permitted": True,
                "ai_disclosure_required": True,
            },
        )
        assert blocked.status_code == 503

        cleared = client.post(
            "/api/gemini/runtime/emergency-stop/clear",
            headers={
                "X-AIGC-Runtime-Admin-Token": (
                    "runtime-admin-value-for-tests-123456"
                )
            },
            json={
                "reason": "Controlled test clear after verifying the stop.",
                "expected_epoch": epoch,
                "exact_phrase": f"CLEAR GEMINI STOP EPOCH {epoch}",
            },
        )
        assert cleared.status_code == 200
        assert cleared.json()["active"] is False
    finally:
        set_service_override(None)
        _role_credentials.cache_clear()
