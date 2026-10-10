from __future__ import annotations

import base64
import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from src.webapp.app import BUSINESS_CYCLE, app


def test_cloud_app_exposes_expected_routes() -> None:
    paths = {route.path for route in app.routes}

    assert "/" in paths
    assert "/health" in paths
    assert "/api/run" in paths
    assert "/api/reviews" in paths
    assert "/api/emergency-stop" in paths


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


def test_deployment_defaults_require_private_auth_boundary() -> None:
    deploy_script = Path("scripts/deploy_cloud_run.ps1").read_text(encoding="utf-8")
    render_config = Path("render.yaml").read_text(encoding="utf-8")
    webapp_source = Path("src/webapp/app.py").read_text(encoding="utf-8")
    local_launcher = Path("scripts/run_cloud_command_center.ps1").read_text(encoding="utf-8")
    batch_launcher = Path("RUN_AIGC_WEBAPP.bat").read_text(encoding="utf-8")
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "--allow-unauthenticated" not in deploy_script
    assert "--no-allow-unauthenticated" in deploy_script
    assert "--set-secrets" in deploy_script
    assert "AIGC_COMMAND_CENTER_TOKEN" in deploy_script
    assert "AIGC_COMMAND_CENTER_TOKEN" in render_config
    assert "sync: false" in render_config
    assert '"127.0.0.1"' in webapp_source
    assert '"127.0.0.1"' in local_launcher
    assert "127.0.0.1" in batch_launcher
    assert "USER aigc" in dockerfile


def test_output_redaction_and_bounds() -> None:
    from src.webapp.app import _safe_output

    result = _safe_output('api_key=abc123 Authorization: Bearer xyz789 {"client_secret": "json-secret"} ' + "x" * 3000)
    assert "abc123" not in result
    assert "xyz789" not in result
    assert "json-secret" not in result
    assert len(result) <= 2000


def test_review_mutations_reject_stale_or_non_pending_packets() -> None:
    from types import SimpleNamespace
    import pytest
    from fastapi import HTTPException
    from src.webapp.app import _require_pending_review

    with pytest.raises(HTTPException) as expired:
        _require_pending_review(SimpleNamespace(expired=True, external_action_performed=False, decision="pending"))
    assert expired.value.status_code == 409

    with pytest.raises(HTTPException) as completed:
        _require_pending_review(SimpleNamespace(expired=False, external_action_performed=True, decision="pending"))
    assert completed.value.status_code == 409

    with pytest.raises(HTTPException) as decided:
        _require_pending_review(SimpleNamespace(expired=False, external_action_performed=False, decision="accepted"))
    assert decided.value.status_code == 409


def test_run_capacity_is_bounded() -> None:
    from src.webapp.app import MAX_CONCURRENT_RUNS, RUN_CAPACITY

    assert MAX_CONCURRENT_RUNS >= 1
    acquired = 0
    try:
        for _ in range(MAX_CONCURRENT_RUNS):
            assert RUN_CAPACITY.acquire(blocking=False)
            acquired += 1
        assert RUN_CAPACITY.acquire(blocking=False) is False
    finally:
        for _ in range(acquired):
            RUN_CAPACITY.release()


def test_governed_command_timeout_is_reported(monkeypatch, tmp_path) -> None:
    import subprocess
    from src.core import operator_cockpit

    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=kwargs.get("timeout", 1), output="partial", stderr="stalled")

    monkeypatch.setattr(operator_cockpit.subprocess, "run", timed_out)
    result = operator_cockpit.run_command(["example"], root=tmp_path, label="test-timeout", timeout_seconds=2)
    assert result.returncode == 124
    assert "Timed out after 2 seconds." in result.stderr


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        ("accept", {}),
        ("deny", {}),
        ("revise", {"revision_instructions": "Please clarify assumptions."}),
    ],
)
@pytest.mark.parametrize(
    ("review_state", "expected_detail"),
    [
        ({"expired": True, "external_action_performed": False, "decision": "pending"}, "expired"),
        ({"expired": False, "external_action_performed": True, "decision": "pending"}, "outward completion"),
        ({"expired": False, "external_action_performed": False, "decision": "accepted"}, "not pending"),
    ],
)
def test_all_review_routes_reject_stale_or_decided_packets_before_command(
    monkeypatch, route, payload, review_state, expected_detail
) -> None:
    from types import SimpleNamespace
    import src.webapp.app as webapp

    monkeypatch.setenv("AIGC_COMMAND_CENTER_TOKEN", "test-operator-token")
    monkeypatch.setattr(webapp, "_find_review", lambda _action_id: SimpleNamespace(action_id="test-action", **review_state))

    def unexpected_command(*args, **kwargs):
        raise AssertionError("A stale or decided review must be rejected before command execution.")

    monkeypatch.setattr(webapp, "run_command", unexpected_command)
    client = TestClient(app)
    response = client.post(
        f"/api/reviews/test-action/{route}",
        json=payload,
        headers={"Authorization": "Bearer test-operator-token"},
    )

    assert response.status_code == 409
    assert expected_detail in response.json()["detail"]


@pytest.mark.parametrize(
    ("aigc_env", "environment", "expected"),
    [
        ("development", "production", True),
        ("prod", "development", True),
        ("development", "development", False),
        (None, "prod", True),
        (None, None, False),
    ],
)
def test_fastapi_production_detection_fails_closed_on_conflicting_environment(
    monkeypatch, aigc_env, environment, expected
) -> None:
    from src.webapp.app import _production_mode

    if aigc_env is None:
        monkeypatch.delenv("AIGC_ENV", raising=False)
    else:
        monkeypatch.setenv("AIGC_ENV", aigc_env)
    if environment is None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("ENVIRONMENT", environment)

    assert _production_mode() is expected


def test_store_factory_does_not_allow_development_override_of_production(monkeypatch) -> None:
    from src.webapp.command_center_store import (
        CommandCenterStoreUnavailable,
        command_center_store_from_env,
    )

    monkeypatch.setenv("AIGC_ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AIGC_COMMAND_CENTER_DATABASE_URL", raising=False)

    with pytest.raises(CommandCenterStoreUnavailable, match="required in production"):
        command_center_store_from_env()
