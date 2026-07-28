from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"aigc_test_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def diagnostics() -> ModuleType:
    return load_script("ci_diagnostics")


@pytest.fixture(scope="module")
def validator() -> ModuleType:
    return load_script("validate_secret_manifest")


@pytest.fixture(scope="module")
def canary() -> ModuleType:
    return load_script("run_controlled_gemini_canary_sandbox")


def test_diagnostics_redaction_and_allowlist(diagnostics: ModuleType) -> None:
    assert diagnostics.redact_text("ordinary", field_name="API_TOKEN") == "[REDACTED]"
    assert diagnostics.redact_text("ghp_abcdefghijklmnopqrstuvwxyz123456") == "[REDACTED]"
    metadata = diagnostics.safe_github_metadata(
        {"GITHUB_REPOSITORY": "Lornt1666/AIGC", "UNRELATED_SECRET": "do-not-read"}
    )
    assert metadata["github_repository"] == "Lornt1666/AIGC"
    assert "unrelated_secret" not in metadata


def test_diagnostics_timeout_is_bounded(diagnostics: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import subprocess

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(diagnostics.subprocess, "run", timeout)
    result = diagnostics.safe_command(("python", "-c", "pass"), cwd=tmp_path, timeout=1)
    assert result.timed_out and result.error == "command_timeout" and result.returncode is None


def manifest() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "secrets": [{
            "id": "gemini-api",
            "provider": "gcp_secret_manager",
            "purpose": "controlled Gemini assessment",
            "environment": "staging",
            "owner": "runtime-service",
            "reference": "projects/aigc-staging/secrets/gemini-api/versions/1",
            "authorized_consumers": ["serviceAccount:aigc-runtime@example.invalid"],
        }],
    }


def test_manifest_reference_only_is_valid(validator: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest()), encoding="utf-8")
    result = validator.validate(path, tmp_path)
    assert result["status"] == "valid" and result["findings"] == []


def test_manifest_rejects_nested_value_without_echoing_it(validator: ModuleType, tmp_path: Path) -> None:
    document = manifest()
    document["metadata"] = {"nested": {"client-secret": "never-echo-this"}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    result = validator.validate(path, tmp_path)
    assert "PROHIBITED_VALUE_FIELD" in {item["code"] for item in result["findings"]}
    assert "never-echo-this" not in json.dumps(result)


def test_canary_dry_run_makes_zero_calls(canary: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(canary, "git_sha", lambda _: "a" * 40)
    output = tmp_path / "receipt.json"
    code = canary.execute(
        root=tmp_path, output=output, execute_live=False, approval_path=None,
        model=None, idempotency_key=None, stop_file=tmp_path / "stop",
        idempotency_store=tmp_path / "idempotency",
        provider=lambda *args: pytest.fail("provider must not run"),
    )
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert receipt["outcome"] == "DRY_RUN_COMPLETE"
    assert receipt["network_calls"] == 0
    assert receipt["model_api_call_performed"] is False


def test_canary_emergency_stop_blocks_provider(canary: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(canary, "git_sha", lambda _: "b" * 40)
    stop = tmp_path / "stop"
    stop.write_text("active\n", encoding="utf-8")
    output = tmp_path / "receipt.json"
    code = canary.execute(
        root=tmp_path, output=output, execute_live=True, approval_path=None,
        model="gemini-2.5-flash", idempotency_key="one-time-key", stop_file=stop,
        idempotency_store=tmp_path / "idempotency",
        provider=lambda *args: pytest.fail("provider must not run"),
    )
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert code == 2 and receipt["outcome"] == "EMERGENCY_STOP_ACTIVE"
    assert receipt["network_calls"] == 0


def approval(canary: ModuleType, sha: str, model: str, key: str) -> dict[str, object]:
    return {
        "authorized": True,
        "action": "gemini_controlled_canary",
        "repository": "Lornt1666/AIGC",
        "git_sha": sha,
        "model": model,
        "prompt_sha256": canary.digest_text(canary.FIXED_PROMPT),
        "idempotency_key_sha256": canary.digest_text(key),
        "maximum_model_calls": 1,
        "maximum_input_tokens": 512,
        "maximum_output_tokens": 512,
        "maximum_total_tokens": 1024,
        "maximum_cost_cad": 1.00,
        "revoked": False,
        "approved_by": "github:236225491",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
    }


def test_canary_replay_is_fail_closed(canary: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sha, model, key = "c" * 40, "gemini-2.5-flash", "one-time-key"
    monkeypatch.setattr(canary, "git_sha", lambda _: sha)
    permit = tmp_path / "approval.json"
    permit.write_text(json.dumps(approval(canary, sha, model, key)), encoding="utf-8")
    store = tmp_path / "idempotency"

    def fake_provider(*args):
        return {"provider": "fake", "model_version": model, "response_id": "fake-response",
                "usage": {"total_tokens": 2}, "output": "safe synthetic result"}

    first = canary.execute(root=tmp_path, output=tmp_path / "first.json", execute_live=True,
        approval_path=permit, model=model, idempotency_key=key, stop_file=tmp_path / "stop",
        idempotency_store=store, provider=fake_provider)
    second = canary.execute(root=tmp_path, output=tmp_path / "second.json", execute_live=True,
        approval_path=permit, model=model, idempotency_key=key, stop_file=tmp_path / "stop",
        idempotency_store=store, provider=fake_provider)
    receipt = json.loads((tmp_path / "second.json").read_text(encoding="utf-8"))
    assert first == 0 and second == 2
    assert receipt["outcome"] == "IDEMPOTENCY_REPLAY_BLOCKED"
    assert receipt["network_calls"] == 0
