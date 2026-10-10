from __future__ import annotations

import ast
from pathlib import Path
import subprocess

import pytest

from scripts.deploy_gemini_staging import StagingDeploymentError, _run


def test_staging_deployer_defaults_to_plan_only() -> None:
    source = Path("scripts/deploy_gemini_staging.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)

    assert "--execute" in source
    assert 'action="store_true"' in source
    assert "validate_authorization(payload, gate=\"deploy\")" in source
    assert "--no-traffic" in source
    assert "--no-allow-unauthenticated" in source
    assert "image_summary.digest" in source
    assert "_DIGEST.fullmatch" in source
    assert "AIGC_SURFACE" in source
    assert "AIGC_GEMINI_CONTROL_DSN_SECRET_REF" in source
    assert "--set-secrets" not in source
    assert "gcloud run services update-traffic" not in source
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "deploy"
        for node in ast.walk(tree)
    )


def test_staging_deployer_never_creates_foundational_resources() -> None:
    source = Path("scripts/deploy_gemini_staging.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "projects create",
        "artifacts repositories create",
        "sql instances create",
        "storage buckets create",
        "iam service-accounts create",
        "secrets create",
        "billing budgets create",
    )
    for command in forbidden:
        assert command not in source


def test_staging_deployer_timeout_is_unknown_outcome_and_not_retried(monkeypatch) -> None:
    calls = []

    def timeout(command, **kwargs):
        calls.append((command, kwargs))
        raise subprocess.TimeoutExpired(command, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(StagingDeploymentError, match="remote state may have changed"):
        _run(["gcloud", "run", "deploy", "service"], timeout_seconds=7)

    assert len(calls) == 1
    assert calls[0][1]["timeout"] == 7
