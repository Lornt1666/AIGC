from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from src.webapp.gemini_app import create_app


GEMINI_PACKAGE_FILES = {
    "src/gemini_workflow/__init__.py",
    "src/gemini_workflow/api.py",
    "src/gemini_workflow/auth.py",
    "src/gemini_workflow/control_store.py",
    "src/gemini_workflow/evidence.py",
    "src/gemini_workflow/judge_receipts.py",
    "src/gemini_workflow/judge_store.py",
    "src/gemini_workflow/models.py",
    "src/gemini_workflow/policy.py",
    "src/gemini_workflow/provider.py",
    "src/gemini_workflow/readiness.py",
    "src/gemini_workflow/redaction.py",
    "src/gemini_workflow/runtime_limits.py",
    "src/gemini_workflow/secret_broker.py",
    "src/gemini_workflow/service.py",
    "src/gemini_workflow/settings.py",
    "src/webapp/gemini_app.py",
    "src/webapp/gemini_ui.py",
}
IMAGE_FILES = {
    "requirements-gemini.txt",
    "config/gemini_runtime_limits.json",
    "config/gemini_secret_access_manifest.json",
    *GEMINI_PACKAGE_FILES,
}
BUILD_CONTEXT_FILES = {
    ".gcloudignore.gemini",
    "Dockerfile.gemini",
    "cloudbuild.gemini.yaml",
    *IMAGE_FILES,
}


def _docker_copy_sources(value: str) -> set[str]:
    sources: set[str] = set()
    for line in value.splitlines():
        stripped = line.strip()
        if not stripped.startswith("COPY "):
            continue
        tokens = stripped.split()
        positional = [token for token in tokens[1:] if not token.startswith("--")]
        assert len(positional) == 2
        sources.add(positional[0])
    return sources


def test_dockerfile_has_an_exact_non_root_copy_allowlist() -> None:
    dockerfile = Path("Dockerfile.gemini").read_text(encoding="utf-8")

    assert re.search(r"(?m)^USER aigc$", dockerfile)
    assert "COPY ." not in dockerfile
    assert "COPY --chown=aigc:aigc . " not in dockerfile
    assert "src/core" not in dockerfile
    assert _docker_copy_sources(dockerfile) == IMAGE_FILES
    assert all(Path(path).is_file() for path in IMAGE_FILES)
    assert "src.webapp.gemini_app:app" in dockerfile
    assert "--limit-concurrency 8" in dockerfile
    assert "--timeout-keep-alive 5" in dockerfile


def test_gcloud_context_is_default_deny_and_exactly_allowlisted() -> None:
    ignore = Path(".gcloudignore.gemini").read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in ignore.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    allowed_files = {
        line[1:]
        for line in lines
        if line.startswith("!") and not line.endswith("/")
    }

    assert lines[0] == "**"
    assert allowed_files == BUILD_CONTEXT_FILES
    assert "!src/" in lines
    assert "src/**" in lines
    assert "!src/gemini_workflow/" in lines
    assert "src/gemini_workflow/**" in lines
    assert "!src/webapp/" in lines
    assert "src/webapp/**" in lines
    assert "!config/" in lines
    assert "config/**" in lines


def test_cloud_build_uses_only_the_gemini_dockerfile_and_never_deploys() -> None:
    config = Path("cloudbuild.gemini.yaml").read_text(encoding="utf-8")

    assert "--ignore-file .gcloudignore.gemini" in config
    assert "verify-gemini-build-context" in config
    assert "Dockerfile.gemini" in config
    assert "Dockerfile\n" not in config
    assert "gcloud run deploy" not in config
    assert "terraform apply" not in config
    assert "_IMAGE_URI: invalid.invalid/" in config
    for path in BUILD_CONTEXT_FILES:
        assert path in config


def test_gemini_requirements_are_pinned_to_the_production_import_closure() -> None:
    requirements = Path("requirements-gemini.txt").read_text(encoding="utf-8")
    normalized = requirements.lower()

    for forbidden in (
        "streamlit",
        "pyjwt",
        "jsonschema",
    ):
        assert forbidden not in normalized
    assert "google-genai==" in requirements
    assert "google-cloud-storage==" in requirements
    assert "google-cloud-secret-manager==" in requirements
    assert "psycopg[binary]==" in requirements
    assert "psycopg-pool==" in requirements
    assert all(
        "==" in line
        for line in requirements.splitlines()
        if line.strip() and not line.startswith("#")
    )


def test_runtime_limits_match_the_container_and_fail_closed() -> None:
    limits = json.loads(
        Path("config/gemini_runtime_limits.json").read_text(encoding="utf-8")
    )

    assert limits["surface"] == "aigc-gemini-only"
    assert limits["server"] == {
        "workers": 1,
        "concurrency_limit": 8,
        "keep_alive_seconds": 5,
    }
    assert limits["security"] == {
        "legacy_routes_allowed": False,
        "generative_readiness_probe_allowed": False,
        "external_business_action_allowed": False,
        "provider_transport_attempts": 1,
    }


def test_isolated_app_exposes_no_legacy_command_center_routes() -> None:
    paths = set(create_app("operator").openapi()["paths"])

    assert paths == {
        "/",
        "/healthz",
        "/readyz",
        "/api/gemini/status",
        "/api/gemini/runtime/emergency-stop",
        "/api/gemini/runtime/emergency-stop/clear",
        "/api/gemini/workflows",
        "/api/gemini/workflows/{run_id}",
        "/api/gemini/workflows/{run_id}/decision",
    }


def test_explicit_package_allowlist_has_a_complete_import_closure(
    tmp_path: Path,
) -> None:
    for source_name in GEMINI_PACKAGE_FILES:
        source = Path(source_name)
        destination = tmp_path / source_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import src.webapp.gemini_app",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
