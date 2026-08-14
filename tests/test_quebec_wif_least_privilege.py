from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _resource_block(text: str, resource_type: str, name: str) -> str:
    marker = f'resource "{resource_type}" "{name}"'
    assert marker in text
    return text.split(marker, 1)[1].split('\nresource "', 1)[0]


def test_wif_accepts_only_manual_protected_main_release_workflow() -> None:
    text = (ROOT / "infra/gcp/quebec/external_identity_and_secrets.tf").read_text(
        encoding="utf-8"
    )
    for mapping_name in ("workflow_ref", "event_name", "environment"):
        assert re.search(
            rf'"attribute\.{mapping_name}"\s*=\s*"assertion\.{mapping_name}"',
            text,
        )
    for required in (
        "assertion.repository_id == '${local.github_repository_id}'",
        "assertion.repository_owner_id == '${local.github_repository_owner_id}'",
        "assertion.repository_visibility == 'private'",
        "assertion.ref == 'refs/heads/main'",
        "assertion.workflow_ref == '${local.github_release_workflow}'",
        "assertion.event_name == 'workflow_dispatch'",
        "assertion.environment == '${local.github_release_environment}'",
    ):
        assert required in text
    assert "assertion.job_workflow_ref" not in text
    assert "refs/heads/release/aigc-nexus-v1' ||" not in text
    assert 'resource "google_service_account_iam_member" "github_wif_security_review"' in text
    wif_binding = text.split(
        'resource "google_service_account_iam_member" "github_wif_security_review"', 1
    )[1].split("}", 1)[0]
    assert 'google_service_account.identity["security_review"].name' in wif_binding
    assert 'google_service_account.identity["deployer"].name' not in wif_binding
    assert 'resource "google_service_account_iam_member" "github_wif_deployer"' not in text


def test_deployer_and_build_source_avoid_broad_project_roles() -> None:
    external = (
        ROOT / "infra/gcp/quebec/external_identity_and_secrets.tf"
    ).read_text(encoding="utf-8")
    main = (ROOT / "infra/gcp/quebec/main.tf").read_text(encoding="utf-8")
    combined = external + "\n" + main
    for forbidden in (
        'role    = "roles/cloudbuild.builds.editor"',
        'role    = "roles/logging.viewer"',
        'role    = "roles/run.developer"',
    ):
        assert forbidden not in combined
    project_viewer = (
        'resource "google_project_iam_member" "cloud_build_source_reader"'
    )
    assert project_viewer not in external
    assert (
        'resource "google_storage_bucket_iam_member" '
        '"cloud_build_source_reader"'
    ) in external
    assert "google_secret_manager_regional_secret_iam_member\" \"judge_access" not in external
    for forbidden_binding in (
        "deployer_receipt_creator",
        "deployer_build_source_writer",
        "deployer_sbom_object_writer",
        "deployer_sbom_metadata_loader",
        "deployer_uses_cloud_build",
    ):
        assert f'"{forbidden_binding}"' not in external
    for forbidden_binding in ("deployer_uses_operator", "deployer_uses_judge"):
        assert f'"{forbidden_binding}"' not in main
    release_role = _resource_block(
        external,
        "google_project_iam_custom_role",
        "release_deployer",
    )
    for forbidden_permission in (
        "cloudbuild.builds.create",
        "run.jobs.create",
        "run.jobs.run",
        "run.jobs.update",
        "run.services.create",
        "run.services.update",
    ):
        assert f'"{forbidden_permission}"' not in release_role
    assert "roles/storage.objectAdmin" not in combined
    assert "roles/storage.admin" not in combined


def test_sbom_load_iam_is_exact_bucket_repository_and_create_only_metadata() -> None:
    external = (
        ROOT / "infra/gcp/quebec/external_identity_and_secrets.tf"
    ).read_text(encoding="utf-8")
    main = (ROOT / "infra/gcp/quebec/main.tf").read_text(encoding="utf-8")
    combined = external + "\n" + main

    assert "roles/storage.admin" not in combined
    assert "roles/storage.objectAdmin" not in combined
    assert "roles/artifactregistry.reader" not in combined

    bucket_role = _resource_block(
        external,
        "google_project_iam_custom_role",
        "sbom_object_writer",
    )
    assert '"storage.buckets.get"' in bucket_role
    assert '"storage.objects.create"' in bucket_role
    for forbidden in (
        "storage.buckets.create",
        "storage.buckets.list",
        "storage.objects.delete",
        "storage.objects.get",
        "storage.objects.list",
        "storage.objects.update",
    ):
        assert forbidden not in bucket_role

    assert (
        'resource "google_storage_bucket_iam_member" '
        '"deployer_sbom_object_writer"'
    ) not in external

    image_role = _resource_block(
        external,
        "google_project_iam_custom_role",
        "sbom_image_reader",
    )
    assert '"artifactregistry.dockerimages.get"' in image_role
    assert '"artifactregistry.dockerimages.list"' in image_role
    assert '"artifactregistry.repositories.downloadArtifacts"' in image_role
    assert '"artifactregistry.repositories.get"' in image_role
    assert "artifactregistry.repositories.list" not in image_role
    repository_binding = _resource_block(
        main,
        "google_artifact_registry_repository_iam_member",
        "deployer_reader",
    )
    assert "google_artifact_registry_repository.runtime[0].name" in repository_binding
    assert "google_project_iam_custom_role.sbom_image_reader[0].name" in repository_binding
    release_role = _resource_block(
        external,
        "google_project_iam_custom_role",
        "release_deployer",
    )
    assert "artifactregistry.dockerimages.get" not in release_role
    assert "artifactregistry.dockerimages.list" not in release_role
    assert "artifactregistry.projectsettings.get" not in release_role
    assert "artifactregistry.repositories.get" not in release_role

    metadata_role = _resource_block(
        external,
        "google_project_iam_custom_role",
        "sbom_metadata_loader",
    )
    for required in (
        "containeranalysis.notes.attachOccurrence",
        "containeranalysis.notes.create",
        "containeranalysis.notes.get",
        "containeranalysis.notes.list",
        "containeranalysis.occurrences.create",
        "containeranalysis.occurrences.get",
        "containeranalysis.occurrences.list",
    ):
        assert f'"{required}"' in metadata_role
    for forbidden in ("delete", "update", "setIamPolicy"):
        assert f"containeranalysis.notes.{forbidden}" not in metadata_role
        assert f"containeranalysis.occurrences.{forbidden}" not in metadata_role


def test_wif_waits_for_iam_and_iamcredentials_apis() -> None:
    external = (
        ROOT / "infra/gcp/quebec/external_identity_and_secrets.tf"
    ).read_text(encoding="utf-8")
    wif = external.split(
        'resource "google_iam_workload_identity_pool" "github"', 1
    )[1].split(
        'resource "google_iam_workload_identity_pool_provider" "github"', 1
    )[0]
    assert "google_project_service.platform_control_plane" in wif
    assert "google_project_service.required" in wif


def test_canary_kms_trust_root_and_signing_identity_are_exact() -> None:
    main = (ROOT / "infra/gcp/quebec/main.tf").read_text(encoding="utf-8")
    assert 'resource "google_kms_crypto_key" "canary_authority"' in main
    assert 'name                          = "${var.resource_prefix}-canary-authority"' in main
    assert 'purpose                       = "ASYMMETRIC_SIGN"' in main
    assert "skip_initial_version_creation = true" in main
    assert "version_template" in main
    assert 'resource "google_kms_crypto_key_version" "canary_authority_v1"' in main
    assert 'algorithm        = "RSA_SIGN_PSS_2048_SHA256"' in main
    assert 'role          = "roles/cloudkms.signer"' in main
    assert (
        'member        = "serviceAccount:${google_service_account.identity['
        '\"authority_signer\"].email}"'
    ) in main
    signer_bindings = [
        line.strip()
        for line in main.splitlines()
        if 'roles/cloudkms.signer"' in line
    ]
    assert signer_bindings == ['role          = "roles/cloudkms.signer"']
    assert "roles/cloudkms.signerVerifier" not in main


def test_canary_provider_identities_are_isolated_from_operator() -> None:
    external = (
        ROOT / "infra/gcp/quebec/external_identity_and_secrets.tf"
    ).read_text(encoding="utf-8")
    main = (ROOT / "infra/gcp/quebec/main.tf").read_text(encoding="utf-8")
    assert 'account_id   = "${var.resource_prefix}-can-gem"' in main
    assert 'account_id   = "${var.resource_prefix}-can-oai"' in main
    assert 'account_id   = "${var.resource_prefix}-signer"' in main
    assert 'resource "google_project_iam_member" "operator_vertex"' not in main
    assert 'resource "google_project_iam_member" "canary_gemini_vertex"' in main
    assert 'role    = "roles/aiplatform.user"' not in main
    assert 'permissions = ["aiplatform.endpoints.predict"]' in main
    assert 'google_service_account.identity["canary_gemini"].email' in main
    assert 'service_account = "canary_openai"' in external
    assert 'resource "google_project_iam_member" "canary_sql_client"' in main
    assert 'role    = "roles/cloudsql.client"' in main
    runtime_logging = main.split(
        'resource "google_project_iam_member" "runtime_logging"', 1
    )[1].split('resource "google_project_iam_member" "runtime_metrics"', 1)[0]
    assert 'canary_gemini = google_service_account.identity["canary_gemini"].email' in runtime_logging
    assert 'canary_openai = google_service_account.identity["canary_openai"].email' in runtime_logging
    operator_scope = external.split(
        "operator_secret_purposes = toset([", 1
    )[1].split("])" , 1)[0]
    assert '"openai_api_key"' not in operator_scope
    assert '"runtime_admin_token"' not in operator_scope
    assert '"runtime_admin_binding_key"' not in operator_scope
    assert 'purpose         = "openai_api_key"' in external
    assert 'service_account = "canary_openai"' in external
    assert 'resource "google_service_account_iam_member" "deployer_uses_canary_gemini"' not in main
    assert 'resource "google_service_account_iam_member" "deployer_uses_canary_openai"' not in main
    assert 'service_account_id = google_service_account.identity["canary_gemini"].name' not in main
    assert 'service_account_id = google_service_account.identity["canary_openai"].name' not in main


def test_release_workflow_is_manual_environment_gated_and_non_mutating() -> None:
    workflow = (ROOT / ".github/workflows/aigc-release-staging.yml").read_text(
        encoding="utf-8"
    )
    assert "workflow_dispatch:" in workflow
    assert "environment: aigc-nexus-staging" in workflow
    assert "id-token: write" in workflow
    assert "gcloud " not in workflow
    assert "terraform apply" not in workflow
    assert "run deploy" not in workflow
