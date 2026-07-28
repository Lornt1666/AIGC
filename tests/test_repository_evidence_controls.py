from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def diagnostics() -> ModuleType:
    return load_script("ci_diagnostics")


@pytest.fixture(scope="module")
def manifest_validator() -> ModuleType:
    return load_script("validate_secret_manifest")


@pytest.fixture(scope="module")
def canary() -> ModuleType:
    return load_script("run_controlled_gemini_canary_sandbox")


def test_diagnostics_redacts_secret_names_and_values(diagnostics: ModuleType) -> None:
    assert diagnostics.redact_text("ordinary", field_name="API_TOKEN") == "[REDACTED]"
    assert diagnostics.redact_text("ghp_abcdefghijklmnopqrstuvwxyz123456") == "[REDACTED]"
    assert diagnostics.redact_text("https://user:pass@example.com/repo.git") == "[REDACTED]"


def test_diagnostics_safe_metadata_is_allowlisted(diagnostics: ModuleType) -> None:
    result = diagnostics.safe_github_metadata(
        {"GITHUB_REPOSITORY": "Lornt1666/AIGC", "UNRELATED_SECRET": "do-not-read"}
    )
    assert result["github_repository"] == "Lornt1666/AIGC"
    assert "unrelated_secret" not in result


def test_diagnostics_timeout_is_bounded(diagnostics: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import subprocess

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(diagnostics.subprocess, "run", timeout)
    result = diagnostics.safe_command(("python", "-c", "pass"), cwd=tmp_path, timeout=1)
    assert result.timed_out is True
    assert result.error == "command_timeout"
    assert result.returncode is None


def valid_manifest() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "secrets": [
            {
                "id": "gemini-api",
                "provider": "gcp_secret_manager",
                "purpose": "controlled Gemini assessment",
                "environment": "staging",
                "owner": "runtime-service",
                "reference": "projects/aigc-staging/secrets/gemini-api/versions/1",
                "authorized_consumers": ["serviceAccount:aigc-runtime@example.invalid"],
            }
        ],
    }


def test_manifest_validator_accepts_reference_only_document(manifest_validator: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(valid_manifest()), encoding="utf-8")
    result = manifest_validator.validate(path, tmp_path)
    assert result["status"] == "valid"
    assert result["entry_count"] == 1
    assert result["findings"] == []


def test_manifest_validator_rejects_nested_plaintext_field(manifest_validator: ModuleType, tmp_path: Path) -> None:
    document = valid_manifest()
    document["metadata"] = {"nested": {"client-secret": "suppressed"}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    result = manifest_validator.validate(path, tmp_path)
    codes = {finding["code"] for finding in result["findings"]}
    assert result["status"] == "invalid"
    assert "PROHIBITED_VALUE_FIELD" in codes
    assert "suppressed" not in json.dumps(result)


def test_manifest_validator_rejects_unversioned_gcp_reference(manifest_validator: ModuleType, tmp_path: Path) -> None:
    document = valid_manifest()
    document["secrets"][0]["reference"] = "projects/aigc-staging/secrets/gemini-api"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    result = manifest_validator.validate(path, tmp_path)
    assert "INVALID_REFERENCE" in {finding["code"] for finding in result["findings"]}


def approval_for(canary: ModuleType, *, sha: str, model: str, key: str) -> dict[str, object]:
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


def test_canary_dry_run_makes_no_provider_call(canary: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(canary, "git_sha", lambda _: "a" * 40)
    calls = 0

    def provider(*args):
        nonlocal calls
        calls += 1
        raise AssertionError("dry run must not invoke provider")

    output = tmp_path / "receipt.json"
    code = canary.execute(
        root=tmp_path,
        output=output,
        execute_live=False,
        approval_path=None,
        model=None,
        idempotency_key=None,
        stop_file=tmp_path / "stop",
        idempotency_store=tmp_path / "idempotency",
        provider=provider,
    )
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert calls == 0
    assert receipt["outcome"] == "DRY_RUN_COMPLETE"
    assert receipt["network_calls"] == 0
    assert receipt["model_api_call_performed"] is False


def test_canary_emergency_stop_blocks_before_provider(canary: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(canary, "git_sha", lambda _: "b" * 40)
    stop = tmp_path / "stop"
    stop.write_text("active\n", encoding="utf-8")
    output = tmp_path / "receipt.json"
    code = canary.execute(
        root=tmp_path,
        output=output,
        execute_live=True,
        approval_path=None,
        model="gemini-2.5-flash",
        idempotency_key="one-time-key",
        stop_file=stop,
        idempotency_store=tmp_path / "idempotency",
        provider=lambda *args: pytest.fail("provider must not run"),
    )
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert code == 2
    assert receipt["outcome"] == "EMERGENCY_STOP_ACTIVE"
    assert receipt["network_calls"] == 0


def test_canary_replay_is_rejected(canary: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sha = "c" * 40
    model = "gemini-2.5-flash"
    key = "one-time-key"
    monkeypatch.setattr(canary, "git_sha", lambda _: sha)
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval_for(canary, sha=sha, model=model, key=key)), encoding="utf-8")
    store = tmp_path / "idempotency"

    def provider(*args):
        return {
            "provider": "fake",
            "model_version": model,
            "response_id": "fake-response",
            "usage": {"prompt_tokens": 1, "candidate_tokens": 1, "total_tokens": 2},
            "output": "safe synthetic result",
        }

    first = canary.execute(
        root=tmp_path,
        output=tmp_path / "first.json",
        execute_live=True,
        approval_path=approval_path,
        model=model,
        idempotency_key=key,
        stop_file=tmp_path / "stop",
        idempotency_store=store,
        provider=provider,
    )
    second = canary.execute(
        root=tmp_path,
        output=tmp_path / "second.json",
        execute_live=True,
        approval_path=approval_path,
        model=model,
        idempotency_key=key,
        stop_file=tmp_path / "stop",
        idempotency_store=store,
        provider=provider,
    )
    second_receipt = json.loads((tmp_path / "second.json").read_text(encoding="utf-8"))
    assert first == 0
    assert second == 2
    assert second_receipt["outcome"] == "IDEMPOTENCY_REPLAY_BLOCKED"
    assert second_receipt["network_calls"] == 0


def test_canary_invalid_approval_is_fail_closed(canary: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sha = "d" * 40
    monkeypatch.setattr(canary, "git_sha", lambda _: sha)
    approval = approval_for(canary, sha=sha, model="gemini-2.5-flash", key="key")
    approval["git_sha"] = "e" * 40
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(approval), encoding="utf-8")
    output = tmp_path / "receipt.json"
    code = canary.execute(
        root=tmp_path,
        output=output,
        execute_live=True,
        approval_path=path,
        model="gemini-2.5-flash",
        idempotency_key="key",
        stop_file=tmp_path / "stop",
        idempotency_store=tmp_path / "idempotency",
        provider=lambda *args: pytest.fail("provider must not run"),
    )
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert code == 2
    assert receipt["outcome"] == "APPROVAL_INVALID"
    assert "approval field mismatch: git_sha" in receipt["authorization_errors"]
