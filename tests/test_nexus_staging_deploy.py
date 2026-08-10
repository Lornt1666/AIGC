from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
import pytest

import scripts.deploy_nexus_staging as deployer


RELEASE = "a" * 40
TREE = "b" * 40
DIGEST = "sha256:" + "c" * 64
AUTHORIZATION_DIGEST = "d" * 64
CONTEXT_DIGEST = "e" * 64
MIGRATION_003_DIGEST = "f" * 64
MIGRATION_004_DIGEST = "1" * 64
MIGRATION_BUNDLE_DIGEST = "2" * 64
PROJECT = "aigc-stage"
BUILD_ACCOUNT = f"aigc-build@{PROJECT}.iam.gserviceaccount.com"
DEPLOYER_ACCOUNT = f"aigc-deployer@{PROJECT}.iam.gserviceaccount.com"
OPERATOR_ACCOUNT = f"aigc-operator@{PROJECT}.iam.gserviceaccount.com"
JUDGE_ACCOUNT = f"aigc-judge@{PROJECT}.iam.gserviceaccount.com"
SECRET_REF = (
    f"projects/{PROJECT}/locations/{deployer.REGION}/"
    "secrets/runtime-control-dsn/versions/7"
)
DOCKER_BUILDER_IMAGE = "gcr.io/cloud-builders/docker@sha256:" + "3" * 64
PYTHON_BASE_IMAGE = "python:3.12.13-slim-bookworm@sha256:" + "4" * 64
SBOM_GENERATOR_IMAGE = "anchore/syft@sha256:" + "5" * 64
EVIDENCE_BUCKET = f"{PROJECT}-aigc-evidence"
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY_PEM = PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("ascii")
PUBLIC_KEY_SHA256 = deployer.authority_public_key_sha256(PUBLIC_KEY_PEM)
KMS_KEY_VERSION = (
    f"projects/{PROJECT}/locations/{deployer.REGION}/keyRings/aigc-keys/"
    "cryptoKeys/aigc-canary-authority/cryptoKeyVersions/1"
)


def payload() -> dict:
    return {
        "project_id": PROJECT,
        "project_number": "170151535592",
        "release_sha": RELEASE,
        "release_tree_sha": TREE,
        "resource_manifest_sha256": "9" * 64,
        "ci_admission_sha256": deployer._canonical_sha256(ci_admission()),
        "resources": {
            "artifact_registry_repository": "aigc-runtime",
            "operator_service": "aigc-nexus-operator",
            "judge_service": "aigc-nexus-judge",
            "cloud_sql_instance": "aigc-control",
            "build_source_bucket": "aigc-build-source-nane1",
            "evidence_bucket": EVIDENCE_BUCKET,
            "receipt_bucket": f"{PROJECT}-aigc-receipts",
        },
        "service_accounts": {
            "deployer": DEPLOYER_ACCOUNT,
            "operator": OPERATOR_ACCOUNT,
            "canary_gemini": f"aigc-can-gem@{PROJECT}.iam.gserviceaccount.com",
            "canary_openai": f"aigc-can-oai@{PROJECT}.iam.gserviceaccount.com",
            "judge": JUDGE_ACCOUNT,
            "cloud_build": BUILD_ACCOUNT,
            "security_review": f"aigc-security@{PROJECT}.iam.gserviceaccount.com",
            "authority_signer": f"aigc-signer@{PROJECT}.iam.gserviceaccount.com",
        },
        "exact_secret_version_refs": {"runtime_control_dsn": SECRET_REF},
        "supply_chain": {
            "docker_builder_image": DOCKER_BUILDER_IMAGE,
            "python_base_image": PYTHON_BASE_IMAGE,
            "sbom_generator_image": SBOM_GENERATOR_IMAGE,
        },
    }


def ci_admission() -> dict:
    run_id = 31264978346
    stages = []
    for stage_id in deployer._EXPECTED_CI_STAGES:
        record = {
            "stage_id": stage_id,
            "target_sha": RELEASE,
            "tested_tree_sha": TREE,
            "run_id": run_id,
            "status": "success",
        }
        record["record_sha256"] = deployer._canonical_sha256(record)
        stages.append(record)
    exact_head = {
        "schema_version": "aigc.exact-head-admission-receipt.v2",
        "repository": deployer.REPOSITORY,
        "pr_number": 181,
        "workflow_event": "push",
        "requested_head_sha": RELEASE,
        "observed_head_sha": RELEASE,
        "tested_tree_sha": TREE,
        "base_sha": "3" * 40,
        "workflow_revision": RELEASE,
        "workflow_run_number": 912,
        "workflow_run_id": run_id,
        "workflow_run_attempt": 1,
        "artifact_name": f"aigc-colosseum-orchestration-exact-head-{RELEASE}",
        "job_status": "success",
        "canonical_contract_sha256": "4" * 64,
        "expected_stage_ids": list(deployer._EXPECTED_CI_STAGES),
        "successful_stage_ids": list(deployer._EXPECTED_CI_STAGES),
        "all_canonical_stages_success": True,
        "stage_receipts": {
            record["stage_id"]: {
                "present": True,
                "status": "success",
                "receipt_sha256": hashlib.sha256(
                    record["stage_id"].encode("utf-8")
                ).hexdigest(),
                "record_sha256": record["record_sha256"],
            }
            for record in stages
        },
        "toolchain": {
            "runner": "ubuntu-24.04",
            "python": "3.12.13",
            "terraform": "1.10.5",
            "postgres_service_image": (
                "postgres:16.14-alpine3.24@sha256:"
                "57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777"
            ),
        },
        "quebec_provider_lockfile_committed": True,
        "quebec_provider_lockfile_sha256": "5" * 64,
        "captured_timestamp": "2026-08-10T00:00:00+00:00",
        "external_authority_granted": False,
        "external_action_performed": False,
        "merge_authority_granted": False,
        "deployment_authority_granted": False,
        "live_model_call_authority_granted": False,
        "financial_authority_granted": False,
    }
    exact_head["receipt_sha256"] = deployer._canonical_sha256(exact_head)
    container = {
        "schema_version": "aigc.nexus-local-container-build.v2",
        "repository_revision": RELEASE,
        "tested_tree_sha": TREE,
        "image_id": "sha256:" + "7" * 64,
        "image_config_user": "aigc",
        "image_identity_labels": {
            "org.opencontainers.image.revision": RELEASE,
            "ai.aigc.source-context-sha256": "8" * 64,
        },
        "source_context_sha256": "8" * 64,
        "source_context_receipt_sha256": "9" * 64,
        "dependency_lock_sha256": "a" * 64,
        "python_base_image": PYTHON_BASE_IMAGE,
        "dockerfile_sha256": "b" * 64,
        "dockerfile": "Dockerfile.nexus",
        "runtime_smoke": {
            "health_contract_passed": True,
            "health_response_sha256": "c" * 64,
            "non_root": True,
            "runtime_uid": 10001,
            "read_only_root_filesystem": True,
            "network_mode": "none",
            "capabilities_dropped": ["ALL"],
            "no_new_privileges": True,
            "live_provider_execution_enabled": False,
            "production_activation": False,
            "live_model_call_performed": False,
        },
        "release_base_image_status": "immutable_default_verified",
        "registry_push_performed": False,
        "cloud_build_performed": False,
        "deployment_performed": False,
        "external_action_performed": False,
        "captured_at": "2026-08-10T00:00:00+00:00",
    }
    container["receipt_sha256"] = deployer._canonical_sha256(container)
    return {
        "schema_version": "aigc.exact-head-ci-admission.v2",
        "workflow_run": {
            "id": run_id,
            "repository": deployer.REPOSITORY,
            "workflow_path": ".github/workflows/aigc-ci.yml",
            "status": "completed",
            "conclusion": "success",
            "head_sha": RELEASE,
            "event": "push",
            "head_branch": "main",
            "head_repository_full_name": deployer.REPOSITORY,
            "protected_branch_verified": True,
            "html_url": f"https://github.com/{deployer.REPOSITORY}/actions/runs/{run_id}",
        },
        "artifact": {
            "id": 9023893562,
            "name": f"aigc-colosseum-orchestration-exact-head-{RELEASE}",
            "digest": "sha256:" + "6" * 64,
            "expired": False,
        },
        "exact_head_receipt": exact_head,
        "stage_records": stages,
        "container_build": container,
    }


def kms_public_key() -> deployer.KmsAuthorityPublicKey:
    return deployer.KmsAuthorityPublicKey(
        kms_key_version=KMS_KEY_VERSION,
        algorithm=deployer.CANARY_AUTHORITY_ALGORITHM,
        public_key_pem=PUBLIC_KEY_PEM,
        public_key_sha256=PUBLIC_KEY_SHA256,
    )


def action_permit(
    plan: dict,
    *,
    predecessor: dict | None = None,
    now: datetime | None = None,
    activation_offset: timedelta = timedelta(seconds=-30),
    active_window: timedelta = timedelta(minutes=5),
    permit_kind: str = "execute",
    reconciliation: dict | None = None,
) -> dict:
    authoritative_now = now or datetime.now(timezone.utc)
    index = 0 if predecessor is None else predecessor["checkpoint"]["action_index"] + 1
    action = plan["actions"][index]
    value = payload()
    not_before = authoritative_now + activation_offset
    permit = {
        "schema_version": deployer.ACTION_PERMIT_SCHEMA,
        "permit_id": f"ACT-{permit_kind.upper()}{index:04d}",
        "nonce": hashlib.sha256(
            f"permit-{permit_kind}-{index}-{authoritative_now.isoformat()}".encode()
        ).hexdigest(),
        "permit_kind": permit_kind,
        "repository": deployer.REPOSITORY,
        "project_id": PROJECT,
        "project_number": value["project_number"],
        "region": deployer.REGION,
        "release_sha": RELEASE,
        "release_tree_sha": TREE,
        "resource_manifest_sha256": value["resource_manifest_sha256"],
        "ci_admission_sha256": value["ci_admission_sha256"],
        "authorization_sha256": deployer._authorization_hash(value),
        "plan_sha256": deployer._canonical_sha256(plan),
        "action_index": index,
        "action_name": action["action"],
        "target": deployer._expected_action_target(
            action_index=index,
            plan=plan,
            predecessor=predecessor,
        ),
        "target_rule": deployer._ACTION_TARGET_RULES[index],
        "predecessor": (
            None
            if predecessor is None
            else deployer._checkpoint_predecessor_binding(predecessor)
        ),
        "reconciliation": reconciliation,
        "receipt_bucket": value["resources"]["receipt_bucket"],
        "maximum_target_mutations": 1 if permit_kind == "execute" else 0,
        "automatic_retry": False,
        "consumption_mode": "gcs_if_generation_match_zero",
        "public_traffic": False,
        "live_model_call": False,
        "production_activation": False,
        "signer_principal": value["service_accounts"]["authority_signer"],
        "executor_principal": value["service_accounts"]["deployer"],
        "kms_key_version": KMS_KEY_VERSION,
        "signing_algorithm": deployer.CANARY_AUTHORITY_ALGORITHM,
        "public_key_sha256": PUBLIC_KEY_SHA256,
        "issued_at": (authoritative_now - timedelta(minutes=1)).isoformat(),
        "not_before": not_before.isoformat(),
        "expires_at": (not_before + active_window).isoformat(),
    }
    digest = hashlib.sha256(deployer._canonical_json_bytes(permit)).digest()
    signature = PRIVATE_KEY.sign(
        digest,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
        utils.Prehashed(hashes.SHA256()),
    )
    permit["signature_b64"] = base64.b64encode(signature).decode("ascii")
    return permit


def summary() -> dict:
    value = payload()
    return {
        "project_id": PROJECT,
        "region": deployer.REGION,
        "release_sha": RELEASE,
        "release_tree_sha": TREE,
        "authorized_scope": {
            "project_id": PROJECT,
            "project_number": value["project_number"],
            "resource_prefix": "aigc",
            "resources": value["resources"],
            "service_accounts": value["service_accounts"],
            "exact_secret_version_refs": value["exact_secret_version_refs"],
            "supply_chain": value["supply_chain"],
            "ci_admission_sha256": value["ci_admission_sha256"],
        },
    }


def migration_receipt() -> dict:
    return {
        "schema_version": "aigc.nexus-runtime-control-migration-receipt.v2",
        "migrations": [
            {
                "name": "003_nexus_provider_runtime_controls.sql",
                "sha256": MIGRATION_003_DIGEST,
            },
            {
                "name": "004_nexus_persisted_authority.sql",
                "sha256": MIGRATION_004_DIGEST,
            },
        ],
        "migration_bundle_sha256": MIGRATION_BUNDLE_DIGEST,
        "runtime_control_singleton_verified": True,
        "persisted_authority_table_verified": True,
        "secret_value_emitted": False,
        "provider_call_performed": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def build_checkpoint_envelope(plan: dict) -> dict:
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/"
        f"aigc-nexus@{DIGEST}"
    )
    permit_sha256 = "a" * 64
    permit_id = "ACT-EXECUTE0000"
    action = {
        "action": "cloud_build_submit",
        "target": plan["build_tag"],
        "mutation_count": 1,
        "automatic_retry": False,
        "status": "succeeded",
        "evidence": {
            "build_id": "build-123",
            "tagged_image_uri": plan["build_tag"],
            "image_digest": DIGEST,
            "source_bucket": "aigc-build-source-nane1",
            "service_account": BUILD_ACCOUNT,
            "docker_builder_image": DOCKER_BUILDER_IMAGE,
            "python_base_image": PYTHON_BASE_IMAGE,
            "build_context_manifest_sha256": CONTEXT_DIGEST,
            "immutable_image_uri": immutable,
            "action_permit_id": permit_id,
            "action_permit_sha256": permit_sha256,
            "predecessor_permit_sha256": "0" * 64,
            "permit_consumption_uri": (
                f"gs://{PROJECT}-aigc-receipts/staging-action-permits/{RELEASE}/"
                f"00-{permit_id}.json"
            ),
            "permit_consumption_generation": "7",
            "permit_consumption_record_sha256": "b" * 64,
        },
    }
    checkpoint = {
        "schema_version": deployer.ACTION_CHECKPOINT_SCHEMA,
        "repository": deployer.REPOSITORY,
        "project_id": PROJECT,
        "project_number": payload()["project_number"],
        "region": deployer.REGION,
        "release_sha": RELEASE,
        "release_tree_sha": TREE,
        "resource_manifest_sha256": payload()["resource_manifest_sha256"],
        "ci_admission_sha256": payload()["ci_admission_sha256"],
        "authorization_sha256": deployer._authorization_hash(payload()),
        "plan_sha256": deployer._canonical_sha256(plan),
        "action_index": 0,
        "action_name": "cloud_build_submit",
        "permit_kind": "execute",
        "permit_sha256": permit_sha256,
        "predecessor_checkpoint_sha256": None,
        "completed_actions": [action],
        "release_state": {
            "ci_evidence": {
                "workflow_run_id": "31264978346",
                "workflow_run_url": (
                    "https://github.com/Lornt1666/AIGC/actions/runs/31264978346"
                ),
                "artifact_id": "9023893562",
                "artifact_digest": "sha256:" + "6" * 64,
                "ci_admission_sha256": payload()["ci_admission_sha256"],
                "stage_count": 15,
                "container_receipt_sha256": "7" * 64,
            },
            "foundation": {
                "artifact_repository_sha256": "1" * 64,
                "cloud_sql_sha256": "2" * 64,
                "network_sha256": "3" * 64,
                "subnet_sha256": "4" * 64,
                "service_account_metadata_sha256": {
                    account: hashlib.sha256(account.encode()).hexdigest()
                    for account in payload()["service_accounts"].values()
                },
                "cloud_sql_connection_name": (
                    f"{PROJECT}:{deployer.REGION}:aigc-control"
                ),
                "region": deployer.REGION,
                "action_permission_preflight_sha256": "5" * 64,
            },
            "build_id": "build-123",
            "build_context_manifest_sha256": CONTEXT_DIGEST,
            "build_substitutions": {
                "_IMAGE_URI": plan["build_tag"],
                "_DOCKER_BUILDER_IMAGE": DOCKER_BUILDER_IMAGE,
                "_PYTHON_BASE_IMAGE": PYTHON_BASE_IMAGE,
                "_RELEASE_SHA": RELEASE,
                "_SOURCE_CONTEXT_SHA256": CONTEXT_DIGEST,
            },
            "image_digest": DIGEST,
            "immutable_image_uri": immutable,
        },
        "status": "succeeded",
        "reconciliation_required": False,
        "reconciliation_authority": None,
        "terminal_deployment_receipt": None,
        "terminal_deployment_receipt_sha256": None,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    checkpoint["checkpoint_sha256"] = deployer._canonical_sha256(checkpoint)
    content = deployer._canonical_json_bytes(checkpoint)
    return {
        "schema_version": deployer.ACTION_CHECKPOINT_ENVELOPE_SCHEMA,
        "checkpoint": checkpoint,
        "checkpoint_object_uri": (
            f"gs://{PROJECT}-aigc-receipts/staging-action-checkpoints/{RELEASE}/"
            f"00-{checkpoint['checkpoint_sha256']}.json"
        ),
        "checkpoint_object_generation": "8",
        "checkpoint_object_sha256": hashlib.sha256(content).hexdigest(),
    }


def rehash_checkpoint_envelope(envelope: dict) -> None:
    checkpoint = envelope["checkpoint"]
    checkpoint.pop("checkpoint_sha256", None)
    checkpoint["checkpoint_sha256"] = deployer._canonical_sha256(checkpoint)
    content = deployer._canonical_json_bytes(checkpoint)
    envelope["checkpoint_object_uri"] = (
        f"gs://{PROJECT}-aigc-receipts/staging-action-checkpoints/{RELEASE}/"
        f"{checkpoint['action_index']:02d}-{checkpoint['checkpoint_sha256']}.json"
    )
    envelope["checkpoint_object_sha256"] = hashlib.sha256(content).hexdigest()


def test_build_plan_declares_ordered_single_mutations_and_provider_free_judge(monkeypatch):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    plan = deployer.build_plan(payload(), {})
    assert plan["schema_version"] == deployer.PLAN_SCHEMA
    assert plan["deployment_image_form"].endswith("@sha256:<registry-resolved>")
    assert plan["build_source_bucket"] == "aigc-build-source-nane1"
    assert plan["sbom_bucket"] == EVIDENCE_BUCKET
    assert plan["migration_before_service_deploy"] is True
    assert plan["public_traffic"] is False
    assert plan["live_model_call"] is False
    assert [item["action"] for item in plan["actions"]] == list(deployer._ACTION_NAMES)
    assert all(item["mutation_count"] == 1 for item in plan["actions"])
    assert all(item["automatic_retry"] is False for item in plan["actions"])
    assert plan["actions"][1]["action"] == "sbom_export"
    assert plan["actions"][1]["prerequisites"] == ["cloud_build_submit"]
    assert plan["actions"][4]["prerequisites"] == ["migration_execute"]
    assert plan["actions"][5]["prerequisites"] == ["operator_deploy"]
    assert plan["action_authorization"]["execution_mode"] == "one_action_per_invocation"
    assert plan["action_authorization"]["fresh_permit_count_per_invocation"] == 1
    assert plan["action_authorization"]["total_ordered_actions"] == 6
    assert plan["action_authorization"]["monolithic_execution_enabled"] is False
    assert plan["action_authorization"]["reconciliation_permit_required_after_indeterminate_mutation"] is True
    assert plan["action_authorization"]["required_deployer_permissions"] == {
        "receipt_bucket": ["storage.objects.create"],
        "sbom_bucket": list(deployer._SBOM_BUCKET_PERMISSIONS),
        "sbom_metadata_project": list(deployer._SBOM_LOAD_PROJECT_PERMISSIONS),
        "image_pull_repository": list(deployer._IMAGE_PULL_REPOSITORY_PERMISSIONS),
    }


def test_sbom_permission_preflight_is_exact_resource_scoped(monkeypatch):
    monkeypatch.setattr(
        deployer,
        "_run",
        lambda command, **_kwargs: DEPLOYER_ACCOUNT
        if command == ["gcloud", "config", "get-value", "account"]
        else (_ for _ in ()).throw(AssertionError(command)),
    )
    observed: list[tuple[str, tuple[str, ...]]] = []

    def grant_exact(*, url, permissions, expected_principal):
        assert expected_principal == DEPLOYER_ACCOUNT
        observed.append((url, tuple(permissions)))
        return 200, {"permissions": list(permissions)}

    monkeypatch.setattr(deployer, "_authorized_test_iam_permissions", grant_exact)
    evidence = deployer._preflight_deployer_action_permissions(
        project=PROJECT,
        receipt_bucket=f"{PROJECT}-aigc-receipts",
        sbom_bucket=EVIDENCE_BUCKET,
        artifact_repository="aigc-runtime",
        deployer_service_account=DEPLOYER_ACCOUNT,
    )
    assert set(evidence) == {
        "receipt_bucket",
        "sbom_bucket",
        "sbom_metadata_project",
        "image_pull_repository",
    }
    assert observed[0][0].endswith(
        f"/b/{PROJECT}-aigc-receipts/iam/testPermissions"
    )
    assert observed[1][0].endswith(f"/b/{EVIDENCE_BUCKET}/iam/testPermissions")
    assert observed[2][0].endswith(f"/projects/{PROJECT}:testIamPermissions")
    assert observed[3][0].endswith(
        f"/projects/{PROJECT}/locations/{deployer.REGION}/repositories/"
        "aigc-runtime:testIamPermissions"
    )
    assert observed[1][1] == deployer._SBOM_BUCKET_PERMISSIONS
    assert observed[2][1] == deployer._SBOM_LOAD_PROJECT_PERMISSIONS
    assert observed[3][1] == deployer._IMAGE_PULL_REPOSITORY_PERMISSIONS


def test_sbom_permission_preflight_fails_if_one_exact_permission_is_missing(monkeypatch):
    monkeypatch.setattr(deployer, "_run", lambda *_args, **_kwargs: DEPLOYER_ACCOUNT)

    def omit_one(*, permissions, **_kwargs):
        return 200, {"permissions": list(permissions)[1:]}

    monkeypatch.setattr(deployer, "_authorized_test_iam_permissions", omit_one)
    with pytest.raises(deployer.NexusStagingDeploymentError, match="lacks the exact"):
        deployer._preflight_deployer_action_permissions(
            project=PROJECT,
            receipt_bucket=f"{PROJECT}-aigc-receipts",
            sbom_bucket=EVIDENCE_BUCKET,
            artifact_repository="aigc-runtime",
            deployer_service_account=DEPLOYER_ACCOUNT,
        )


def test_action_permit_is_one_active_kms_signed_jit_mutation(monkeypatch):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    monkeypatch.setattr(deployer, "fetch_kms_authority_public_key", lambda _key: kms_public_key())
    plan = deployer.build_plan(payload(), {})
    validated = deployer.validate_action_permit(
        action_permit(plan),
        payload=payload(),
        summary=summary(),
        plan=plan,
        predecessor=None,
    )
    assert validated["action_index"] == 0
    assert validated["action_name"] == "cloud_build_submit"
    assert validated["permit_kind"] == "execute"
    assert validated["maximum_target_mutations"] == 1
    assert validated["automatic_retry"] is False
    assert validated["predecessor"] is None
    assert deployer._SHA256.fullmatch(validated["permit_sha256"])


def test_six_permit_monolithic_validator_is_disabled(monkeypatch):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    plan = deployer.build_plan(payload(), {})
    with pytest.raises(
        deployer.NexusStagingDeploymentError,
        match="six-permit monolithic execution is disabled",
    ):
        deployer.validate_action_permits(
            [action_permit(plan)] * 6,
            payload=payload(),
            summary=summary(),
            plan=plan,
        )


@pytest.mark.parametrize(
    ("activation_offset", "active_window"),
    [
        (timedelta(minutes=1), timedelta(minutes=5)),
        (timedelta(minutes=-6), timedelta(minutes=5)),
    ],
)
def test_jit_action_permit_must_be_active_at_this_invocation(
    monkeypatch,
    activation_offset,
    active_window,
):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    monkeypatch.setattr(deployer, "fetch_kms_authority_public_key", lambda _key: kms_public_key())
    plan = deployer.build_plan(payload(), {})
    with pytest.raises(deployer.NexusStagingDeploymentError, match="not active"):
        deployer.validate_action_permit(
            action_permit(
                plan,
                now=now,
                activation_offset=activation_offset,
                active_window=active_window,
            ),
            payload=payload(),
            summary=summary(),
            plan=plan,
            predecessor=None,
            authoritative_now=now,
        )


def test_action_permit_active_window_cannot_exceed_fifteen_minutes(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    plan = deployer.build_plan(payload(), {})
    with pytest.raises(
        deployer.NexusStagingDeploymentError,
        match="active window exceeds 15 minutes",
    ):
        deployer.validate_action_permit(
            action_permit(
                plan,
                now=now,
                active_window=timedelta(minutes=15, seconds=1),
            ),
            payload=payload(),
            summary=summary(),
            plan=plan,
            predecessor=None,
            authoritative_now=now,
        )


def test_dormant_old_permit_cannot_be_reactivated_as_jit(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    monkeypatch.setattr(deployer, "fetch_kms_authority_public_key", lambda _key: kms_public_key())
    plan = deployer.build_plan(payload(), {})
    permit = action_permit(plan, now=now)
    permit["issued_at"] = (now - timedelta(days=30)).isoformat()
    permit.pop("signature_b64")
    digest = hashlib.sha256(deployer._canonical_json_bytes(permit)).digest()
    permit["signature_b64"] = base64.b64encode(
        PRIVATE_KEY.sign(
            digest,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            utils.Prehashed(hashes.SHA256()),
        )
    ).decode("ascii")
    with pytest.raises(deployer.NexusStagingDeploymentError, match="freshly issued"):
        deployer.validate_action_permit(
            permit,
            payload=payload(),
            summary=summary(),
            plan=plan,
            predecessor=None,
            authoritative_now=now,
        )


def test_dispatch_waits_only_until_signed_activation_window():
    now = datetime.now(timezone.utc)
    observed = [now]
    slept: list[float] = []
    permit = {
        "not_before": (now + timedelta(seconds=2.5)).isoformat(),
        "expires_at": (now + timedelta(minutes=1)).isoformat(),
    }

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        observed[0] += timedelta(seconds=seconds)

    deployer._wait_for_action_permit_window(
        permit,
        now_fn=lambda: observed[0],
        sleep_fn=sleep,
    )
    assert sum(slept) == pytest.approx(2.5)
    assert all(0 < seconds <= deployer._ACTION_PERMIT_WAIT_POLL_SECONDS for seconds in slept)


@pytest.mark.parametrize("tamper", ["target", "signature", "predecessor", "expired"])
def test_action_permit_tampering_fails_before_consumption(monkeypatch, tamper):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    monkeypatch.setattr(deployer, "fetch_kms_authority_public_key", lambda _key: kms_public_key())
    plan = deployer.build_plan(payload(), {})
    permit = action_permit(plan)
    if tamper == "target":
        permit["target"] += "-attacker"
    elif tamper == "signature":
        signature = bytearray(base64.b64decode(permit["signature_b64"]))
        signature[0] ^= 1
        permit["signature_b64"] = base64.b64encode(signature).decode("ascii")
    elif tamper == "predecessor":
        permit["predecessor"] = {
            "action_index": 0,
            "action_name": "cloud_build_submit",
        }
    else:
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        permit = action_permit(plan, now=past)
    with pytest.raises(deployer.NexusStagingDeploymentError):
        deployer.validate_action_permit(
            permit,
            payload=payload(),
            summary=summary(),
            plan=plan,
            predecessor=None,
        )


def test_action_permit_replay_blocks_target_dispatch(monkeypatch):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    monkeypatch.setattr(deployer, "fetch_kms_authority_public_key", lambda _key: kms_public_key())
    plan = deployer.build_plan(payload(), {})
    permit = deployer.validate_action_permit(
        action_permit(plan),
        payload=payload(),
        summary=summary(),
        plan=plan,
        predecessor=None,
    )
    monkeypatch.setattr(
        deployer,
        "_authorized_storage_create_only",
        lambda **_kwargs: (412, {"error": {"message": "conditionNotMet"}}),
    )
    with pytest.raises(deployer.NexusStagingPermitAlreadyConsumed, match="already consumed"):
        deployer._consume_action_permit(permit)


def test_sbom_target_resolves_only_the_verified_predecessor_image(monkeypatch):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    plan = deployer.build_plan(payload(), {})
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/"
        f"aigc-nexus@{DIGEST}"
    )
    predecessor = {
        "checkpoint": {
            "action_index": 0,
            "release_state": {"immutable_image_uri": immutable},
        }
    }
    assert deployer._expected_action_target(
        action_index=1,
        plan=plan,
        predecessor=predecessor,
    ) == immutable
    predecessor["checkpoint"]["release_state"]["immutable_image_uri"] = (
        immutable.replace(DIGEST, "sha256:" + "f" * 64).replace("aigc-nexus", "other")
    )
    with pytest.raises(
        deployer.NexusStagingDeploymentError,
        match="exact predecessor image digest",
    ):
        deployer._expected_action_target(
            action_index=1,
            plan=plan,
            predecessor=predecessor,
        )


def test_action_permit_is_rechecked_for_expiry_at_dispatch(monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    monkeypatch.setattr(deployer, "fetch_kms_authority_public_key", lambda _key: kms_public_key())
    plan = deployer.build_plan(payload(), {})
    permit = deployer.validate_action_permit(
        action_permit(plan, now=now),
        payload=payload(),
        summary=summary(),
        plan=plan,
        predecessor=None,
        authoritative_now=now,
    )
    called = False

    def should_not_consume(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("expired permit must not be consumed or dispatched")

    monkeypatch.setattr(deployer, "_authorized_storage_create_only", should_not_consume)
    with pytest.raises(deployer.NexusStagingDeploymentError, match="expired before dispatch"):
        deployer._consume_action_permit(
            permit,
            authoritative_now=now + timedelta(minutes=6),
        )
    assert called is False


@pytest.mark.parametrize(
    "tamper",
    ["extra_secret", "nested_foundation_secret", "inconsistent_digest"],
)
def test_checkpoint_rejects_extra_or_inconsistent_cumulative_state(monkeypatch, tamper):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    plan = deployer.build_plan(payload(), {})
    envelope = build_checkpoint_envelope(plan)
    if tamper == "extra_secret":
        envelope["checkpoint"]["release_state"]["raw_secret"] = "must-not-propagate"
    elif tamper == "nested_foundation_secret":
        envelope["checkpoint"]["release_state"]["foundation"]["raw_secret"] = (
            "must-not-propagate"
        )
    else:
        envelope["checkpoint"]["release_state"]["image_digest"] = (
            "sha256:" + "f" * 64
        )
    rehash_checkpoint_envelope(envelope)
    with pytest.raises(deployer.NexusStagingDeploymentError):
        deployer._validated_checkpoint(
            envelope,
            payload=payload(),
            summary=summary(),
            plan=plan,
            verify_remote=False,
        )


def test_reconciliation_permit_binds_original_predecessor_chain(monkeypatch):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    monkeypatch.setattr(deployer, "fetch_kms_authority_public_key", lambda _key: kms_public_key())
    plan = deployer.build_plan(payload(), {})
    hint = {
        "action_index": 0,
        "action_name": "cloud_build_submit",
        "build_id": "build-123",
    }
    original_id = "ACT-ORIGINAL0000"
    reconciliation = {
        "original_permit_id": original_id,
        "original_permit_sha256": "1" * 64,
        "original_predecessor_action_permit_sha256": "f" * 64,
        "original_consumption_uri": (
            f"gs://{PROJECT}-aigc-receipts/staging-action-permits/{RELEASE}/"
            f"00-{original_id}.json"
        ),
        "original_consumption_generation": "9",
        "original_consumption_record_sha256": "2" * 64,
        "readback_hint_sha256": deployer._canonical_sha256(hint),
        "reason": "indeterminate_target_mutation",
    }
    permit = action_permit(
        plan,
        permit_kind="reconcile",
        reconciliation=reconciliation,
    )
    with pytest.raises(
        deployer.NexusStagingDeploymentError,
        match="exact original predecessor",
    ):
        deployer.validate_action_permit(
            permit,
            payload=payload(),
            summary=summary(),
            plan=plan,
            predecessor=None,
            reconciliation_hint=hint,
        )


def test_reconciliation_reads_back_without_dispatching_target_mutation(monkeypatch):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    plan = deployer.build_plan(payload(), {})
    hint = {
        "action_index": 0,
        "action_name": "cloud_build_submit",
        "build_id": "build-123",
    }
    permit = {
        "action_index": 0,
        "action_name": "cloud_build_submit",
        "target": plan["build_tag"],
        "permit_kind": "reconcile",
        "executor_principal": DEPLOYER_ACCOUNT,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    }
    fresh_authority = {
        "action_permit_id": "ACT-RECONCILE0000",
        "action_permit_sha256": "3" * 64,
        "predecessor_permit_sha256": "0" * 64,
        "permit_consumption_uri": (
            f"gs://{PROJECT}-aigc-receipts/staging-action-permits/{RELEASE}/"
            "00-ACT-RECONCILE0000.json"
        ),
        "permit_consumption_generation": "11",
        "permit_consumption_record_sha256": "4" * 64,
    }
    original_authority = {
        "action_permit_id": "ACT-ORIGINAL0000",
        "action_permit_sha256": "1" * 64,
        "predecessor_permit_sha256": "0" * 64,
        "permit_consumption_uri": (
            f"gs://{PROJECT}-aigc-receipts/staging-action-permits/{RELEASE}/"
            "00-ACT-ORIGINAL0000.json"
        ),
        "permit_consumption_generation": "9",
        "permit_consumption_record_sha256": "2" * 64,
    }
    monkeypatch.setattr(deployer, "_preflight_deployer_action_permissions", lambda **_kwargs: {})
    monkeypatch.setattr(deployer, "_regional_bucket", lambda **_kwargs: {})
    monkeypatch.setattr(deployer, "_foundation_evidence", lambda **_kwargs: {"region": deployer.REGION})

    def prepare(**kwargs):
        kwargs["output_dir"].mkdir(parents=True)
        return {"manifest_sha256": CONTEXT_DIGEST}

    monkeypatch.setattr(deployer, "prepare_build_context", prepare)
    monkeypatch.setattr(deployer, "_consume_action_permit", lambda *_args, **_kwargs: fresh_authority)
    monkeypatch.setattr(deployer, "_verify_original_consumption", lambda *_args, **_kwargs: original_authority)
    monkeypatch.setattr(
        deployer,
        "_build_evidence",
        lambda **_kwargs: {
            "build_id": "build-123",
            "tagged_image_uri": plan["build_tag"],
            "image_digest": DIGEST,
            "source_bucket": "aigc-build-source-nane1",
            "service_account": BUILD_ACCOUNT,
            "docker_builder_image": DOCKER_BUILDER_IMAGE,
            "python_base_image": PYTHON_BASE_IMAGE,
        },
    )
    monkeypatch.setattr(deployer, "_registry_digest", lambda **_kwargs: DIGEST)
    monkeypatch.setattr(
        deployer,
        "_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("reconciliation must not dispatch a target command")
        ),
    )
    actions, state, reconciliation_authority = deployer._execute_or_reconcile_action(
        permit=permit,
        predecessor=None,
        reconciliation_hint=hint,
        summary=summary(),
        plan=plan,
        payload=payload(),
        ci_evidence={"ci_admission_sha256": payload()["ci_admission_sha256"]},
    )
    assert actions[0]["evidence"]["action_permit_sha256"] == "1" * 64
    assert reconciliation_authority == fresh_authority
    assert state["build_id"] == "build-123"


def test_migration_job_clears_inherited_secret_and_volume_configuration(tmp_path):
    command = deployer._migration_job_command(
        project=PROJECT,
        job_name="aigc-migrate-aaaaaaaa",
        immutable_image=f"image@{DIGEST}",
        operator_service_account=OPERATOR_ACCOUNT,
        executor_service_account=DEPLOYER_ACCOUNT,
        cloud_sql=f"{PROJECT}:{deployer.REGION}:aigc-control",
        network="aigc-vpc",
        subnet="aigc-subnet",
        runtime_control_dsn_secret_ref=SECRET_REF,
        release_sha=RELEASE,
        env_path=tmp_path / "env.yaml",
    )
    assert "--clear-secrets" in command
    assert "--clear-volumes" in command
    assert command[command.index("--max-retries") + 1] == "0"


def test_migration_execution_rejects_inherited_secret_source(monkeypatch):
    described = {
        "name": f"projects/{PROJECT}/locations/{deployer.REGION}/jobs/job/executions/execution-1",
        "metadata": {
            "annotations": {
                "run.googleapis.com/cloudsql-instances": f"{PROJECT}:{deployer.REGION}:aigc-control",
                "run.googleapis.com/network-interfaces": json.dumps(
                    [{"network": "aigc-vpc", "subnetwork": "aigc-subnet"}]
                ),
            }
        },
        "template": {
            "serviceAccount": OPERATOR_ACCOUNT,
            "containers": [
                {
                    "image": f"image@{DIGEST}",
                    "env": [
                        {
                            "name": "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF",
                            "valueSource": {"secretKeyRef": {"secret": "attacker"}},
                        }
                    ],
                }
            ],
        },
    }
    monkeypatch.setattr(deployer, "_run", lambda *_args, **_kwargs: json.dumps(described))
    with pytest.raises(deployer.NexusStagingDeploymentError, match="secret/value source"):
        deployer._migration_execution_target(
            project=PROJECT,
            execution_name="execution-1",
            immutable_image=f"image@{DIGEST}",
            service_account=OPERATOR_ACCOUNT,
            runtime_control_dsn_secret_ref=SECRET_REF,
            cloud_sql=f"{PROJECT}:{deployer.REGION}:aigc-control",
            network="aigc-vpc",
            subnet="aigc-subnet",
        )


def test_ci_admission_v2_rejects_stale_flat_container_contract():
    admission = ci_admission()
    admission["container_build"] = {
        "repository_revision": RELEASE,
        "tested_tree_sha": TREE,
        "container_user": "aigc",
        "runtime_smoke_passed": True,
    }
    with pytest.raises(deployer.NexusStagingDeploymentError, match="local container"):
        deployer._validate_ci_admission(
            admission,
            release_sha=RELEASE,
            release_tree_sha=TREE,
            expected_sha256=deployer._canonical_sha256(admission),
            expected_python_base_image=PYTHON_BASE_IMAGE,
        )


def test_resumable_executor_runs_one_action_per_checkpoint_and_emits_terminal_receipt(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    monkeypatch.setattr(deployer, "_git_identity", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        deployer,
        "fetch_kms_authority_public_key",
        lambda key_version: kms_public_key()
        if key_version == KMS_KEY_VERSION
        else (_ for _ in ()).throw(AssertionError(key_version)),
    )
    consumed: list[tuple[str, str, dict]] = []
    uploaded: dict[tuple[str, str, str], bytes] = {}

    def fake_create_only(*, bucket, object_name, content, expected_principal):
        assert expected_principal == DEPLOYER_ACCOUNT
        record = json.loads(content)
        generation = str(1000 + len(uploaded) + 1)
        uploaded[(bucket, object_name, generation)] = content
        if record.get("schema_version") == (
            "aigc.nexus-staging-action-permit-consumption.v1"
        ):
            consumed.append((bucket, object_name, record))
        return 200, {
            "bucket": bucket,
            "name": object_name,
            "generation": generation,
        }

    monkeypatch.setattr(deployer, "_authorized_storage_create_only", fake_create_only)
    monkeypatch.setattr(
        deployer,
        "_authorized_storage_read_exact",
        lambda *, bucket, object_name, generation, **_kwargs: (
            200,
            uploaded[(bucket, object_name, generation)],
        ),
    )
    monkeypatch.setattr(
        deployer,
        "_preflight_deployer_action_permissions",
        lambda **_kwargs: {
            "receipt_bucket": {"permissions": ["storage.objects.create"]},
            "sbom_bucket": {
                "permissions": list(deployer._SBOM_BUCKET_PERMISSIONS)
            },
            "sbom_metadata_project": {
                "permissions": list(deployer._SBOM_LOAD_PROJECT_PERMISSIONS)
            },
            "image_pull_repository": {
                "permissions": list(deployer._IMAGE_PULL_REPOSITORY_PERMISSIONS)
            },
        },
    )
    contexts: list[dict] = []

    def fake_prepare(**kwargs):
        contexts.append(kwargs)
        kwargs["output_dir"].mkdir(parents=True)
        (kwargs["output_dir"] / "cloudbuild.nexus.yaml").write_text("steps: []\n", encoding="utf-8")
        return {"manifest_sha256": CONTEXT_DIGEST}

    monkeypatch.setattr(deployer, "prepare_build_context", fake_prepare)
    foundation = {
        "artifact_repository_sha256": "8" * 64,
        "cloud_sql_sha256": "9" * 64,
        "network_sha256": "a" * 64,
        "subnet_sha256": "b" * 64,
        "service_account_metadata_sha256": {
            account: hashlib.sha256(account.encode()).hexdigest()
            for account in payload()["service_accounts"].values()
        },
        "cloud_sql_connection_name": f"{PROJECT}:{deployer.REGION}:aigc-control",
        "region": deployer.REGION,
    }
    monkeypatch.setattr(deployer, "_foundation_evidence", lambda **_kwargs: foundation)
    sbom_local_metadata = {
        "sbom_generator_image": SBOM_GENERATOR_IMAGE,
        "sbom_source_image_uri": (
            f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/"
            f"aigc-nexus@{DIGEST}"
        ),
        "sbom_local_sha256": "0" * 64,
        "sbom_format": "SPDX-2.3",
        "sbom_package_count": 7,
        "sbom_document_namespace_sha256": "1" * 64,
    }

    def fake_generate_sbom(*, work_dir, **_kwargs):
        sbom_path = work_dir / "sbom.spdx.json"
        sbom_path.write_text("{}\n", encoding="utf-8")
        return sbom_path, dict(sbom_local_metadata)

    monkeypatch.setattr(deployer, "_generate_pinned_sbom", fake_generate_sbom)
    artifact_security = {
        "provenance_sha256": "5" * 64,
        "provenance_builder_id": deployer._CLOUD_BUILD_BUILDER_ID,
        "provenance_build_id": "build-123",
        **sbom_local_metadata,
        "sbom_reference_count": 1,
        "sbom_metadata_sha256": "6" * 64,
        "sbom_gcs_uri": f"gs://{EVIDENCE_BUCKET}/sboms/exact.spdx.json",
        "sbom_gcs_bucket": EVIDENCE_BUCKET,
        "sbom_gcs_location": deployer.REGION,
        "sbom_occurrence_name": (
            f"projects/{PROJECT}/locations/{deployer.REGION}/occurrences/sbom-1"
        ),
        "vulnerability_finding_count": 0,
        "release_blocking_vulnerability_count": 0,
        "vulnerability_metadata_sha256": "7" * 64,
        "vulnerability_scan_status": "FINISHED_SUCCESS",
        "vulnerability_scan_note": deployer._PACKAGE_VULNERABILITY_NOTE,
        "vulnerability_scan_occurrence_name": (
            f"projects/{PROJECT}/locations/{deployer.REGION}/occurrences/scan-1"
        ),
        "vulnerability_scan_metadata_sha256": "8" * 64,
    }
    monkeypatch.setattr(
        deployer,
        "_artifact_security_evidence",
        lambda **_kwargs: artifact_security,
    )
    expected_authorization = deployer._authorization_hash(payload())
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    tagged = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus:{RELEASE}"
    )
    commands: list[tuple[list[str], bool]] = []
    deployed_env: dict[str, dict[str, str]] = {}

    def fake_run(command, *, capture=False, mutating=False):
        command = list(command)
        commands.append((command, mutating))
        if mutating:
            assert len(consumed) == sum(
                1 for _command, is_mutating in commands if is_mutating
            )
        if command[:3] == ["gcloud", "builds", "submit"]:
            assert Path(command[3]).name == "context"
            assert command[3] != "."
            assert command[command.index("--gcs-source-staging-dir") + 1] == (
                f"gs://aigc-build-source-nane1/nexus/{RELEASE}"
            )
            substitutions = command[command.index("--substitutions") + 1]
            assert f"_DOCKER_BUILDER_IMAGE={DOCKER_BUILDER_IMAGE}" in substitutions
            assert f"_PYTHON_BASE_IMAGE={PYTHON_BASE_IMAGE}" in substitutions
            assert f"_SOURCE_CONTEXT_SHA256={CONTEXT_DIGEST}" in substitutions
            return "build-123"
        if command[:4] == ["gcloud", "artifacts", "sbom", "load"]:
            source_argument = next(item for item in command if item.startswith("--source="))
            assert Path(source_argument.split("=", 1)[1]).name == "sbom.spdx.json"
            assert f"--uri={immutable}" in command
            assert f"--destination=gs://{EVIDENCE_BUCKET}" in command
            assert f"--location={deployer.REGION}" in command
            return ""
        if command[:3] == ["gcloud", "builds", "describe"]:
            return json.dumps(
                {
                    "id": "build-123",
                    "status": "SUCCESS",
                    "serviceAccount": f"projects/{PROJECT}/serviceAccounts/{BUILD_ACCOUNT}",
                    "substitutions": {
                        "_IMAGE_URI": tagged,
                        "_DOCKER_BUILDER_IMAGE": DOCKER_BUILDER_IMAGE,
                        "_PYTHON_BASE_IMAGE": PYTHON_BASE_IMAGE,
                        "_RELEASE_SHA": RELEASE,
                        "_SOURCE_CONTEXT_SHA256": CONTEXT_DIGEST,
                    },
                    "options": {"requestedVerifyOption": "VERIFIED"},
                    "steps": [{"name": DOCKER_BUILDER_IMAGE}],
                    "source": {"storageSource": {"bucket": "aigc-build-source-nane1"}},
                    "results": {"images": [{"name": tagged, "digest": DIGEST}]},
                }
            )
        if command[:5] == ["gcloud", "artifacts", "docker", "images", "describe"]:
            return json.dumps({"image_summary": {"digest": DIGEST}})
        if command[:4] == ["gcloud", "storage", "buckets", "describe"]:
            bucket = command[4].removeprefix("gs://")
            return json.dumps(
                {
                    "name": bucket,
                    "location": deployer.REGION,
                }
            )
        if command[:3] == ["gcloud", "projects", "get-iam-policy"]:
            expression = " || ".join(
                (
                    f"resource.name == 'projects/{PROJECT}/locations/{deployer.REGION}/services/aigc-nexus-operator'",
                    f"resource.name == 'projects/{PROJECT}/locations/{deployer.REGION}/services/aigc-nexus-judge'",
                )
            )
            return json.dumps(
                {
                    "bindings": [
                        {
                            "role": "roles/run.invoker",
                            "members": [f"serviceAccount:{DEPLOYER_ACCOUNT}"],
                            "condition": {"expression": expression},
                        }
                    ]
                }
            )
        if command[:5] == [
            "gcloud",
            "run",
            "jobs",
            "describe",
            "aigc-migrate-aaaaaaaa",
        ]:
            return json.dumps(
                {
                    "metadata": {
                        "name": (
                            f"projects/{PROJECT}/locations/{deployer.REGION}/jobs/"
                            "aigc-migrate-aaaaaaaa"
                        ),
                        "labels": {
                            "aigc-release-sha": RELEASE,
                            "aigc-purpose": "migration",
                        },
                    },
                    "spec": {
                        "template": {
                            "metadata": {
                                "annotations": {
                                    "run.googleapis.com/cloudsql-instances": (
                                        f"{PROJECT}:{deployer.REGION}:aigc-control"
                                    ),
                                    "run.googleapis.com/network-interfaces": json.dumps(
                                        [
                                            {
                                                "network": "aigc-vpc",
                                                "subnetwork": "aigc-subnet",
                                            }
                                        ]
                                    ),
                                }
                            },
                            "spec": {
                                "taskCount": 1,
                                "parallelism": 1,
                                "template": {
                                    "maxRetries": 0,
                                    "serviceAccountName": OPERATOR_ACCOUNT,
                                    "containers": [
                                        {
                                            "image": immutable,
                                            "command": ["python"],
                                            "args": [
                                                "-m",
                                                "src.operations.nexus_postgres_migrate",
                                            ],
                                            "env": [
                                                {
                                                    "name": (
                                                        "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF"
                                                    ),
                                                    "value": SECRET_REF,
                                                }
                                            ],
                                        }
                                    ],
                                },
                            },
                        }
                    },
                }
            )
        if command[:5] == ["gcloud", "run", "jobs", "execute", "aigc-migrate-aaaaaaaa"]:
            return json.dumps(
                {
                    "name": (
                        "projects/aigc-stage/locations/northamerica-northeast1/"
                        "jobs/aigc-migrate-aaaaaaaa/executions/execution-1"
                    )
                }
            )
        if command[:3] == ["gcloud", "logging", "read"]:
            return json.dumps(
                [
                    {
                        "labels": {"run.googleapis.com/execution_name": "execution-1"},
                        "resource": {"labels": {"job_name": "aigc-migrate-aaaaaaaa"}},
                        "textPayload": deployer._MIGRATION_MARKER
                        + json.dumps(migration_receipt()),
                    }
                ]
            )
        if command[:6] == ["gcloud", "run", "jobs", "executions", "describe", "execution-1"]:
            return json.dumps(
                {
                    "name": (
                        "projects/aigc-stage/locations/northamerica-northeast1/"
                        "jobs/aigc-migrate-aaaaaaaa/executions/execution-1"
                        ),
                        "metadata": {
                            "annotations": {
                                "run.googleapis.com/cloudsql-instances": (
                                    f"{PROJECT}:{deployer.REGION}:aigc-control"
                                ),
                                "run.googleapis.com/network-interfaces": json.dumps(
                                    [{"network": "aigc-vpc", "subnetwork": "aigc-subnet"}]
                                ),
                            }
                        },
                        "template": {
                        "serviceAccount": OPERATOR_ACCOUNT,
                        "containers": [
                            {
                                "image": immutable,
                                "env": [
                                    {
                                        "name": "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF",
                                        "value": SECRET_REF,
                                    }
                                ],
                            }
                        ],
                    },
                }
            )
        if command[:3] == ["gcloud", "run", "deploy"]:
            env_path = Path(command[command.index("--env-vars-file") + 1])
            role = "operator" if command[3] == "aigc-nexus-operator" else "judge"
            environment = {}
            for line in env_path.read_text(encoding="utf-8").splitlines():
                key, raw = line.split(": ", 1)
                environment[key] = json.loads(raw)
            deployed_env[role] = environment
            return ""
        if command[:4] == ["gcloud", "run", "services", "describe"]:
            role = "operator" if command[4] == "aigc-nexus-operator" else "judge"
            return json.dumps(
                {
                    "status": {
                        "url": f"https://{role}-hash-nn.a.run.app",
                        "traffic": [
                            {
                                "tag": f"candidate-{role}-{RELEASE[:8]}",
                                "revisionName": f"aigc-nexus-{role}-00001",
                                "url": f"https://candidate-{role}---{role}-hash-nn.a.run.app",
                                "percent": 0,
                            }
                        ],
                    }
                }
            )
        if command[:5] == ["gcloud", "run", "services", "get-iam-policy", "aigc-nexus-operator"]:
            return json.dumps(
                {
                    "bindings": [
                        {
                            "role": "roles/run.invoker",
                            "members": [f"serviceAccount:{DEPLOYER_ACCOUNT}"],
                        }
                    ]
                }
            )
        if command[:5] == ["gcloud", "run", "services", "get-iam-policy", "aigc-nexus-judge"]:
            return json.dumps(
                {
                    "bindings": [
                        {
                            "role": "roles/run.invoker",
                            "members": [f"serviceAccount:{DEPLOYER_ACCOUNT}"],
                        }
                    ]
                }
            )
        if command[:4] == ["gcloud", "run", "revisions", "describe"]:
            role = "operator" if "operator" in command[4] else "judge"
            account = OPERATOR_ACCOUNT if role == "operator" else JUDGE_ACCOUNT
            return json.dumps(
                {
                    "metadata": {
                        "labels": {
                            "aigc-release-sha": RELEASE,
                            "aigc-runtime-role": role,
                        }
                    },
                    "spec": {
                        "serviceAccountName": account,
                        "containers": [
                            {
                                "image": immutable,
                                "env": [
                                    {"name": key, "value": value}
                                    for key, value in deployed_env[role].items()
                                ],
                            }
                        ],
                    },
                }
            )
        return ""

    def fake_probe(url, *, audience, expected_identity):
        assert expected_identity == DEPLOYER_ACCOUNT
        role = "operator" if "operator" in url else "judge"
        return {
            "ready": True,
            "project_id": PROJECT,
            "runtime_role": role,
            "provider_capable": role == "operator",
            "release_revision": RELEASE,
            "image_digest": DIGEST,
            "region": deployer.REGION,
            "deployment_authorization_sha256": expected_authorization,
            "live_provider_execution_enabled": False,
            "production_activation": False,
            "runtime_control_backend": "postgresql" if role == "operator" else "not_applicable",
            "emergency_active": False,
            "stop_epoch": 0 if role == "operator" else None,
        }

    monkeypatch.setattr(deployer, "_run", fake_run)
    monkeypatch.setattr(deployer, "_authenticated_json", fake_probe)
    output = tmp_path / "receipt.json"
    plan = deployer.build_plan(payload(), {})
    predecessor = None
    result = None
    for index in range(len(deployer._ACTION_NAMES)):
        permit = action_permit(plan, predecessor=predecessor)
        result = deployer.execute_staging_action(
            payload(),
            {},
            ci_admission=ci_admission(),
            action_permit=permit,
            predecessor_checkpoint=predecessor,
            checkpoint_output=tmp_path / f"checkpoint-{index}.json",
            deployment_receipt_output=output,
        )
        predecessor = result["checkpoint"]
        assert result["target_mutations_dispatched"] == 1
        assert len(
            result["checkpoint"]["checkpoint"]["completed_actions"]
        ) == index + 1
    assert result is not None
    receipt = result["deployment_receipt"]
    assert receipt is not None

    mutating = [command for command, mutation in commands if mutation]
    mutation_kinds = []
    for command in mutating:
        if command[:3] == ["gcloud", "builds", "submit"]:
            mutation_kinds.append("cloud_build_submit")
        elif command[:4] == ["gcloud", "artifacts", "sbom", "load"]:
            mutation_kinds.append("sbom_export")
        elif command[:5] == ["gcloud", "run", "jobs", "deploy", "aigc-migrate-aaaaaaaa"]:
            mutation_kinds.append("migration_job_deploy")
        elif command[:5] == ["gcloud", "run", "jobs", "execute", "aigc-migrate-aaaaaaaa"]:
            mutation_kinds.append("migration_execute")
        elif command[:3] == ["gcloud", "run", "deploy"]:
            mutation_kinds.append(f"{deployed_env['operator' if command[3].endswith('operator') else 'judge']['AIGC_RUNTIME_ROLE']}_deploy")
    assert mutation_kinds == list(deployer._ACTION_NAMES)
    assert len(consumed) == len(deployer._ACTION_NAMES)
    assert len({record[2]["permit_sha256"] for record in consumed}) == 6
    assert all(record[2]["state"] == "consumed_before_dispatch" for record in consumed)
    assert contexts[0]["expected_sha"] == RELEASE
    assert contexts[0]["expected_tree"] == TREE

    operator_command = next(command for command in mutating if command[:4] == ["gcloud", "run", "deploy", "aigc-nexus-operator"])
    judge_command = next(command for command in mutating if command[:4] == ["gcloud", "run", "deploy", "aigc-nexus-judge"])
    assert operator_command[operator_command.index("--image") + 1] == immutable
    assert "--network" in operator_command and "--set-cloudsql-instances" in operator_command
    assert "--network" not in judge_command and "--set-cloudsql-instances" not in judge_command
    assert "--clear-network" in judge_command
    assert "--clear-cloudsql-instances" in judge_command
    assert "--clear-secrets" in judge_command
    assert "--no-traffic" in operator_command and "--no-allow-unauthenticated" in judge_command
    assert deployed_env["operator"]["AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF"] == SECRET_REF
    assert "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF" not in deployed_env["judge"]
    assert deployed_env["judge"]["AIGC_LIVE_PROVIDER_EXECUTION_ENABLED"] == "false"
    assert deployed_env["judge"]["AIGC_DEPLOYMENT_AUTHORIZATION_SHA256"] == expected_authorization
    assert [item["action"] for item in receipt["actions"]] == list(deployer._ACTION_NAMES)
    assert receipt["migration"]["execution_name"].endswith("execution-1")
    assert receipt["operator_revision"] == "aigc-nexus-operator-00001"
    assert receipt["judge_revision"] == "aigc-nexus-judge-00001"
    assert receipt["build_context_manifest_sha256"] == CONTEXT_DIGEST
    assert receipt["receipt_sha256"] == deployer._canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    deployer._validate_receipt(receipt)
    assert json.loads(output.read_text(encoding="utf-8")) == receipt
    assert predecessor["checkpoint"]["terminal_deployment_receipt"] == receipt


def test_candidate_target_rejects_a_stale_or_different_tag(monkeypatch):
    monkeypatch.setattr(
        deployer,
        "_run",
        lambda *_args, **_kwargs: json.dumps(
            {
                "status": {
                    "url": "https://operator.example.invalid",
                    "traffic": [
                        {
                            "tag": "candidate-operator-deadbeef",
                            "revisionName": "old-revision",
                            "url": "https://old.example.invalid",
                        }
                    ],
                }
            }
        ),
    )
    with pytest.raises(deployer.NexusStagingDeploymentError, match="exact candidate tag"):
        deployer._candidate_target(
            project=PROJECT,
            service="aigc-nexus-operator",
            candidate_tag=f"candidate-operator-{RELEASE[:8]}",
            immutable_image="image@" + DIGEST,
            service_account=OPERATOR_ACCOUNT,
            runtime_role="operator",
            release_sha=RELEASE,
            digest=DIGEST,
            authorization_sha256=AUTHORIZATION_DIGEST,
            expected_secret_reference=SECRET_REF,
        )


def test_private_service_evidence_rejects_public_invocation(monkeypatch):
    monkeypatch.setattr(
        deployer,
        "_run",
        lambda *_args, **_kwargs: json.dumps(
            {
                "bindings": [
                    {
                        "role": "roles/run.invoker",
                        "members": ["allUsers"],
                    }
                ]
            }
        ),
    )
    with pytest.raises(deployer.NexusStagingDeploymentError, match="public invocation"):
        deployer._private_service_iam(
            project=PROJECT,
            service="aigc-nexus-operator",
        )


def test_deployer_invoker_must_be_bound_on_the_exact_service(monkeypatch):
    observed: list[str] = []

    def service_policy(command, **_kwargs):
        observed.extend(command)
        return json.dumps(
            {
                "bindings": [
                    {
                        "role": "roles/run.invoker",
                        "members": [f"serviceAccount:{DEPLOYER_ACCOUNT}"],
                    }
                ]
            }
        )

    monkeypatch.setattr(deployer, "_run", service_policy)
    assert deployer._deployer_invoker_binding(
        project=PROJECT,
        deployer_service_account=DEPLOYER_ACCOUNT,
        service="aigc-nexus-operator",
    ) is True
    assert observed[:5] == [
        "gcloud",
        "run",
        "services",
        "get-iam-policy",
        "aigc-nexus-operator",
    ]
    assert "projects" not in observed[:2]


def test_project_style_conditional_invoker_is_not_accepted_as_service_scope(monkeypatch):
    monkeypatch.setattr(
        deployer,
        "_run",
        lambda *_args, **_kwargs: json.dumps(
            {
                "bindings": [
                    {
                        "role": "roles/run.invoker",
                        "members": [f"serviceAccount:{DEPLOYER_ACCOUNT}"],
                        "condition": {
                            "expression": "resource.name == 'unsupported'"
                        },
                    }
                ]
            }
        ),
    )
    with pytest.raises(deployer.NexusStagingDeploymentError, match="per-service"):
        deployer._deployer_invoker_binding(
            project=PROJECT,
            deployer_service_account=DEPLOYER_ACCOUNT,
            service="aigc-nexus-operator",
        )


def test_migration_receipt_rejects_a_different_execution_label(monkeypatch):
    monkeypatch.setattr(
        deployer,
        "_run",
        lambda *_args, **_kwargs: json.dumps(
            [
                {
                    "labels": {"run.googleapis.com/execution_name": "execution-old"},
                    "resource": {"labels": {"job_name": "aigc-migrate-aaaaaaaa"}},
                    "textPayload": deployer._MIGRATION_MARKER
                    + json.dumps(migration_receipt()),
                }
            ]
        ),
    )
    with pytest.raises(deployer.NexusStagingDeploymentError, match="exact migration"):
        deployer._migration_receipt(
            project=PROJECT,
            job_name="aigc-migrate-aaaaaaaa",
            execution_name="execution-1",
        )


def test_receipt_hash_tampering_fails_closed():
    invalid = {"schema_version": deployer.RECEIPT_SCHEMA, "receipt_sha256": "0" * 64}
    with pytest.raises(deployer.NexusStagingDeploymentError, match="schema mismatch"):
        deployer._validate_receipt(invalid)


def test_mutating_command_failure_is_indeterminate(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "failure"

    monkeypatch.setattr(deployer.subprocess, "run", lambda *_args, **_kwargs: Result())
    with pytest.raises(deployer.NexusStagingMutationIndeterminate):
        deployer._run(["gcloud", "run", "deploy"], mutating=True)


def test_local_write_failure_after_remote_checkpoint_reports_recovery(monkeypatch, tmp_path):
    plan = {"actions": [{"action": "cloud_build_submit", "target": "target"}]}
    monkeypatch.setattr(deployer, "_prepare_create_only_local_path", lambda _path: None)
    monkeypatch.setattr(deployer, "validate_quebec_authorization", lambda *_args, **_kwargs: summary())
    monkeypatch.setattr(deployer, "_validate_ci_admission", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(deployer, "_git_identity", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(deployer, "build_plan", lambda *_args, **_kwargs: plan)
    monkeypatch.setattr(deployer, "_validated_checkpoint", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        deployer,
        "validate_action_permit",
        lambda *_args, **_kwargs: {
            "action_index": 0,
            "action_name": "cloud_build_submit",
            "permit_kind": "execute",
        },
    )
    monkeypatch.setattr(
        deployer,
        "_execute_or_reconcile_action",
        lambda **_kwargs: ([], {}, None),
    )
    remote = {
        "checkpoint_object_uri": (
            f"gs://{PROJECT}-aigc-receipts/staging-action-checkpoints/{RELEASE}/"
            f"00-{'a' * 64}.json"
        ),
        "checkpoint_object_generation": "77",
        "checkpoint_object_sha256": "b" * 64,
    }
    monkeypatch.setattr(
        deployer,
        "_publish_action_checkpoint",
        lambda **_kwargs: remote,
    )
    monkeypatch.setattr(
        deployer,
        "_write_json_create_only",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk failure")),
    )
    with pytest.raises(
        deployer.NexusStagingMutationIndeterminate,
        match="do not retry the target.*generation 77",
    ):
        deployer.execute_staging_action(
            payload(),
            {},
            ci_admission={},
            action_permit={},
            predecessor_checkpoint=None,
            checkpoint_output=tmp_path / "checkpoint.json",
            deployment_receipt_output=tmp_path / "receipt.json",
        )


def _provenance_payload(
    *,
    immutable_image: str,
    build_id: str,
    substitutions: dict[str, str],
) -> dict:
    raw_digest = immutable_image.rsplit("@sha256:", 1)[1]
    return {
        "image_summary": {"digest": f"sha256:{raw_digest}"},
        "provenance_summary": {
            "provenance": [
                {
                    "build": {
                        "inTotoSlsaProvenanceV1": {
                            "predicate": {
                                "buildDefinition": {
                                    "buildType": "https://cloud.google.com/build/gcb-buildtypes/google-worker/v1",
                                    "externalParameters": {"substitutions": substitutions},
                                    "internalParameters": {
                                        "systemSubstitutions": {"BUILD_ID": build_id}
                                    },
                                },
                                "runDetails": {
                                    "builder": {"id": deployer._CLOUD_BUILD_BUILDER_ID},
                                    "metadata": {
                                        "invocationId": (
                                            f"https://cloudbuild.googleapis.com/v1/projects/{PROJECT}/"
                                            f"locations/{deployer.REGION}/builds/{build_id}"
                                        )
                                    },
                                },
                            },
                            "subject": [{"digest": {"sha256": raw_digest}}],
                        }
                    },
                    "envelope": {
                        "signatures": [{"keyid": "verified-builder", "sig": "opaque"}]
                    },
                }
            ]
        },
    }


def test_artifact_security_evidence_binds_provenance_sbom_and_scan(monkeypatch):
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    substitutions = {
        "_IMAGE_URI": immutable.split("@", 1)[0] + f":{RELEASE}",
        "_DOCKER_BUILDER_IMAGE": DOCKER_BUILDER_IMAGE,
        "_PYTHON_BASE_IMAGE": PYTHON_BASE_IMAGE,
        "_RELEASE_SHA": RELEASE,
        "_SOURCE_CONTEXT_SHA256": CONTEXT_DIGEST,
    }

    def fake_run(command, *, capture=False, mutating=False):
        if command[:5] == ["gcloud", "artifacts", "docker", "images", "describe"]:
            return json.dumps(
                _provenance_payload(
                    immutable_image=immutable,
                    build_id="build-123",
                    substitutions=substitutions,
                )
            )
        if command[:4] == ["gcloud", "artifacts", "vulnerabilities", "list"]:
            return "[]"
        raise AssertionError(command)

    monkeypatch.setattr(deployer, "_run", fake_run)
    monkeypatch.setattr(
        deployer,
        "_sbom_reference_evidence",
        lambda **_kwargs: {
            "sbom_reference_count": 1,
            "sbom_metadata_sha256": "6" * 64,
            "sbom_gcs_uri": f"gs://{EVIDENCE_BUCKET}/sboms/exact.spdx.json",
            "sbom_gcs_bucket": EVIDENCE_BUCKET,
            "sbom_gcs_location": deployer.REGION,
            "sbom_occurrence_name": (
                f"projects/{PROJECT}/locations/{deployer.REGION}/occurrences/sbom-1"
            ),
        },
    )
    monkeypatch.setattr(
        deployer,
        "_package_vulnerability_scan_evidence",
        lambda **_kwargs: {
            "vulnerability_scan_status": "FINISHED_SUCCESS",
            "vulnerability_scan_note": deployer._PACKAGE_VULNERABILITY_NOTE,
            "vulnerability_scan_occurrence_name": (
                f"projects/{PROJECT}/locations/{deployer.REGION}/occurrences/scan-1"
            ),
            "vulnerability_scan_metadata_sha256": "8" * 64,
        },
    )
    evidence = deployer._artifact_security_evidence(
        project=PROJECT,
        immutable_image=immutable,
        image_digest=DIGEST,
        build_id="build-123",
        expected_substitutions=substitutions,
        sbom_bucket=EVIDENCE_BUCKET,
        sbom_local_metadata={
            "sbom_generator_image": SBOM_GENERATOR_IMAGE,
            "sbom_source_image_uri": immutable,
            "sbom_local_sha256": "0" * 64,
            "sbom_format": "SPDX-2.3",
            "sbom_package_count": 7,
            "sbom_document_namespace_sha256": "1" * 64,
        },
        deployer_service_account=DEPLOYER_ACCOUNT,
    )
    assert evidence["provenance_build_id"] == "build-123"
    assert evidence["sbom_reference_count"] == 1
    assert evidence["release_blocking_vulnerability_count"] == 0


def test_artifact_security_evidence_rejects_high_vulnerability(monkeypatch):
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    substitutions = {
        "_IMAGE_URI": immutable.split("@", 1)[0] + f":{RELEASE}",
        "_DOCKER_BUILDER_IMAGE": DOCKER_BUILDER_IMAGE,
        "_PYTHON_BASE_IMAGE": PYTHON_BASE_IMAGE,
        "_RELEASE_SHA": RELEASE,
        "_SOURCE_CONTEXT_SHA256": CONTEXT_DIGEST,
    }

    def fake_run(command, *, capture=False, mutating=False):
        if command[:5] == ["gcloud", "artifacts", "docker", "images", "describe"]:
            return json.dumps(
                _provenance_payload(
                    immutable_image=immutable,
                    build_id="build-123",
                    substitutions=substitutions,
                )
            )
        if command[:4] == ["gcloud", "artifacts", "vulnerabilities", "list"]:
            return json.dumps([{"effectiveSeverity": "HIGH"}])
        raise AssertionError(command)

    monkeypatch.setattr(deployer, "_run", fake_run)
    monkeypatch.setattr(
        deployer,
        "_sbom_reference_evidence",
        lambda **_kwargs: {
            "sbom_reference_count": 1,
            "sbom_metadata_sha256": "6" * 64,
            "sbom_gcs_uri": f"gs://{EVIDENCE_BUCKET}/sboms/exact.spdx.json",
            "sbom_gcs_bucket": EVIDENCE_BUCKET,
            "sbom_gcs_location": deployer.REGION,
            "sbom_occurrence_name": (
                f"projects/{PROJECT}/locations/{deployer.REGION}/occurrences/sbom-1"
            ),
        },
    )
    with pytest.raises(deployer.NexusStagingDeploymentError, match="release-blocking"):
        deployer._artifact_security_evidence(
            project=PROJECT,
            immutable_image=immutable,
            image_digest=DIGEST,
            build_id="build-123",
            expected_substitutions=substitutions,
            sbom_bucket=EVIDENCE_BUCKET,
            sbom_local_metadata={"sbom_local_sha256": "0" * 64},
            deployer_service_account=DEPLOYER_ACCOUNT,
        )


def _sbom_occurrence(*, immutable: str, local_sha256: str) -> dict:
    raw_digest = immutable.rsplit("@sha256:", 1)[1]
    return {
        "name": (
            f"projects/{PROJECT}/locations/{deployer.REGION}/occurrences/sbom-1"
        ),
        "resourceUri": immutable,
        "noteName": f"projects/{PROJECT}/notes/aigc-sbom-1",
        "kind": "SBOM_REFERENCE",
        "sbomReference": {
            "payloadType": "application/vnd.in-toto+json",
            "payload": {
                "subject": [
                    {
                        "name": immutable,
                        "digest": {"sha256": raw_digest},
                    }
                ],
                "predicate": {
                    "location": f"gs://{EVIDENCE_BUCKET}/sboms/exact.spdx.json",
                    "mimeType": "application/spdx+json",
                    "digest": {"sha256": local_sha256},
                },
            },
        },
    }


def test_sbom_reference_evidence_binds_exact_image_hash_and_montreal_bucket(
    monkeypatch,
):
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    local_sha256 = "0" * 64
    occurrence = _sbom_occurrence(
        immutable=immutable,
        local_sha256=local_sha256,
    )
    monkeypatch.setattr(
        deployer,
        "_occurrences_for_exact_resource",
        lambda **_kwargs: [occurrence],
    )
    evidence = deployer._sbom_reference_evidence(
        project=PROJECT,
        immutable_image=immutable,
        image_digest=DIGEST,
        sbom_bucket=EVIDENCE_BUCKET,
        sbom_local_sha256=local_sha256,
        expected_principal=DEPLOYER_ACCOUNT,
    )
    assert evidence["sbom_reference_count"] == 1
    assert evidence["sbom_gcs_bucket"] == EVIDENCE_BUCKET
    assert evidence["sbom_gcs_location"] == deployer.REGION
    assert evidence["sbom_gcs_uri"].startswith(f"gs://{EVIDENCE_BUCKET}/")


@pytest.mark.parametrize(
    "tamper",
    (
        "resource",
        "subject_name",
        "subject_digest",
        "local_hash",
        "bucket",
        "traversal",
        "encoded_traversal",
        "whitespace",
        "malformed_uri",
        "occurrence_location",
        "duplicate",
    ),
)
def test_sbom_reference_evidence_rejects_ambiguous_or_unbound_metadata(
    monkeypatch,
    tamper,
):
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    local_sha256 = "0" * 64
    occurrence = _sbom_occurrence(
        immutable=immutable,
        local_sha256=local_sha256,
    )
    if tamper == "resource":
        occurrence["resourceUri"] = immutable.replace("aigc-nexus", "other")
    elif tamper == "subject_name":
        occurrence["sbomReference"]["payload"]["subject"][0]["name"] = (
            immutable.replace("aigc-nexus", "other")
        )
    elif tamper == "subject_digest":
        occurrence["sbomReference"]["payload"]["subject"][0]["digest"][
            "sha256"
        ] = "9" * 64
    elif tamper == "local_hash":
        occurrence["sbomReference"]["payload"]["predicate"]["digest"][
            "sha256"
        ] = "9" * 64
    elif tamper == "bucket":
        occurrence["sbomReference"]["payload"]["predicate"]["location"] = (
            "gs://attacker-bucket/sbom.spdx.json"
        )
    elif tamper == "traversal":
        occurrence["sbomReference"]["payload"]["predicate"]["location"] = (
            f"gs://{EVIDENCE_BUCKET}/sboms/../attacker.json"
        )
    elif tamper == "encoded_traversal":
        occurrence["sbomReference"]["payload"]["predicate"]["location"] = (
            f"gs://{EVIDENCE_BUCKET}/sboms/%2e%2e/attacker.json"
        )
    elif tamper == "whitespace":
        occurrence["sbomReference"]["payload"]["predicate"]["location"] = (
            f"gs://{EVIDENCE_BUCKET}/sboms/attacker%0a.json"
        )
    elif tamper == "malformed_uri":
        occurrence["sbomReference"]["payload"]["predicate"]["location"] = (
            "gs://[invalid/sbom.json"
        )
    elif tamper == "occurrence_location":
        occurrence["name"] = f"projects/{PROJECT}/occurrences/sbom-1"
    records = [occurrence, occurrence] if tamper == "duplicate" else [occurrence]
    if tamper == "duplicate":
        records[1] = json.loads(json.dumps(occurrence))
        records[1]["name"] = (
            f"projects/{PROJECT}/locations/{deployer.REGION}/occurrences/sbom-2"
        )
    monkeypatch.setattr(
        deployer,
        "_occurrences_for_exact_resource",
        lambda **_kwargs: records,
    )
    with pytest.raises(deployer.NexusStagingDeploymentError, match="exactly one"):
        deployer._sbom_reference_evidence(
            project=PROJECT,
            immutable_image=immutable,
            image_digest=DIGEST,
            sbom_bucket=EVIDENCE_BUCKET,
            sbom_local_sha256=local_sha256,
            expected_principal=DEPLOYER_ACCOUNT,
        )


def _scan_occurrence(*, immutable: str) -> dict:
    return {
        "name": (
            f"projects/{PROJECT}/locations/{deployer.REGION}/occurrences/scan-1"
        ),
        "resourceUri": immutable,
        "noteName": deployer._PACKAGE_VULNERABILITY_NOTE,
        "kind": "DISCOVERY",
        "discovery": {"analysisStatus": "FINISHED_SUCCESS"},
    }


@pytest.mark.parametrize(
    "note_name",
    (
        deployer._PACKAGE_VULNERABILITY_NOTE,
        deployer._REGIONAL_PACKAGE_VULNERABILITY_NOTE,
    ),
)
def test_vulnerability_completion_requires_exact_package_discovery_occurrence(
    monkeypatch,
    note_name,
):
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    occurrence = _scan_occurrence(immutable=immutable)
    occurrence["noteName"] = note_name
    observed: dict[str, str] = {}

    def exact_query(**kwargs):
        observed.update(kwargs)
        return [occurrence]

    monkeypatch.setattr(deployer, "_occurrences_for_exact_resource", exact_query)
    evidence = deployer._package_vulnerability_scan_evidence(
        project=PROJECT,
        immutable_image=immutable,
        expected_principal=DEPLOYER_ACCOUNT,
    )
    assert observed["filter_suffix"] == (
        'noteProjectId="goog-analysis" AND noteId="PACKAGE_VULNERABILITY"'
    )
    assert evidence["vulnerability_scan_status"] == "FINISHED_SUCCESS"
    assert evidence["vulnerability_scan_note"] == note_name


def test_occurrence_query_uses_official_montreal_regional_endpoint(monkeypatch):
    observed: dict[str, object] = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"occurrences": []}

    class Session:
        @staticmethod
        def request(method, url, *, params, timeout):
            observed.update(
                {"method": method, "url": url, "params": params, "timeout": timeout}
            )
            return Response()

    monkeypatch.setattr(
        deployer,
        "_authorized_session_for_principal",
        lambda **_kwargs: Session(),
    )
    assert deployer._list_regional_occurrences(
        project=PROJECT,
        filter_expression='kind="DISCOVERY"',
        expected_principal=DEPLOYER_ACCOUNT,
    ) == []
    assert observed["method"] == "GET"
    assert observed["url"] == (
        f"https://containeranalysis.{deployer.REGION}.rep.googleapis.com/v1/"
        f"projects/{PROJECT}/locations/{deployer.REGION}/occurrences"
    )
    assert observed["params"] == {
        "filter": 'kind="DISCOVERY"',
        "pageSize": "1000",
    }


@pytest.mark.parametrize(
    "tamper",
    ("resource", "note", "kind", "status", "global_name", "nested_success", "duplicate"),
)
def test_vulnerability_completion_rejects_unrelated_or_ambiguous_success(
    monkeypatch,
    tamper,
):
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    occurrence = _scan_occurrence(immutable=immutable)
    if tamper == "resource":
        occurrence["resourceUri"] = immutable.replace("aigc-nexus", "other")
    elif tamper == "note":
        occurrence["noteName"] = "projects/goog-analysis/notes/OTHER_ANALYSIS"
    elif tamper == "kind":
        occurrence["kind"] = "VULNERABILITY"
    elif tamper == "status":
        occurrence["discovery"]["analysisStatus"] = "PENDING"
    elif tamper == "global_name":
        occurrence["name"] = f"projects/{PROJECT}/occurrences/scan-1"
    elif tamper == "nested_success":
        occurrence["discovery"]["analysisStatus"] = "PENDING"
        occurrence["unrelated"] = {
            "deeply": {"nested": {"analysisStatus": "FINISHED_SUCCESS"}}
        }
    records = [occurrence]
    if tamper == "duplicate":
        duplicate = json.loads(json.dumps(occurrence))
        duplicate["name"] = (
            f"projects/{PROJECT}/locations/{deployer.REGION}/occurrences/scan-2"
        )
        records.append(duplicate)
    monkeypatch.setattr(
        deployer,
        "_occurrences_for_exact_resource",
        lambda **_kwargs: records,
    )
    with pytest.raises(deployer.NexusStagingDeploymentError, match="PACKAGE_VULNERABILITY"):
        deployer._package_vulnerability_scan_evidence(
            project=PROJECT,
            immutable_image=immutable,
            expected_principal=DEPLOYER_ACCOUNT,
        )


def _spdx_document(*, immutable: str) -> dict:
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": immutable,
        "documentNamespace": "https://example.invalid/spdx/exact",
        "creationInfo": {
            "creators": ["Organization: Anchore, Inc", "Tool: syft-1.25.0"]
        },
        "packages": [{"SPDXID": "SPDXRef-RootPackage", "name": "root"}],
        "documentDescribes": ["SPDXRef-RootPackage"],
    }


def test_generated_spdx_must_be_syft_output_for_exact_immutable_image(tmp_path):
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    sbom_path = tmp_path / "sbom.spdx.json"
    sbom_path.write_text(
        json.dumps(_spdx_document(immutable=immutable)),
        encoding="utf-8",
    )
    metadata = deployer._validate_generated_spdx(
        sbom_path=sbom_path,
        immutable_image=immutable,
    )
    assert metadata["sbom_format"] == "SPDX-2.3"
    assert metadata["sbom_package_count"] == 1
    assert len(metadata["sbom_local_sha256"]) == 64


@pytest.mark.parametrize(
    "tamper",
    ("image", "creator", "describes", "version", "document_id", "duplicate_package"),
)
def test_generated_spdx_rejects_unbound_or_non_syft_document(
    tmp_path,
    tamper,
):
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    document = _spdx_document(immutable=immutable)
    if tamper == "image":
        document["name"] = immutable.replace("aigc-nexus", "other")
    elif tamper == "creator":
        document["creationInfo"]["creators"] = ["Tool: attacker-1.0"]
    elif tamper == "describes":
        document["documentDescribes"] = ["SPDXRef-Unbound"]
    elif tamper == "version":
        document["spdxVersion"] = "SPDX-3.0"
    elif tamper == "document_id":
        document["SPDXID"] = "SPDXRef-Attacker"
    else:
        document["packages"].append(
            {"SPDXID": "SPDXRef-RootPackage", "name": "duplicate"}
        )
    sbom_path = tmp_path / "sbom.spdx.json"
    sbom_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(deployer.NexusStagingDeploymentError, match="Syft-produced"):
        deployer._validate_generated_spdx(
            sbom_path=sbom_path,
            immutable_image=immutable,
        )


def test_generated_spdx_rejects_duplicate_json_members(tmp_path):
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    document = json.dumps(_spdx_document(immutable=immutable))
    duplicate = document.replace(
        '"spdxVersion": "SPDX-2.3"',
        '"spdxVersion": "SPDX-2.3", "spdxVersion": "SPDX-2.3"',
        1,
    )
    sbom_path = tmp_path / "sbom.spdx.json"
    sbom_path.write_text(duplicate, encoding="utf-8")
    with pytest.raises(deployer.NexusStagingDeploymentError, match="canonical JSON"):
        deployer._validate_generated_spdx(
            sbom_path=sbom_path,
            immutable_image=immutable,
        )


def test_pinned_syft_generation_is_networkless_read_only_and_digest_bound(
    monkeypatch,
    tmp_path,
):
    immutable = (
        f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/aigc-nexus@{DIGEST}"
    )
    commands: list[list[str]] = []

    def fake_local(command, *, env, capture=False):
        command = list(command)
        commands.append(command)
        assert env["DOCKER_CONFIG"].startswith(str(tmp_path))
        if command[:3] == ["docker", "image", "inspect"]:
            return json.dumps([command[-1]])
        if command[:3] == ["docker", "image", "save"]:
            Path(command[command.index("--output") + 1]).write_bytes(b"exact-image")
        if command[:2] == ["docker", "run"]:
            output_mount = next(
                item for item in command if item.endswith(",dst=/output")
            )
            output_dir = Path(
                output_mount.split("src=", 1)[1].split(",dst=/output", 1)[0]
            )
            (output_dir / "sbom.spdx.json").write_text(
                json.dumps(_spdx_document(immutable=immutable)),
                encoding="utf-8",
            )
        return ""

    monkeypatch.setattr(deployer, "_run_sbom_local", fake_local)
    _path, metadata = deployer._generate_pinned_sbom(
        immutable_image=immutable,
        generator_image=SBOM_GENERATOR_IMAGE,
        deployer_service_account=DEPLOYER_ACCOUNT,
        work_dir=tmp_path,
    )
    run_command = next(command for command in commands if command[:2] == ["docker", "run"])
    for required in (
        "--pull=never",
        "--network=none",
        "--read-only",
        "--cpus=2",
        "--memory=1g",
        "--memory-swap=1g",
        "--pids-limit=256",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--user=65532:65532",
        "--env=SYFT_CHECK_FOR_APP_UPDATE=false",
    ):
        assert required in run_command
    assert SBOM_GENERATOR_IMAGE in run_command
    assert "docker-archive:/input/image.tar" in run_command
    assert "--quiet" in run_command
    assert metadata["sbom_generator_image"] == SBOM_GENERATOR_IMAGE
    assert metadata["sbom_source_image_uri"] == immutable
    assert not any(command[:3] == ["gcloud", "artifacts", "sbom"] for command in commands)


def test_sbom_generation_rejects_unpinned_generator_before_local_execution(
    monkeypatch,
    tmp_path,
):
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unpinned generator must not execute")

    monkeypatch.setattr(deployer, "_run_sbom_local", forbidden)
    with pytest.raises(deployer.NexusStagingDeploymentError, match="authorization-bound"):
        deployer._generate_pinned_sbom(
            immutable_image=(
                f"{deployer.REGION}-docker.pkg.dev/{PROJECT}/aigc-runtime/"
                f"aigc-nexus@{DIGEST}"
            ),
            generator_image="anchore/syft:latest",
            deployer_service_account=DEPLOYER_ACCOUNT,
            work_dir=tmp_path,
        )
    assert called is False
