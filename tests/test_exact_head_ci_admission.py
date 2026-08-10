from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import jsonschema
import pytest
import yaml

from scripts import assemble_exact_head_ci_admission as assembler
from scripts import deploy_nexus_staging as deployer


RELEASE = "a" * 40
TREE = "b" * 40
RUN_ID = 123456789
ARTIFACT_ID = 987654321
BASE_IMAGE = "python:3.12.13-slim-bookworm@sha256:" + "1" * 64
_CONTEXT_PATHS = sorted(
    {*assembler._BUILD_CONTEXT_REQUIRED_FILES, "src/example.py"}
)
_CONTEXT_RECORDS = [
    {
        "path": path,
        "git_blob_sha": hashlib.sha1(path.encode()).hexdigest(),
        "mode": "100644",
        "sha256": hashlib.sha256(f"content:{path}".encode()).hexdigest(),
    }
    for path in _CONTEXT_PATHS
]


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


@pytest.fixture(autouse=True)
def _exact_build_context_tree(monkeypatch):
    monkeypatch.setattr(
        assembler,
        "_build_context_tree_entries",
        lambda _release_sha: _CONTEXT_RECORDS,
    )


def _successful_stage_evidence(
    stage: dict,
    *,
    lockfile_digest: str,
) -> tuple[list[dict], dict | None]:
    stage_id = stage["id"]
    commands = assembler._expected_stage_commands(
        stage,
        release_sha=RELEASE,
    )
    outcomes = []
    diagnostics = assembler._safe_success_diagnostics(stage_id)
    for index, command in enumerate(commands):
        accepted = [0]
        outcome = {
            "argv": command,
            "argv_sha256": _canonical_sha256(command),
            "exit_code": 0,
            "output_sha256": hashlib.sha256(
                f"{stage_id}:{index}".encode()
            ).hexdigest(),
            "accepted_exit_codes": accepted,
            "policy_accepted": True,
        }
        if diagnostics is not None:
            outcome["sanitized_diagnostics"] = diagnostics
        if stage_id == "quebec_terraform_validate":
            outcome["command_role"] = assembler._QUEBEC_COMMAND_ROLES[index]
        outcomes.append(outcome)

    summary = None
    if stage_id == "quebec_terraform_validate":
        summary = {
            "terraform_root": "infra/gcp/quebec",
            "lockfile_path": "infra/gcp/quebec/.terraform.lock.hcl",
            "lockfile_committed_at_start": True,
            "lockfile_readonly_mode": True,
            "machine_readable_test_plan": True,
            "isolated_in_memory_test_state": True,
            "backend_initialized": False,
            "provider_or_cloud_mutation_performed": False,
            "provider_lock": {
                "lock_sha256": lockfile_digest,
                "provider_source": "registry.terraform.io/hashicorp/google",
                "provider_version": "6.49.0",
                "h1_checksum_count": 1,
                "zh_checksum_count": 1,
            },
            "validate": {"valid": True, "error_count": 0, "warning_count": 0},
            "inert_plan": {
                "managed_resource_change_count": 0,
                "resource_drift_change_count": 0,
                "resource_action_summary": {},
                "drift_action_summary": {},
                "output_action_summary": {"create": 1},
                "output_metadata_change_count": 1,
                "test_file_count": 1,
                "test_run_count": 1,
                "test_plan_count": 1,
                "diagnostic_warning_count": 0,
                "all_assertion_runs_passed": True,
                "machine_readable_test_plan_verified": True,
                "isolated_in_memory_test_state": True,
                "zero_managed_resource_changes": True,
            },
            "lockfile_unchanged": True,
            "status": "success",
            "failure_reason": None,
        }
    return outcomes, summary


def _fixture(tmp_path: Path) -> tuple[dict, dict, Path, dict, Path]:
    contract = json.loads(
        Path("config/exact_sha_ci_validation_contract.json").read_text(encoding="utf-8")
    )
    stage_ids = [item["id"] for item in contract["stages"]]
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    lockfile = tmp_path / ".terraform.lock.hcl"
    lockfile.write_text(
        """provider "registry.terraform.io/hashicorp/google" {
  version     = "6.49.0"
  constraints = "6.49.0"
  hashes = [
    "h1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "zh:1111111111111111111111111111111111111111111111111111111111111111",
  ]
}
""",
        encoding="utf-8",
    )
    lockfile_digest = hashlib.sha256(lockfile.read_bytes()).hexdigest()
    retained = {}
    for stage in contract["stages"]:
        stage_id = stage["id"]
        outcomes, stage_summary = _successful_stage_evidence(
            stage,
            lockfile_digest=lockfile_digest,
        )
        record = {
            "schema_version": "1.2.0",
            "contract_id": contract["contract_id"],
            "contract_sha256": _canonical_sha256(contract),
            "stage_id": stage_id,
            "target_sha": RELEASE,
            "tested_tree_sha": TREE,
            "broker_revision": RELEASE,
            "run_number": 42,
            "run_id": RUN_ID,
            "ordered_command_digest": _canonical_sha256(
                [outcome["argv_sha256"] for outcome in outcomes]
            ),
            "command_outcomes": outcomes,
            "status": "success",
            "external_action_performed": False,
            "production_activation_authorized": False,
            "merge_authority_granted": False,
            "deployment_authority_granted": False,
            "live_model_call_authority_granted": False,
            "financial_authority_granted": False,
        }
        if stage_summary is not None:
            record["stage_summary"] = stage_summary
        record["record_sha256"] = _canonical_sha256(record)
        path = evidence / f"{stage_id}.json"
        _write(path, record)
        retained[stage_id] = {
            "present": True,
            "status": "success",
            "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "record_sha256": record["record_sha256"],
        }

    exact_head = {
        "schema_version": assembler.INNER_SCHEMA_VERSION,
        "repository": assembler.REPOSITORY,
        "pr_number": 0,
        "workflow_event": "push",
        "requested_head_sha": RELEASE,
        "observed_head_sha": RELEASE,
        "tested_tree_sha": TREE,
        "base_sha": "",
        "workflow_revision": RELEASE,
        "workflow_run_number": 42,
        "workflow_run_id": RUN_ID,
        "workflow_run_attempt": 1,
        "artifact_name": f"aigc-colosseum-orchestration-exact-head-{RELEASE}",
        "job_status": "success",
        "canonical_contract_sha256": _canonical_sha256(contract),
        "expected_stage_ids": stage_ids,
        "successful_stage_ids": stage_ids,
        "all_canonical_stages_success": True,
        "stage_receipts": retained,
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
        "quebec_provider_lockfile_sha256": lockfile_digest,
        "captured_timestamp": "2026-08-10T00:00:00+00:00",
        "external_authority_granted": False,
        "external_action_performed": False,
        "merge_authority_granted": False,
        "deployment_authority_granted": False,
        "live_model_call_authority_granted": False,
        "financial_authority_granted": False,
    }
    exact_head["receipt_sha256"] = _canonical_sha256(exact_head)
    _write(evidence / "exact_head_admission_receipt.json", exact_head)

    context_manifest = {
        "schema_version": "aigc.nexus-build-context-manifest.v1",
        "repository": assembler.REPOSITORY,
        "release_sha": RELEASE,
        "release_tree_sha": TREE,
        "file_count": len(_CONTEXT_RECORDS),
        "files": _CONTEXT_RECORDS,
        "ignored_worktree_files_included": False,
    }
    context_manifest["manifest_sha256"] = _canonical_sha256(context_manifest)
    context_path = evidence / "nexus_build_context_receipt.json"
    _write(context_path, context_manifest)
    context_files = {item["path"]: item for item in _CONTEXT_RECORDS}

    container = {
        "schema_version": assembler.CONTAINER_SCHEMA_VERSION,
        "repository_revision": RELEASE,
        "tested_tree_sha": TREE,
        "image_id": "sha256:" + "3" * 64,
        "image_config_user": "aigc",
        "image_identity_labels": {
            "org.opencontainers.image.revision": RELEASE,
            "ai.aigc.source-context-sha256": context_manifest["manifest_sha256"],
        },
        "source_context_sha256": context_manifest["manifest_sha256"],
        "source_context_receipt_sha256": hashlib.sha256(
            context_path.read_bytes()
        ).hexdigest(),
        "dependency_lock_sha256": context_files["requirements.lock"]["sha256"],
        "python_base_image": BASE_IMAGE,
        "dockerfile_sha256": context_files["Dockerfile.nexus"]["sha256"],
        "dockerfile": "Dockerfile.nexus",
        "runtime_smoke": {
            "health_contract_passed": True,
            "health_response_sha256": "8" * 64,
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
    container["receipt_sha256"] = _canonical_sha256(container)
    _write(evidence / "nexus_local_container_build_receipt.json", container)

    run = {
        "id": RUN_ID,
        "run_number": 42,
        "run_attempt": 1,
        "name": "AIGC CI",
        "path": f"{assembler.WORKFLOW_PATH}@main",
        "status": "completed",
        "conclusion": "success",
        "event": "push",
        "head_branch": "main",
        "head_sha": RELEASE,
        "head_repository": {"full_name": assembler.REPOSITORY},
        "html_url": f"https://github.com/{assembler.REPOSITORY}/actions/runs/{RUN_ID}",
    }
    artifact = {
        "id": ARTIFACT_ID,
        "workflow_run": {"id": RUN_ID, "head_branch": "main", "head_sha": RELEASE},
        "name": f"aigc-colosseum-orchestration-exact-head-{RELEASE}",
        "digest": "sha256:" + "9" * 64,
        "expired": False,
    }
    return run, artifact, evidence, contract, lockfile


def test_assembler_emits_schema_valid_deployment_compatible_packet(tmp_path: Path):
    run, artifact, evidence, contract, lockfile = _fixture(tmp_path)
    admission = assembler.assemble_ci_admission(
        run=run,
        artifact=artifact,
        evidence_dir=evidence,
        contract=contract,
        lockfile_path=lockfile,
        release_sha=RELEASE,
        release_tree_sha=TREE,
        protected_branch_verified=True,
    )

    schema = json.loads(
        Path("schemas/exact_head_ci_admission.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(admission, schema)
    summary = deployer._validate_ci_admission(
        admission,
        release_sha=RELEASE,
        release_tree_sha=TREE,
        expected_sha256=_canonical_sha256(admission),
        expected_python_base_image=BASE_IMAGE,
    )
    assert summary["workflow_run_id"] == str(RUN_ID)
    assert summary["artifact_id"] == str(ARTIFACT_ID)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda run, artifact, _evidence: run.update({"conclusion": "failure"}), "successful"),
        (lambda _run, artifact, _evidence: artifact.update({"digest": "sha256:bad"}), "artifact"),
        (
            lambda _run, _artifact, evidence: (evidence / "pip_check.json").write_text("{}\n"),
            "record_sha256",
        ),
    ],
)
def test_assembler_rejects_untrusted_or_tampered_evidence(tmp_path: Path, mutation, message):
    run, artifact, evidence, contract, lockfile = _fixture(tmp_path)
    mutation(run, artifact, evidence)
    with pytest.raises(assembler.CiAdmissionAssemblyError, match=message):
        assembler.assemble_ci_admission(
            run=run,
            artifact=artifact,
            evidence_dir=evidence,
            contract=contract,
            lockfile_path=lockfile,
            release_sha=RELEASE,
            release_tree_sha=TREE,
            protected_branch_verified=True,
        )


def _rewrite_stage_evidence(evidence: Path, stage_id: str, mutate) -> None:
    stage_path = evidence / f"{stage_id}.json"
    record = json.loads(stage_path.read_text(encoding="utf-8"))
    mutate(record)
    record["record_sha256"] = _canonical_sha256(
        {key: value for key, value in record.items() if key != "record_sha256"}
    )
    _write(stage_path, record)

    exact_path = evidence / "exact_head_admission_receipt.json"
    exact = json.loads(exact_path.read_text(encoding="utf-8"))
    exact["stage_receipts"][stage_id]["record_sha256"] = record["record_sha256"]
    exact["stage_receipts"][stage_id]["receipt_sha256"] = hashlib.sha256(
        stage_path.read_bytes()
    ).hexdigest()
    exact["receipt_sha256"] = _canonical_sha256(
        {key: value for key, value in exact.items() if key != "receipt_sha256"}
    )
    _write(exact_path, exact)


def _rewrite_receipt(path: Path, mutate, *, digest_field: str) -> None:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    mutate(receipt)
    receipt[digest_field] = _canonical_sha256(
        {key: value for key, value in receipt.items() if key != digest_field}
    )
    _write(path, receipt)


@pytest.mark.parametrize(
    ("stage_id", "mutate", "message"),
    [
        (
            "pip_check",
            lambda record: record.update({"command_outcomes": []}),
            "no command evidence",
        ),
        (
            "pip_check",
            lambda record: record.update({"ordered_command_digest": "2" * 64}),
            "ordered command digest",
        ),
        (
            "pip_check",
            lambda record: record["command_outcomes"][0].update(
                {"raw_secret": "must-not-be-republished"}
            ),
            "command 0",
        ),
        (
            "pip_check",
            lambda record: record["command_outcomes"][0].update(
                {"argv": ["python", "-c", "print('not canonical')"]}
            ),
            "command 0",
        ),
        (
            "pip_check",
            lambda record: record["command_outcomes"][0].update(
                {"policy_accepted": False}
            ),
            "command 0",
        ),
        (
            "quebec_terraform_validate",
            lambda record: record["stage_summary"].update(
                {"raw_secret": "must-not-be-republished"}
            ),
            "unsafe field set",
        ),
        (
            "quebec_terraform_validate",
            lambda record: record["stage_summary"]["provider_lock"].update(
                {"provider_version": "9.9.9"}
            ),
            "successful inert evidence",
        ),
        (
            "quebec_terraform_validate",
            lambda record: record["stage_summary"]["inert_plan"].update(
                {"resource_action_summary": {"create": 5}}
            ),
            "successful inert evidence",
        ),
        (
            "quebec_terraform_validate",
            lambda record: record["stage_summary"]["inert_plan"].update(
                {"drift_action_summary": {"delete": 2}}
            ),
            "successful inert evidence",
        ),
        (
            "quebec_terraform_validate",
            lambda record: record["stage_summary"]["inert_plan"].update(
                {"test_run_count": 0}
            ),
            "successful inert evidence",
        ),
    ],
)
def test_assembler_rejects_forged_or_unsafe_stage_execution(
    tmp_path: Path,
    stage_id,
    mutate,
    message,
):
    run, artifact, evidence, contract, lockfile = _fixture(tmp_path)
    _rewrite_stage_evidence(evidence, stage_id, mutate)
    with pytest.raises(assembler.CiAdmissionAssemblyError, match=message):
        assembler.assemble_ci_admission(
            run=run,
            artifact=artifact,
            evidence_dir=evidence,
            contract=contract,
            lockfile_path=lockfile,
            release_sha=RELEASE,
            release_tree_sha=TREE,
            protected_branch_verified=True,
        )


def test_assembler_rejects_target_revision_contract_command_substitution(tmp_path: Path):
    run, artifact, evidence, contract, lockfile = _fixture(tmp_path)
    tests_stage = next(stage for stage in contract["stages"] if stage["id"] == "tests")
    tests_stage["commands"] = [["python", "-c", "pass"]]
    with pytest.raises(assembler.CiAdmissionAssemblyError, match="canonical CI contract"):
        assembler.assemble_ci_admission(
            run=run,
            artifact=artifact,
            evidence_dir=evidence,
            contract=contract,
            lockfile_path=lockfile,
            release_sha=RELEASE,
            release_tree_sha=TREE,
            protected_branch_verified=True,
        )


def test_assembler_rejects_coherent_target_revision_provider_policy_substitution(
    tmp_path: Path,
):
    run, artifact, evidence, contract, lockfile = _fixture(tmp_path)
    lockfile.write_text(
        lockfile.read_text(encoding="utf-8").replace("6.49.0", "9.9.9"),
        encoding="utf-8",
    )
    lock_digest = hashlib.sha256(lockfile.read_bytes()).hexdigest()

    stage_path = evidence / "quebec_terraform_validate.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    stage["stage_summary"]["provider_lock"].update(
        {"provider_version": "9.9.9", "lock_sha256": lock_digest}
    )
    stage["record_sha256"] = _canonical_sha256(
        {key: value for key, value in stage.items() if key != "record_sha256"}
    )
    _write(stage_path, stage)

    exact_path = evidence / "exact_head_admission_receipt.json"
    exact = json.loads(exact_path.read_text(encoding="utf-8"))
    exact["quebec_provider_lockfile_sha256"] = lock_digest
    exact["stage_receipts"]["quebec_terraform_validate"].update(
        {
            "record_sha256": stage["record_sha256"],
            "receipt_sha256": hashlib.sha256(stage_path.read_bytes()).hexdigest(),
        }
    )
    exact["receipt_sha256"] = _canonical_sha256(
        {key: value for key, value in exact.items() if key != "receipt_sha256"}
    )
    _write(exact_path, exact)

    policy = json.loads(
        assembler.PROVIDER_LOCK_POLICY_PATH.read_text(encoding="utf-8")
    )
    policy["provider_version"] = "9.9.9"
    policy_path = tmp_path / "substituted-provider-policy.json"
    _write(policy_path, policy)

    with pytest.raises(assembler.CiAdmissionAssemblyError, match="policy is invalid"):
        assembler.assemble_ci_admission(
            run=run,
            artifact=artifact,
            evidence_dir=evidence,
            contract=contract,
            lockfile_path=lockfile,
            provider_lock_policy_path=policy_path,
            release_sha=RELEASE,
            release_tree_sha=TREE,
            protected_branch_verified=True,
        )


@pytest.mark.parametrize(
    ("target", "mutate"),
    [
        (
            "exact",
            lambda receipt: receipt.update({"pr_number": "raw-secret-value"}),
        ),
        (
            "exact",
            lambda receipt: receipt.update({"base_sha": "raw-secret-value"}),
        ),
        (
            "exact",
            lambda receipt: receipt.update(
                {"captured_timestamp": "raw-secret-value"}
            ),
        ),
        (
            "container",
            lambda receipt: receipt.update({"captured_at": "raw-secret-value"}),
        ),
    ],
)
def test_assembler_rejects_unbounded_receipt_metadata(
    tmp_path: Path,
    target,
    mutate,
):
    run, artifact, evidence, contract, lockfile = _fixture(tmp_path)
    path = evidence / (
        "exact_head_admission_receipt.json"
        if target == "exact"
        else "nexus_local_container_build_receipt.json"
    )
    _rewrite_receipt(
        path,
        mutate,
        digest_field="receipt_sha256",
    )
    with pytest.raises(assembler.CiAdmissionAssemblyError):
        assembler.assemble_ci_admission(
            run=run,
            artifact=artifact,
            evidence_dir=evidence,
            contract=contract,
            lockfile_path=lockfile,
            release_sha=RELEASE,
            release_tree_sha=TREE,
            protected_branch_verified=True,
        )


@pytest.mark.parametrize(
    "field",
    [
        "source_context_sha256",
        "source_context_receipt_sha256",
        "dependency_lock_sha256",
        "dockerfile_sha256",
    ],
)
def test_assembler_rejects_unbound_container_input_digests(tmp_path: Path, field):
    run, artifact, evidence, contract, lockfile = _fixture(tmp_path)

    def mutate(receipt):
        receipt[field] = "f" * 64
        if field == "source_context_sha256":
            receipt["image_identity_labels"][
                "ai.aigc.source-context-sha256"
            ] = "f" * 64

    _rewrite_receipt(
        evidence / "nexus_local_container_build_receipt.json",
        mutate,
        digest_field="receipt_sha256",
    )
    with pytest.raises(assembler.CiAdmissionAssemblyError, match="container evidence"):
        assembler.assemble_ci_admission(
            run=run,
            artifact=artifact,
            evidence_dir=evidence,
            contract=contract,
            lockfile_path=lockfile,
            release_sha=RELEASE,
            release_tree_sha=TREE,
            protected_branch_verified=True,
        )


def test_assembler_rejects_coherently_rehashed_non_tree_build_context(tmp_path: Path):
    run, artifact, evidence, contract, lockfile = _fixture(tmp_path)
    context_path = evidence / "nexus_build_context_receipt.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["files"][0]["sha256"] = "f" * 64
    context["manifest_sha256"] = _canonical_sha256(
        {key: value for key, value in context.items() if key != "manifest_sha256"}
    )
    _write(context_path, context)

    def bind_container_to_forged_context(receipt):
        receipt["source_context_sha256"] = context["manifest_sha256"]
        receipt["source_context_receipt_sha256"] = hashlib.sha256(
            context_path.read_bytes()
        ).hexdigest()
        receipt["image_identity_labels"][
            "ai.aigc.source-context-sha256"
        ] = context["manifest_sha256"]

    _rewrite_receipt(
        evidence / "nexus_local_container_build_receipt.json",
        bind_container_to_forged_context,
        digest_field="receipt_sha256",
    )
    with pytest.raises(assembler.CiAdmissionAssemblyError, match="exact-tree evidence"):
        assembler.assemble_ci_admission(
            run=run,
            artifact=artifact,
            evidence_dir=evidence,
            contract=contract,
            lockfile_path=lockfile,
            release_sha=RELEASE,
            release_tree_sha=TREE,
            protected_branch_verified=True,
        )


def test_schema_rejects_extra_fields_at_every_nested_evidence_boundary(tmp_path: Path):
    run, artifact, evidence, contract, lockfile = _fixture(tmp_path)
    admission = assembler.assemble_ci_admission(
        run=run,
        artifact=artifact,
        evidence_dir=evidence,
        contract=contract,
        lockfile_path=lockfile,
        release_sha=RELEASE,
        release_tree_sha=TREE,
        protected_branch_verified=True,
    )
    schema = json.loads(
        Path("schemas/exact_head_ci_admission.schema.json").read_text(encoding="utf-8")
    )
    boundaries = [
        ("exact_head_receipt",),
        ("exact_head_receipt", "toolchain"),
        ("exact_head_receipt", "stage_receipts", "pip_check"),
        ("container_build",),
        ("container_build", "runtime_smoke"),
    ]
    for path in boundaries:
        candidate = json.loads(json.dumps(admission))
        target = candidate
        for part in path:
            target = target[part]
        target["raw_secret"] = "must-not-validate"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(candidate, schema)


def test_collector_workflow_is_read_only_and_exact_main_gated():
    workflow_path = Path(".github/workflows/aigc-ci-admission.yml")
    text = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert workflow["permissions"] == {"actions": "read", "contents": "read"}
    assert "workflow_run.head_branch == 'main'" in text
    assert "workflow_run.conclusion == 'success'" in text
    assert "--protected-main" in text
    assert "actions/artifacts/$artifact_id/zip" in text
    assert "--artifact-archive" in text
    assert "--provider-lock-policy" in text
    assert "id-token: write" not in text
    assert "gcloud " not in text
    assert "terraform apply" not in text


def test_artifact_archive_digest_is_verified_before_safe_extraction(tmp_path: Path):
    _run, artifact, evidence, _contract, _lockfile = _fixture(tmp_path)
    archive_path = tmp_path / "artifact.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in sorted(evidence.iterdir()):
            archive.write(path, arcname=path.name)
    artifact["digest"] = "sha256:" + hashlib.sha256(archive_path.read_bytes()).hexdigest()
    destination = tmp_path / "verified"
    assembler.extract_verified_artifact(
        archive_path,
        artifact=artifact,
        destination=destination,
    )
    assert (destination / "exact_head_admission_receipt.json").is_file()

    tampered = tmp_path / "tampered.zip"
    tampered.write_bytes(archive_path.read_bytes() + b"tamper")
    with pytest.raises(assembler.CiAdmissionAssemblyError, match="digest"):
        assembler.extract_verified_artifact(
            tampered,
            artifact=artifact,
            destination=tmp_path / "rejected",
        )


def test_oversized_artifact_is_rejected_before_content_read(tmp_path: Path, monkeypatch):
    archive_path = tmp_path / "oversized.zip"
    with archive_path.open("wb") as stream:
        stream.seek(50 * 1024 * 1024)
        stream.write(b"x")
    opened = False
    original_open = Path.open

    def observed_open(path, *args, **kwargs):
        nonlocal opened
        if path == archive_path:
            opened = True
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", observed_open)
    with pytest.raises(assembler.CiAdmissionAssemblyError, match="bounded size"):
        assembler.extract_verified_artifact(
            archive_path,
            artifact={"digest": "sha256:" + "0" * 64},
            destination=tmp_path / "rejected-oversized",
        )
    assert opened is False
