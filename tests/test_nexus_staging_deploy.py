from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.deploy_nexus_staging as deployer


RELEASE = "a" * 40
TREE = "b" * 40
DIGEST = "sha256:" + "c" * 64


def payload():
    return {
        "project_id": "aigc-stage",
        "release_sha": RELEASE,
        "release_tree_sha": TREE,
        "resource_manifest_sha256": "d" * 64,
        "resources": {
            "artifact_registry_repository": "aigc-runtime",
            "operator_service": "aigc-nexus-operator",
            "cloud_sql_instance": "aigc-control",
        },
        "service_accounts": {
            "operator": "aigc-operator@aigc-stage.iam.gserviceaccount.com",
            "cloud_build": "aigc-build@aigc-stage.iam.gserviceaccount.com",
        },
        "exact_secret_version_refs": {
            "runtime_control_dsn": "projects/aigc-stage/locations/northamerica-northeast1/secrets/runtime-control-dsn/versions/7"
        },
    }


def summary():
    return {
        "project_id": "aigc-stage",
        "region": deployer.REGION,
        "release_sha": RELEASE,
        "release_tree_sha": TREE,
    }


def test_build_plan_is_immutable_private_no_traffic_and_non_generative(monkeypatch):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    plan = deployer.build_plan(payload(), {})
    assert plan["deployment_image_form"].endswith("@sha256:<registry-resolved>")
    assert plan["public_traffic"] is False
    assert plan["traffic_migration"] is False
    assert plan["live_model_call"] is False
    assert plan["production_activation"] is False
    assert plan["readiness_path"] == "/ready"
    assert plan["runtime_migration_required"] is True
    assert plan["vpc_egress"] == "private-ranges-only"


def test_deploy_builds_regionally_migrates_and_deploys_digest_with_private_probes(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    monkeypatch.setattr(deployer, "_git_identity", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        deployer,
        "_authenticated_json",
        lambda *_args, **_kwargs: {"ready": True, "runtime_control_backend": "postgresql"},
    )
    monkeypatch.setattr(
        deployer,
        "_run_runtime_migration",
        lambda **_kwargs: {
            "job_name": "aigc-migrate",
            "execution_name": "execution-1",
            "receipt": {"runtime_control_singleton_verified": True},
            "automatic_retry": False,
            "max_retries": 0,
        },
    )
    commands: list[list[str]] = []
    runtime_env = ""

    def fake_run(command, *, capture=False, mutating=False):
        nonlocal runtime_env
        command = list(command)
        commands.append(command)
        if command[:3] == ["gcloud", "builds", "submit"]:
            assert mutating is True
            assert "--region" in command and deployer.REGION in command
            assert "--service-account" in command
            return "build-123"
        if command[:5] == ["gcloud", "artifacts", "docker", "images", "describe"]:
            return DIGEST
        if command[:3] == ["gcloud", "run", "deploy"]:
            assert mutating is True
            env_file = Path(command[command.index("--env-vars-file") + 1])
            runtime_env = env_file.read_text(encoding="utf-8")
            return ""
        if command[:4] == ["gcloud", "run", "services", "describe"]:
            return json.dumps(
                {
                    "status": {
                        "url": "https://service.example.invalid",
                        "traffic": [
                            {
                                "tag": f"candidate-{RELEASE[:8]}",
                                "revisionName": "aigc-nexus-00001",
                                "url": "https://candidate.example.invalid",
                            }
                        ],
                    }
                }
            )
        return ""

    monkeypatch.setattr(deployer, "_run", fake_run)
    output = tmp_path / "receipt.json"
    receipt = deployer.deploy(payload(), {}, output=output)
    run_command = next(command for command in commands if command[:3] == ["gcloud", "run", "deploy"])
    immutable = f"northamerica-northeast1-docker.pkg.dev/aigc-stage/aigc-runtime/aigc-nexus@{DIGEST}"
    assert run_command[run_command.index("--image") + 1] == immutable
    assert "--no-traffic" in run_command
    assert "--no-allow-unauthenticated" in run_command
    assert run_command[run_command.index("--vpc-egress") + 1] == "private-ranges-only"
    assert "--network" in run_command
    assert "--subnet" in run_command
    assert "--startup-probe" in run_command
    startup = run_command[run_command.index("--startup-probe") + 1]
    assert "path=/health" in startup
    assert "--liveness-probe" in run_command
    assert "--readiness-probe" in run_command
    assert "AIGC_LIVE_PROVIDER_EXECUTION_ENABLED: \"false\"" in runtime_env
    assert "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF" in runtime_env
    assert "opaque" not in runtime_env
    assert receipt["readiness_verified"] is True
    assert receipt["runtime_migration"]["receipt"]["runtime_control_singleton_verified"] is True
    assert receipt["traffic_migration_performed"] is False
    assert receipt["live_model_call_performed"] is False
    assert output.exists()


def test_mutating_command_failure_is_indeterminate(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "failure"

    monkeypatch.setattr(deployer.subprocess, "run", lambda *_args, **_kwargs: Result())
    with pytest.raises(deployer.NexusStagingMutationIndeterminate):
        deployer._run(["gcloud", "run", "deploy"], mutating=True)
