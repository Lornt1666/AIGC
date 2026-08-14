from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TF_ROOT = ROOT / "infra" / "gcp" / "quebec"


def _resource_block(text: str, resource_type: str, name: str) -> str:
    marker = f'resource "{resource_type}" "{name}"'
    assert marker in text
    return text.split(marker, 1)[1].split('\nresource "', 1)[0]


def _permissions(block: str) -> set[str]:
    match = re.search(r"permissions\s*=\s*\[(.*?)\]", block, flags=re.DOTALL)
    assert match is not None
    return set(re.findall(r'"([a-z][A-Za-z.]+)"', match.group(1)))


def test_canary_job_control_identities_are_deterministic_and_in_inventory() -> None:
    main = (TF_ROOT / "main.tf").read_text(encoding="utf-8")
    assert 'account_id   = "${var.resource_prefix}-can-prov"' in main
    assert 'account_id   = "${var.resource_prefix}-can-exec"' in main

    required_accounts = {"canary_provisioner", "canary_executor"}
    for schema_path in (
        ROOT / "schemas" / "quebec_cloud_authorization.schema.json",
        ROOT / "schemas" / "quebec_resource_manifest.schema.json",
    ):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema_path.name == "quebec_cloud_authorization.schema.json":
            accounts = schema["properties"]["service_accounts"]
        else:
            accounts = schema["properties"]["authorization_bindings"]["properties"][
                "service_accounts"
            ]
        assert required_accounts.issubset(accounts["required"])
        assert required_accounts.issubset(accounts["properties"])

    authorization_example = json.loads(
        (ROOT / "config" / "quebec_staging_authorization.example.json").read_text(
            encoding="utf-8"
        )
    )
    manifest_example = json.loads(
        (ROOT / "config" / "quebec_resource_manifest.example.json").read_text(
            encoding="utf-8"
        )
    )
    assert required_accounts.issubset(authorization_example["service_accounts"])
    assert required_accounts.issubset(
        manifest_example["authorization_bindings"]["service_accounts"]
    )


def test_canary_provisioner_has_only_bounded_job_control_permissions() -> None:
    external = (TF_ROOT / "external_identity_and_secrets.tf").read_text(
        encoding="utf-8"
    )
    role = _resource_block(
        external, "google_project_iam_custom_role", "canary_job_provisioner"
    )
    assert _permissions(role) == {
        "run.jobs.create",
        "run.jobs.get",
        "run.jobs.update",
    }
    support = _resource_block(
        external, "google_project_iam_custom_role", "canary_provisioner_support"
    )
    assert _permissions(support) == {
        "iam.serviceAccounts.getIamPolicy",
        "resourcemanager.projects.get",
        "resourcemanager.projects.getIamPolicy",
        "run.operations.get",
        "serviceusage.services.use",
    }
    for forbidden in (
        "run.jobs.run",
        "run.jobs.runWithOverrides",
        "run.jobs.delete",
        "run.jobs.getIamPolicy",
        "run.jobs.setIamPolicy",
        "run.executions.delete",
        "run.executions.cancel",
    ):
        assert forbidden not in role


def test_canary_executor_has_readback_but_no_project_wide_run() -> None:
    external = (TF_ROOT / "external_identity_and_secrets.tf").read_text(
        encoding="utf-8"
    )
    role = _resource_block(
        external, "google_project_iam_custom_role", "canary_job_executor"
    )
    assert _permissions(role) == {
        "run.jobs.get",
        "run.jobs.getIamPolicy",
    }
    evidence = _resource_block(
        external,
        "google_project_iam_custom_role",
        "canary_executor_evidence_reader",
    )
    assert _permissions(evidence) == {
        "logging.logEntries.list",
        "run.executions.get",
        "run.operations.get",
    }
    for forbidden in (
        "run.jobs.runWithOverrides",
        "run.jobs.create",
        "run.jobs.update",
        "run.jobs.delete",
        "run.jobs.setIamPolicy",
        "run.executions.delete",
        "run.executions.cancel",
        "iam.serviceAccounts.actAs",
    ):
        assert forbidden not in role


def test_canary_provisioner_dependencies_are_resource_scoped_and_read_only() -> None:
    main = (TF_ROOT / "main.tf").read_text(encoding="utf-8")
    external = (TF_ROOT / "external_identity_and_secrets.tf").read_text(
        encoding="utf-8"
    )

    image_role = _resource_block(
        external, "google_project_iam_custom_role", "canary_image_reader"
    )
    assert _permissions(image_role) == {
        "artifactregistry.dockerimages.get",
        "artifactregistry.dockerimages.list",
        "artifactregistry.repositories.downloadArtifacts",
        "artifactregistry.repositories.get",
    }
    image_binding = _resource_block(
        main,
        "google_artifact_registry_repository_iam_member",
        "canary_provisioner_image_reader",
    )
    assert "google_artifact_registry_repository.runtime[0].name" in image_binding
    assert 'identity["canary_provisioner"].email' in image_binding

    network_role = _resource_block(
        external, "google_project_iam_custom_role", "canary_network_inspector"
    )
    assert _permissions(network_role) == {"compute.networks.get"}
    subnet_role = _resource_block(
        external, "google_project_iam_custom_role", "canary_subnetwork_user"
    )
    assert _permissions(subnet_role) == {
        "compute.subnetworks.get",
        "compute.subnetworks.use",
    }
    subnet_binding = _resource_block(
        main,
        "google_compute_subnetwork_iam_member",
        "canary_provisioner_subnetwork_user",
    )
    assert "google_compute_subnetwork.serverless[0].name" in subnet_binding
    assert 'identity["canary_provisioner"].email' in subnet_binding
    assert "roles/compute.networkUser" not in subnet_binding

    receipt_binding = _resource_block(
        external,
        "google_storage_bucket_iam_member",
        "canary_provisioning_receipt_creator",
    )
    assert 'google_storage_bucket.regional["receipts"].name' in receipt_binding
    assert 'role   = "roles/storage.objectCreator"' in receipt_binding
    assert 'identity["canary_provisioner"].email' in receipt_binding


def test_canary_provisioner_mutation_and_act_as_roles_are_inert_by_default() -> None:
    external = (TF_ROOT / "external_identity_and_secrets.tf").read_text(
        encoding="utf-8"
    )
    assert 'resource "google_project_iam_member" "canary_job_provisioner"' not in external
    assert 'resource "google_service_account_iam_member" "canary_provisioner_uses_runtime"' not in external

    service_account_bindings = re.findall(
        r'resource "google_service_account_iam_member" "[^"]+"\s*\{'
        r'(.*?)(?=\nresource "|\Z)',
        external,
        flags=re.DOTALL,
    )
    act_as_bindings = "\n".join(
        block
        for block in service_account_bindings
        if 'role               = "roles/iam.serviceAccountUser"' in block
    )
    assert 'identity["canary_executor"]' not in act_as_bindings
    assert 'identity["canary_provisioner"].email' not in act_as_bindings


def test_canary_control_identities_are_keyless_kms_readers_and_not_federated() -> None:
    main = (TF_ROOT / "main.tf").read_text(encoding="utf-8")
    external = (TF_ROOT / "external_identity_and_secrets.tf").read_text(
        encoding="utf-8"
    )
    kms = _resource_block(
        main,
        "google_kms_crypto_key_iam_member",
        "canary_authority_public_key_viewer",
    )
    assert 'canary_provisioner = google_service_account.identity["canary_provisioner"].email' in kms
    assert 'canary_executor    = google_service_account.identity["canary_executor"].email' in kms
    assert 'canary_binder      = google_service_account.identity["canary_binder"].email' in kms
    assert 'canary_publisher   = google_service_account.identity["canary_publisher"].email' in kms
    assert 'role          = "roles/cloudkms.publicKeyViewer"' in kms

    assert external.count('role               = "roles/iam.workloadIdentityUser"') == 1
    wif = _resource_block(
        external,
        "google_service_account_iam_member",
        "github_wif_security_review",
    )
    assert 'identity["security_review"].name' in wif
    assert "canary_provisioner" not in wif
    assert "canary_executor" not in wif
    assert "canary_binder" not in wif
    assert "canary_publisher" not in wif
    assert 'resource "google_service_account_key"' not in main + external


def test_canary_control_identities_do_not_inherit_broad_deployer_roles() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in TF_ROOT.glob("*.tf")
    )
    for broad_role in (
        'roles/run.admin',
        'roles/run.developer',
        'roles/run.editor',
        'roles/run.viewer',
        'roles/artifactregistry.reader',
        'roles/compute.networkUser',
        'roles/iam.serviceAccountTokenCreator',
        'roles/editor',
        'roles/owner',
    ):
        assert broad_role not in combined

    external = (TF_ROOT / "external_identity_and_secrets.tf").read_text(
        encoding="utf-8"
    )
    assert 'resource "google_project_iam_member" "deployer_release"' in external
    for removed_mutating_binding in (
        "deployer_sbom_metadata_loader",
        "deployer_uses_cloud_build",
        "deployer_build_source_writer",
        "deployer_sbom_object_writer",
        "deployer_receipt_creator",
    ):
        assert f'"{removed_mutating_binding}"' not in external
    assert 'resource "google_project_iam_member" "deployer_invokes_release_candidates"' not in external


def test_canary_binder_and_publisher_are_narrow_and_non_impersonable() -> None:
    external = (TF_ROOT / "external_identity_and_secrets.tf").read_text(
        encoding="utf-8"
    )
    binder = _resource_block(
        external, "google_project_iam_custom_role", "canary_job_iam_binder"
    )
    assert _permissions(binder) == {
        "run.jobs.get", "run.jobs.getIamPolicy", "run.jobs.setIamPolicy"
    }
    assert 'resource "google_project_iam_member" "canary_job_iam_binder"' not in external
    publisher = _resource_block(
        external, "google_storage_bucket_iam_member", "canary_receipt_publisher_creator"
    )
    assert 'role   = "roles/storage.objectCreator"' in publisher
    assert 'identity["canary_publisher"].email' in publisher
