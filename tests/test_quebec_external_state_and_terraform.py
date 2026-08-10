from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

import scripts.bootstrap_quebec_terraform_state as state_bootstrap
import scripts.terraform_quebec_foundation as foundation
from scripts.aigc_external_release_procurement import ExternalReleaseContract


NOW = datetime(2026, 8, 8, 14, 0, tzinfo=timezone.utc)


def payload() -> dict:
    return {
        "schema_version": "aigc.external-release-procurement.v1",
        "template_only": False,
        "repository": "Lornt1666/AIGC",
        "project_id": "aigc-stage",
        "project_number": "170151535592",
        "billing_account_id": "0156E0-2BDD06-7561F1",
        "region": "northamerica-northeast1",
        "resource_prefix": "aigc-qc-stg",
        "release_sha": "a" * 40,
        "release_tree_sha": "b" * 40,
        "monthly_budget_cad": 25,
        "budget_notification_channels": ["projects/aigc-stage/notificationChannels/123"],
        "provider_canary_spend_cad": 1,
        "gemini_model": "example-gemini",
        "openai_model": "example-openai",
        "pricing": {
            "gemini_input_cad_per_million": 1,
            "gemini_output_cad_per_million": 2,
            "openai_input_cad_per_million": 1,
            "openai_output_cad_per_million": 2,
        },
        "authority": {
            "authorized_by": "operator:test",
            "authorized_at": "2026-08-08T13:00:00+00:00",
            "expires_at": "2026-08-08T18:00:00+00:00",
            "read_only_discovery_authorized": True,
            "state_backend_bootstrap_authorized": False,
            "terraform_plan_authorized": False,
            "resource_creation_authorized": False,
            "terraform_apply_authorized": False,
            "secret_version_creation_authorized": False,
            "gemini_canary_authorized": False,
            "openai_canary_authorized": False,
            "staging_deployment_authorized": False,
            "load_validation_authorized": False,
            "fault_injection_authorized": False,
            "mark_pr_ready_authorized": False,
            "merge_authorized": False,
            "production_activation_authorized": False,
        },
    }


def contract(**flags: bool) -> ExternalReleaseContract:
    value = payload()
    value["authority"].update(flags)
    item = ExternalReleaseContract(payload=value)
    item.validate(now=NOW)
    return item


def discovery_ok() -> dict:
    return {
        "project_number_matches": True,
        "billing_link_matches": True,
        "billing_link_enabled": True,
        "wif_pool_exists": True,
        "wif_provider_exists": True,
        "artifact_registry_exists": True,
        "cloud_sql_exists": True,
        "service_accounts": {
            "deployer": True,
            "cloud_build": True,
            "operator": True,
            "canary_gemini": True,
            "canary_openai": True,
            "canary_provisioner": True,
            "canary_executor": True,
            "judge": True,
            "security_review": True,
            "authority_signer": True,
        },
        "regional_secret_metadata": {
            "runtime_control_dsn": True,
            "operator_token": True,
            "operator_binding_key": True,
            "runtime_admin_token": True,
            "runtime_admin_binding_key": True,
            "judge_token": True,
            "judge_binding_key": True,
            "openai_api_key": True,
        },
    }


def state_receipt() -> dict:
    return {
        "schema_version": "aigc.quebec-terraform-state-receipt.v1",
        "status": "succeeded",
        "project_id": "aigc-stage",
        "region": "northamerica-northeast1",
        "bucket": "aigc-stage-aigc-qc-stg-tfstate",
        "prefix": "aigc/nexus-v1",
        "reconciliation_required": False,
    }


def test_state_bootstrap_plan_is_read_only(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(state_bootstrap, "discover", lambda _contract: discovery_ok())
    monkeypatch.setattr(state_bootstrap, "_describe", lambda _bucket: None)
    output = tmp_path / "state-plan.json"
    result = state_bootstrap.bootstrap(
        contract(),
        execute=False,
        output=output,
    )
    assert result["cloud_mutation_performed"] is False
    assert result["bucket"].endswith("-tfstate")
    assert result["prefix"] == "aigc/nexus-v1"


def test_state_bootstrap_execute_requires_explicit_state_authority(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(state_bootstrap, "discover", lambda _contract: discovery_ok())
    monkeypatch.setattr(state_bootstrap, "_describe", lambda _bucket: None)
    with pytest.raises(state_bootstrap.StateBootstrapError, match="not authorized"):
        state_bootstrap.bootstrap(
            contract(),
            execute=True,
            output=tmp_path / "state.json",
        )


def test_state_bootstrap_creates_montreal_hardened_bucket_without_blind_retry(monkeypatch, tmp_path: Path):
    item = contract(state_backend_bootstrap_authorized=True)
    monkeypatch.setattr(state_bootstrap, "discover", lambda _contract: discovery_ok())
    observed = [None, {
        "location": "northamerica-northeast1",
        "iamConfiguration": {
            "uniformBucketLevelAccess": {"enabled": True},
            "publicAccessPrevention": "enforced",
        },
        "versioning": {"enabled": True},
        "retentionPolicy": {"retentionPeriod": state_bootstrap.RETENTION_SECONDS},
    }]
    monkeypatch.setattr(state_bootstrap, "_describe", lambda _bucket: observed.pop(0))
    commands: list[list[str]] = []
    monkeypatch.setattr(
        state_bootstrap,
        "_run",
        lambda command, *, mutating=False: commands.append(list(command)) or "",
    )
    result = state_bootstrap.bootstrap(
        item,
        execute=True,
        output=tmp_path / "state.json",
    )
    assert result["status"] == "succeeded"
    assert result["automatic_retry"] is False
    create = next(command for command in commands if command[:4] == ["gcloud", "storage", "buckets", "create"])
    assert "--uniform-bucket-level-access" in create
    assert "--public-access-prevention" in create
    assert "--location" in create and "northamerica-northeast1" in create


def test_foundation_plan_is_saved_digest_bound_and_non_mutating(monkeypatch, tmp_path: Path):
    item = contract(terraform_plan_authorized=True, resource_creation_authorized=True)
    monkeypatch.setattr(foundation, "assert_git_identity", lambda _contract: None)
    monkeypatch.setattr(foundation, "discover", lambda _contract: discovery_ok())
    monkeypatch.setattr(foundation, "_init_backend", lambda **_kwargs: None)
    commands: list[list[str]] = []

    def fake_run(command, *, capture=True, mutating=False):
        commands.append(list(command))
        if "plan" in command:
            Path(command[-1].split("=", 1)[1]).write_bytes(b"saved-plan")
        return ""

    monkeypatch.setattr(foundation, "_run", fake_run)
    monkeypatch.setattr(
        foundation,
        "_plan_summary",
        lambda _path: {
            "counts": {"create": 12, "update": 0, "delete": 0, "replace": 0, "no_op": 0, "read": 0},
            "addresses": ("google_project_service.required",),
        },
    )
    plan_file = tmp_path / "foundation.tfplan"
    receipt = foundation.create_plan(
        contract=item,
        state_receipt=state_receipt(),
        plan_file=plan_file,
        receipt_file=tmp_path / "plan-receipt.json",
    )
    assert receipt["terraform_apply_performed"] is False
    assert receipt["cloud_mutation_performed"] is False
    assert receipt["plan_sha256"] == hashlib.sha256(b"saved-plan").hexdigest()
    assert any("plan" in command for command in commands)


def test_foundation_apply_rejects_plan_digest_mismatch_before_mutation(monkeypatch, tmp_path: Path):
    item = contract(
        terraform_plan_authorized=True,
        resource_creation_authorized=True,
        terraform_apply_authorized=True,
    )
    monkeypatch.setattr(foundation, "assert_git_identity", lambda _contract: None)
    monkeypatch.setattr(foundation, "_init_backend", lambda **_kwargs: None)
    plan_file = tmp_path / "foundation.tfplan"
    plan_file.write_bytes(b"actual-plan")
    receipt = {
        "schema_version": "aigc.quebec-terraform-foundation-plan-receipt.v1",
        "project_id": item.project_id,
        "release_sha": item.payload["release_sha"],
        "release_tree_sha": item.payload["release_tree_sha"],
        "procurement_sha256": foundation.canonical_sha256(item.payload),
        "state_receipt_sha256": foundation.canonical_sha256(state_receipt()),
        "backend_bucket": state_receipt()["bucket"],
        "backend_prefix": state_receipt()["prefix"],
        "plan_sha256": "0" * 64,
        "resource_change_counts": {"delete": 0, "replace": 0},
    }
    with pytest.raises(foundation.TerraformFoundationError, match="digest mismatch"):
        foundation.apply_plan(
            contract=item,
            state_receipt=state_receipt(),
            plan_file=plan_file,
            plan_receipt=receipt,
            receipt_file=tmp_path / "apply.json",
        )


def test_gcs_backend_is_declared_but_contains_no_committed_bucket_name():
    backend = (Path(__file__).resolve().parents[1] / "infra" / "gcp" / "quebec" / "backend.tf").read_text(encoding="utf-8")
    assert 'backend "gcs"' in backend
    assert "bucket" not in backend
    assert "prefix" not in backend
