from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

import scripts.aigc_external_release_procurement as procurement
import scripts.provision_nexus_regional_secret_version as secrets


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config" / "aigc_external_release_procurement.example.json"
NOW = datetime(2026, 8, 8, 14, 0, tzinfo=timezone.utc)


def executable_payload() -> dict:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["template_only"] = False
    payload["release_sha"] = "a" * 40
    payload["release_tree_sha"] = "b" * 40
    payload["authority"]["authorized_by"] = "operator:test"
    payload["authority"]["authorized_at"] = "2026-08-08T13:00:00+00:00"
    payload["authority"]["expires_at"] = "2026-08-08T18:00:00+00:00"
    return payload


def test_committed_external_procurement_contract_is_inert_and_zero_spend():
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    contract = procurement.ExternalReleaseContract(payload=payload)
    contract.validate()
    assert payload["template_only"] is True
    assert payload["monthly_budget_cad"] == 0
    assert payload["provider_canary_spend_cad"] == 0
    assert payload["authority"]["read_only_discovery_authorized"] is True
    for flag in procurement.AUTHORITY_FLAGS:
        if flag != "read_only_discovery_authorized":
            assert payload["authority"][flag] is False
    assert payload["authority"]["authorized_by"] == ""
    assert payload["authority"]["authorized_at"] is None
    assert payload["authority"]["expires_at"] is None


def test_resource_manifest_is_deterministic_and_binds_verified_project_identity():
    contract = procurement.ExternalReleaseContract.load(EXAMPLE)
    first = procurement.build_resource_manifest(contract)
    second = procurement.build_resource_manifest(contract)
    assert first == second
    assert first["project_id"] == "oceanic-base-485407-i7"
    assert first["project_number"] == "170151535592"
    assert first["region"] == procurement.REGION
    assert first["public_resources"] is False
    assert first["production_resources"] is False
    assert first["service_account_keys"] is False


def test_template_cannot_be_promoted_by_flipping_plan_flag():
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["authority"]["terraform_plan_authorized"] = True
    with pytest.raises(procurement.ProcurementError, match="template-only"):
        procurement.ExternalReleaseContract(payload=payload).validate()


def test_non_template_requires_bounded_authority_window():
    payload = executable_payload()
    payload["authority"]["expires_at"] = None
    with pytest.raises(procurement.ProcurementError, match="expires_at"):
        procurement.ExternalReleaseContract(payload=payload).validate(now=NOW)


def test_expired_external_authority_is_rejected():
    payload = executable_payload()
    payload["authority"]["expires_at"] = "2026-08-08T13:30:00+00:00"
    with pytest.raises(procurement.ProcurementError, match="expired"):
        procurement.ExternalReleaseContract(payload=payload).validate(now=NOW)


def test_resource_creation_intent_requires_plan_authority():
    payload = executable_payload()
    payload["authority"]["resource_creation_authorized"] = True
    with pytest.raises(procurement.ProcurementError, match="plan authority"):
        procurement.ExternalReleaseContract(payload=payload).validate(now=NOW)


def test_zero_budget_blocks_non_template_material_terraform_plan():
    payload = executable_payload()
    payload["authority"]["terraform_plan_authorized"] = True
    payload["authority"]["resource_creation_authorized"] = True
    contract = procurement.ExternalReleaseContract(payload=payload)
    contract.validate(now=NOW)
    with pytest.raises(procurement.ProcurementError, match="nonzero reviewed monthly_budget_cad"):
        procurement.terraform_inputs(contract, procurement.build_resource_manifest(contract))


def test_material_terraform_plan_emits_creation_intent_but_never_deployment_or_live_model_authority():
    payload = executable_payload()
    payload["monthly_budget_cad"] = 25
    payload["budget_notification_channels"] = [
        "projects/aigc-stage/notificationChannels/123"
    ]
    payload["authority"]["terraform_plan_authorized"] = True
    payload["authority"]["resource_creation_authorized"] = True
    contract = procurement.ExternalReleaseContract(payload=payload)
    contract.validate(now=NOW)
    variables = procurement.terraform_inputs(contract, procurement.build_resource_manifest(contract))
    assert variables["resource_creation_authorized"] is True
    assert variables["staging_deployment_authorized"] is False
    assert variables["live_model_call_authorized"] is False
    assert variables["production_activation_authorized"] is False


def test_wif_is_repo_id_owner_id_and_ref_restricted_without_service_account_keys():
    text = (ROOT / "infra" / "gcp" / "quebec" / "external_identity_and_secrets.tf").read_text(encoding="utf-8")
    assert 'github_repository_id       = "1287333065"' in text
    assert 'github_repository_owner_id = "236225491"' in text
    assert "refs/heads/release/aigc-nexus-v1" in text
    assert "refs/heads/main" in text
    assert "roles/iam.workloadIdentityUser" in text
    assert "google_service_account_key" not in text
    assert "google_secret_manager_regional_secret_version" not in text
    assert "openai-api-key" in text


def test_control_plane_explicitly_enables_sts_and_serviceusage():
    text = (ROOT / "infra" / "gcp" / "quebec" / "platform_apis.tf").read_text(encoding="utf-8")
    assert '"sts.googleapis.com"' in text
    assert '"serviceusage.googleapis.com"' in text


def test_secret_plan_never_requires_reading_value_file(monkeypatch, tmp_path: Path):
    calls: list[list[str]] = []

    def fake_run(command, *, capture=True, mutating=False):
        calls.append(list(command))
        if command[:4] == ["gcloud", "secrets", "versions", "list"]:
            return ""
        return "projects/aigc-stage/locations/northamerica-northeast1/secrets/runtime"

    monkeypatch.setattr(secrets, "_run", fake_run)
    result = secrets.provision(
        project="aigc-stage",
        purpose="runtime_control_dsn",
        secret_id="runtime",
        value_file=tmp_path / "does-not-exist",
        execute=False,
    )
    assert result["new_version_authorized"] is False
    assert result["secret_value_read_by_script"] is False
    assert result["secret_value_emitted"] is False
    assert all("versions add" not in " ".join(call) for call in calls)


def test_staging_deployment_uses_private_vpc_and_user_specified_build_identity():
    text = (ROOT / "scripts" / "deploy_nexus_staging.py").read_text(encoding="utf-8")
    assert '"--service-account", build_service_account' in text
    assert '"--network", network' in text
    assert '"--subnet", subnet' in text
    assert '"--vpc-egress", "private-ranges-only"' in text
    assert "src.operations.nexus_postgres_migrate" in text
    assert '"--max-retries", "0"' in text
