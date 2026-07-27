from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from src.gemini_workflow.api import set_service_override
from src.gemini_workflow.evidence import JsonlEvidenceStore
from src.gemini_workflow.models import GeminiAssessment
from src.gemini_workflow.provider import StubGeminiProvider
from src.gemini_workflow.service import GeminiWorkflowService
from src.webapp.app import BUSINESS_CYCLE, app


def test_cloud_app_exposes_expected_routes() -> None:
    paths = set(app.openapi()["paths"])

    assert "/" in paths
    assert "/health" in paths
    assert "/api/run" in paths
    assert "/api/reviews" in paths
    assert "/api/emergency-stop" in paths
    assert "/api/gemini/status" in paths
    assert "/api/gemini/workflows" in paths
    assert "/api/gemini/workflows/{run_id}" in paths
    assert "/api/gemini/workflows/{run_id}/decision" in paths


def test_business_cycle_contains_phase24_and_validation() -> None:
    names = [name for name, _command in BUSINESS_CYCLE]

    assert names[0] == "runtime_preflight"
    assert "autonomic_business_pipeline" in names
    assert names[-1] == "contract_validation"


def test_business_cycle_commands_are_project_scoped() -> None:
    for _name, command in BUSINESS_CYCLE:
        joined = " ".join(command)
        assert "src" in joined
        assert "aigc.py" in joined


def test_command_center_fails_closed_without_auth_token(monkeypatch) -> None:
    monkeypatch.delenv("AIGC_COMMAND_CENTER_TOKEN", raising=False)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert "project_root" not in health.json()
    assert health.json()["auth_configured"] is False
    assert client.get("/").status_code == 503
    assert client.get("/api/reviews").status_code == 503
    assert client.post("/api/run").status_code == 503
    assert client.get("/api/gemini/status").status_code == 503


def test_command_center_rejects_missing_or_wrong_operator_token(monkeypatch) -> None:
    monkeypatch.setenv("AIGC_COMMAND_CENTER_TOKEN", "correct-token")
    client = TestClient(app)

    assert client.get("/api/pipeline").status_code == 401
    assert client.get("/api/pipeline", headers={"Authorization": "Bearer wrong-token"}).status_code == 401


def test_command_center_accepts_bearer_header_and_basic_auth(monkeypatch) -> None:
    monkeypatch.setenv("AIGC_COMMAND_CENTER_TOKEN", "correct-token")
    client = TestClient(app)

    bearer = client.get("/api/pipeline", headers={"Authorization": "Bearer correct-token"})
    assert bearer.status_code == 200

    basic_value = base64.b64encode(b"operator:correct-token").decode("ascii")
    root = client.get("/", headers={"Authorization": f"Basic {basic_value}"})
    assert root.status_code == 200
    assert "AIGC Governed Worker Command Center" in root.text


def test_command_center_rejects_cross_origin_mutation(monkeypatch) -> None:
    monkeypatch.setenv("AIGC_COMMAND_CENTER_TOKEN", "correct-token")
    client = TestClient(app)
    response = client.post(
        "/api/run",
        headers={
            "Authorization": "Bearer correct-token",
            "Origin": "https://malicious.example",
        },
    )
    assert response.status_code == 403


def test_gemini_http_workflow_runs_end_to_end_with_offline_provider(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AIGC_COMMAND_CENTER_TOKEN", "correct-token")
    assessment = GeminiAssessment(
        fit_score=88,
        recommendation="pursue",
        rationale=["Strong supplied fit.", "The scope is reviewable."],
        evidence_basis=[
            {
                "input_pointer": "/description",
                "observation": "The supplied description defines the task.",
                "impact": "positive",
            }
        ],
        assumptions=[],
        risks=[],
        clarifying_questions=[],
        proposed_scope=["Prepare an internal work package."],
        ai_use_disclosure=(
            "AI assisted with the assessment; a human reviews it before use."
        ),
        human_review_required=True,
    )
    service = GeminiWorkflowService(
        provider=StubGeminiProvider(assessment),
        evidence_store=JsonlEvidenceStore(tmp_path / "events.jsonl"),
    )
    set_service_override(service)
    client = TestClient(app)
    headers = {"Authorization": "Bearer correct-token"}
    try:
        created = client.post(
            "/api/gemini/workflows",
            headers=headers,
            json={
                "title": "Permissioned opportunity",
                "description": (
                    "A detailed opportunity supplied for an authenticated "
                    "offline full-stack test."
                ),
                "source_url": "https://example.com/opportunity",
                "constraints": ["No external business action"],
                "ai_assistance_permitted": True,
                "ai_disclosure_required": True,
            },
        )
        assert created.status_code == 200
        execution = created.json()
        assert execution["status"] == "pending_human_review"
        assert execution["model_api_call_performed"] is False
        assert execution["external_business_action_performed"] is False

        decision = client.post(
            f"/api/gemini/workflows/{execution['run_id']}/decision",
            headers=headers,
            json={
                "decision": "approve",
                "reason": "The internal assessment passed human review.",
                "revision_instructions": "",
            },
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "human_approve"

        retrieved = client.get(
            f"/api/gemini/workflows/{execution['run_id']}",
            headers=headers,
        )
        assert retrieved.status_code == 200
        assert len(retrieved.json()["events"]) == 2
    finally:
        set_service_override(None)


def test_deployment_defaults_require_private_auth_boundary() -> None:
    deploy_script = Path("scripts/deploy_cloud_run.ps1").read_text(encoding="utf-8")
    render_config = Path("render.yaml").read_text(encoding="utf-8")
    webapp_source = Path("src/webapp/app.py").read_text(encoding="utf-8")
    local_launcher = Path("scripts/run_cloud_command_center.ps1").read_text(encoding="utf-8")
    batch_launcher = Path("RUN_AIGC_WEBAPP.bat").read_text(encoding="utf-8")
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")

    assert "--allow-unauthenticated" not in deploy_script
    assert "--no-allow-unauthenticated" in deploy_script
    assert "--set-secrets" in deploy_script
    assert "AIGC_COMMAND_CENTER_TOKEN" in deploy_script
    assert "AIGC_GEMINI_ENABLED=true" in deploy_script
    assert "AIGC_GEMINI_EVIDENCE_BACKEND=gcs" in deploy_script
    assert "--service-account" in deploy_script
    assert "docker.pkg.dev" in deploy_script
    assert "gcr.io" not in deploy_script
    assert "--max-instances 3" in deploy_script
    assert ":latest" not in deploy_script
    assert "AIGC_COMMAND_CENTER_TOKEN" in render_config
    assert "sync: false" in render_config
    assert '"127.0.0.1"' in webapp_source
    assert '"127.0.0.1"' in local_launcher
    assert "127.0.0.1" in batch_launcher
    assert "root.innerHTML" not in webapp_source
    assert "div.innerHTML" not in webapp_source
    assert "USER aigc" in dockerfile
    assert "*service-account*.json" in dockerignore
