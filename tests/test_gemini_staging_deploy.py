from __future__ import annotations

import ast
from pathlib import Path


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
