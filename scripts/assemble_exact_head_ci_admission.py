from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import PurePosixPath
import re
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "aigc.exact-head-ci-admission.v2"
INNER_SCHEMA_VERSION = "aigc.exact-head-admission-receipt.v2"
CONTAINER_SCHEMA_VERSION = "aigc.nexus-local-container-build.v2"
REPOSITORY = "Lornt1666/AIGC"
WORKFLOW_PATH = ".github/workflows/aigc-ci.yml"
PROVIDER_LOCK_POLICY_PATH = Path(
    "infra/gcp/quebec/ci/lock/provider_lock_policy.json"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PYTHON_BASE_IMAGE_PATTERN = re.compile(r"^python:3\.12\.13-slim-bookworm@sha256:[a-f0-9]{64}$")
SHA40 = re.compile(r"^[a-f0-9]{40}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
TAGGED_SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")
_EXACT_HEAD_FIELDS = {
    "schema_version",
    "repository",
    "pr_number",
    "workflow_event",
    "requested_head_sha",
    "observed_head_sha",
    "tested_tree_sha",
    "base_sha",
    "workflow_revision",
    "workflow_run_number",
    "workflow_run_id",
    "workflow_run_attempt",
    "artifact_name",
    "job_status",
    "canonical_contract_sha256",
    "expected_stage_ids",
    "successful_stage_ids",
    "all_canonical_stages_success",
    "stage_receipts",
    "toolchain",
    "quebec_provider_lockfile_committed",
    "quebec_provider_lockfile_sha256",
    "captured_timestamp",
    "external_authority_granted",
    "external_action_performed",
    "merge_authority_granted",
    "deployment_authority_granted",
    "live_model_call_authority_granted",
    "financial_authority_granted",
    "receipt_sha256",
}
_STAGE_FIELDS = {
    "schema_version",
    "contract_id",
    "contract_sha256",
    "stage_id",
    "target_sha",
    "tested_tree_sha",
    "broker_revision",
    "run_number",
    "run_id",
    "ordered_command_digest",
    "command_outcomes",
    "status",
    "external_action_performed",
    "production_activation_authorized",
    "merge_authority_granted",
    "deployment_authority_granted",
    "live_model_call_authority_granted",
    "financial_authority_granted",
    "record_sha256",
}
_EXPECTED_STAGE_IDS = (
    "pip_check",
    "python_compilation",
    "contracts",
    "orchestration_schema_validation",
    "orchestration_round_trip_validation",
    "redaction",
    "release_secret_scan",
    "procurement_smoke",
    "provider_discovery",
    "terraform_inert",
    "quebec_terraform_validate",
    "nexus_supply_chain",
    "tests",
    "false_authority",
    "readiness",
)
_OUTCOME_FIELDS = {
    "argv",
    "argv_sha256",
    "exit_code",
    "output_sha256",
    "accepted_exit_codes",
    "policy_accepted",
}
_QUEBEC_COMMAND_ROLES = ("fmt", "init", "validate", "test")
_SAFE_TERRAFORM_ACTIONS = {
    "no-op",
    "create",
    "read",
    "update",
    "delete",
    "create,delete",
    "delete,create",
}
_QUEBEC_STAGE_POLICY = {
    "runner_image": "ubuntu-24.04",
    "terraform_version": "1.10.5",
    "terraform_root": "infra/gcp/quebec",
    "provider_lock_policy": "infra/gcp/quebec/ci/lock/provider_lock_policy.json",
    "test_directory": "ci/tftest",
    "inert_test_file": "ci/tftest/inert_authority.tftest.hcl",
    "committed_provider_lock_required": True,
    "native_terraform_test_required": True,
    "machine_readable_test_plan_required": True,
    "isolated_in_memory_test_state_required": True,
    "test_state_event_forbidden": True,
    "zero_managed_resource_changes_required": True,
    "all_test_assertion_runs_pass_required": True,
    "output_only_metadata_initialization_reported_separately": True,
    "backend_initialization_permitted": False,
    "standalone_plan_permitted": False,
    "external_action_permitted": False,
}
_CANONICAL_STATIC_STAGE_COMMANDS: dict[str, list[list[str]]] = {
    "contracts": [
        ["python", "src/aigc.py", "validate"],
        [
            "python",
            "src/aigc.py",
            "validate",
            "--schema",
            "provider_discovery_command_catalog",
            "--path",
            "config/provider_discovery_command_catalog.json",
        ],
        [
            "python",
            "src/aigc.py",
            "validate",
            "--schema",
            "provider_discovery_mock_fixture",
            "--path",
            "config/provider_discovery_mock_fixture.json",
        ],
        ["python", "src/validate_aec_001.py"],
    ],
    "orchestration_schema_validation": [
        [
            "python",
            "scripts/validate_colosseum_persistence.py",
            "--mode",
            "schema",
            "--project-root",
            ".",
        ],
        [
            "python",
            "scripts/validate_governed_orchestration_bundle.py",
            "--mode",
            "schema",
            "--project-root",
            ".",
        ],
    ],
    "orchestration_round_trip_validation": [
        [
            "python",
            "scripts/validate_colosseum_persistence.py",
            "--mode",
            "roundtrip",
            "--project-root",
            ".",
        ],
        [
            "python",
            "scripts/validate_governed_orchestration_bundle.py",
            "--mode",
            "roundtrip",
            "--project-root",
            ".",
        ],
    ],
    "redaction": [
        [
            "python",
            "src/security/redaction_scanner.py",
            "--paths",
            "src",
            "scripts",
            "config",
            "docs",
            "governance",
            "README.md",
            "AGENTS.md",
            "AIGC_MASTER_PROMPT.md",
            "OMEGA_X_CONSTITUTION.md",
            "schemas",
            "tests",
            "reports",
            "Dockerfile",
            "render.yaml",
            "fly.toml",
            "Procfile",
        ]
    ],
    "release_secret_scan": [["python", "scripts/release_secret_scan.py"]],
    "procurement_smoke": [
        [
            "python",
            "src/save_credential_broker_procurement.py",
            "--project-root",
            ".",
            "--config",
            "config/aigc_save_credential_broker.json",
        ],
        [
            "python",
            "src/n8n_workflow_dispatch_bridge_procurement.py",
            "--project-root",
            ".",
            "--config",
            "config/aigc_n8n_workflow_dispatch_bridge.json",
        ],
        [
            "python",
            "src/aigc.py",
            "validate",
            "--schema",
            "save_credential_broker_packet",
            "--path",
            "data/save_credential_broker/aigc_save_credential_broker_packet.json",
        ],
        [
            "python",
            "src/aigc.py",
            "validate",
            "--schema",
            "n8n_workflow_dispatch_bridge_packet",
            "--path",
            "data/n8n_bridge/aigc_n8n_workflow_dispatch_bridge_packet.json",
        ],
    ],
    "provider_discovery": [
        [
            "python",
            "scripts/run_provider_discovery_mock.py",
            "--repository-revision",
            "${REPOSITORY_REVISION}",
            "--created-at",
            "2026-07-15T00:00:00Z",
            "--output-dir",
            "reports/artifacts/provider_discovery_simulation",
        ]
    ],
    "nexus_supply_chain": [["python", "scripts/verify_nexus_supply_chain.py"]],
    "tests": [
        ["python", "-m", "pytest", "tests/colosseum"],
        ["python", "-m", "pytest"],
    ],
    "false_authority": [
        ["python", "scripts/verify_colosseum_false_authority.py"]
    ],
    "readiness": [["python", "src/aigc.py", "readiness"]],
}
_BUILD_CONTEXT_REQUIRED_FILES = {
    "Dockerfile.nexus",
    "cloudbuild.nexus.yaml",
    "requirements.txt",
    "requirements.lock",
    "migrations/003_nexus_provider_runtime_controls.sql",
    "migrations/004_nexus_persisted_authority.sql",
}
_CONTAINER_FIELDS = {
    "schema_version",
    "repository_revision",
    "tested_tree_sha",
    "image_id",
    "image_config_user",
    "image_identity_labels",
    "source_context_sha256",
    "source_context_receipt_sha256",
    "dependency_lock_sha256",
    "python_base_image",
    "dockerfile_sha256",
    "dockerfile",
    "runtime_smoke",
    "release_base_image_status",
    "registry_push_performed",
    "cloud_build_performed",
    "deployment_performed",
    "external_action_performed",
    "captured_at",
    "receipt_sha256",
}


class CiAdmissionAssemblyError(RuntimeError):
    pass


def extract_verified_artifact(
    archive_path: Path,
    *,
    artifact: dict[str, Any],
    destination: Path,
) -> None:
    """Verify GitHub's archive digest, then extract a bounded non-link file set."""

    expected = str(artifact.get("digest") or "")
    try:
        archive_size = archive_path.stat().st_size
    except OSError as exc:
        raise CiAdmissionAssemblyError("retained CI artifact archive is unavailable") from exc
    if archive_size <= 0 or archive_size > 50 * 1024 * 1024:
        raise CiAdmissionAssemblyError("downloaded artifact archive exceeds the bounded size")
    digest = hashlib.sha256()
    try:
        with archive_path.open("rb") as archive_stream:
            for chunk in iter(lambda: archive_stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CiAdmissionAssemblyError("retained CI artifact archive is unavailable") from exc
    observed = "sha256:" + digest.hexdigest()
    if observed != expected:
        raise CiAdmissionAssemblyError("downloaded artifact archive digest does not match GitHub")

    destination.mkdir(parents=True, exist_ok=False)
    total_size = 0
    file_count = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for item in archive.infolist():
                relative = PurePosixPath(item.filename)
                unix_mode = item.external_attr >> 16
                if (
                    not item.filename
                    or "\\" in item.filename
                    or relative.is_absolute()
                    or ".." in relative.parts
                    or stat.S_ISLNK(unix_mode)
                ):
                    raise CiAdmissionAssemblyError("artifact archive contains an unsafe path")
                if item.is_dir():
                    continue
                file_count += 1
                total_size += item.file_size
                if file_count > 1000 or item.file_size > 10 * 1024 * 1024 or total_size > 50 * 1024 * 1024:
                    raise CiAdmissionAssemblyError("artifact archive exceeds extraction limits")
                target = destination.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
    except (OSError, zipfile.BadZipFile) as exc:
        raise CiAdmissionAssemblyError("retained CI artifact is not a valid ZIP archive") from exc


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_rfc3339_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not re.fullmatch(
        r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})$",
        value,
    ):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _terraform_inert_commands() -> list[list[str]]:
    return [
        ["terraform", "-chdir=infra/terraform/gcp", "fmt", "-check", "-recursive"],
        [
            "terraform",
            "-chdir=infra/terraform/gcp",
            "init",
            "-backend=false",
            "-input=false",
        ],
        ["terraform", "-chdir=infra/terraform/gcp", "validate"],
        [
            "terraform",
            "-chdir=infra/terraform/gcp",
            "plan",
            "-input=false",
            "-lock=false",
            "-refresh=false",
            "-var-file=staging.tfvars.example",
            "-out=/tmp/aigc-exact-sha.tfplan",
        ],
        [
            "terraform",
            "-chdir=infra/terraform/gcp",
            "show",
            "-json",
            "/tmp/aigc-exact-sha.tfplan",
        ],
    ]


def _quebec_commands() -> list[list[str]]:
    return [
        ["terraform", "-chdir=infra/gcp/quebec", "fmt", "-check", "-recursive"],
        [
            "terraform",
            "-chdir=infra/gcp/quebec",
            "init",
            "-backend=false",
            "-input=false",
            "-no-color",
            "-lockfile=readonly",
        ],
        ["terraform", "-chdir=infra/gcp/quebec", "validate", "-json"],
        [
            "terraform",
            "-chdir=infra/gcp/quebec",
            "test",
            "-test-directory=ci/tftest",
            "-filter=ci/tftest/inert_authority.tftest.hcl",
            "-json",
            "-verbose",
            "-no-color",
        ],
    ]


def _canonical_stage_definitions() -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for stage_id in _EXPECTED_STAGE_IDS:
        if stage_id == "pip_check":
            definitions.append({"id": stage_id, "runner": "pip_check"})
        elif stage_id == "python_compilation":
            definitions.append({"id": stage_id, "runner": "compileall"})
        elif stage_id == "terraform_inert":
            definitions.append({"id": stage_id, "runner": "terraform_inert"})
        elif stage_id == "quebec_terraform_validate":
            definitions.append(
                {
                    "id": stage_id,
                    "runner": "quebec_terraform_validate",
                    "policy": _QUEBEC_STAGE_POLICY,
                }
            )
        else:
            definitions.append(
                {"id": stage_id, "commands": _CANONICAL_STATIC_STAGE_COMMANDS[stage_id]}
            )
    return definitions


def _expected_stage_commands(
    stage: dict[str, Any],
    *,
    release_sha: str,
) -> list[list[str]]:
    stage_id = stage.get("id")
    if stage_id == "pip_check":
        commands: Any = [["python", "-m", "pip", "check"]]
    elif stage_id == "python_compilation":
        commands = [["python", "-m", "compileall", "-q", "src", "scripts", "tests"]]
    elif stage_id == "terraform_inert":
        commands = _terraform_inert_commands()
    elif stage_id == "quebec_terraform_validate":
        commands = _quebec_commands()
    else:
        commands = _CANONICAL_STATIC_STAGE_COMMANDS.get(str(stage_id))
    if (
        not isinstance(commands, list)
        or not commands
        or any(
            not isinstance(command, list)
            or not command
            or any(not isinstance(part, str) or not part for part in command)
            for command in commands
        )
    ):
        raise CiAdmissionAssemblyError(
            f"canonical stage {stage.get('id')} has invalid command definitions"
        )
    return [
        [part.replace("${REPOSITORY_REVISION}", release_sha) for part in command]
        for command in commands
    ]


def _safe_success_diagnostics(stage_id: str) -> dict[str, Any] | None:
    if stage_id in {"redaction", "release_secret_scan"}:
        return {"finding_count": 0, "findings": [], "truncated": False}
    if stage_id == "tests":
        return {
            "failed_or_error_test_count": 0,
            "failed_or_error_tests": [],
            "truncated": False,
        }
    return None


def _is_nonnegative_int(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _valid_action_summary(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and all(key in _SAFE_TERRAFORM_ACTIONS for key in value)
        and all(_is_nonnegative_int(count) for count in value.values())
    )


def _provider_lock_evidence(
    *,
    lockfile_path: Path,
    policy_path: Path,
) -> dict[str, Any]:
    policy = _load_object(policy_path, label="Québec provider-lock policy")
    expected_policy_fields = {
        "schema_version",
        "lockfile_path",
        "provider_source",
        "provider_version",
        "bootstrap_command",
        "bootstrap_artifact_path",
        "committed_lockfile_required_for_pass",
        "handwritten_lockfile_permitted",
    }
    if (
        set(policy) != expected_policy_fields
        or policy.get("schema_version") != "aigc.terraform-provider-lock-policy.v1"
        or policy.get("lockfile_path") != "infra/gcp/quebec/.terraform.lock.hcl"
        or policy.get("provider_source") != "registry.terraform.io/hashicorp/google"
        or policy.get("provider_version") != "6.49.0"
        or policy.get("bootstrap_command")
        != "terraform -chdir=infra/gcp/quebec init -backend=false -input=false -no-color"
        or policy.get("bootstrap_artifact_path")
        != "quebec_terraform_lock_bootstrap/terraform.lock.hcl.generated"
        or policy.get("committed_lockfile_required_for_pass") is not True
        or policy.get("handwritten_lockfile_permitted") is not False
    ):
        raise CiAdmissionAssemblyError("Québec provider-lock policy is invalid")
    try:
        lockfile_bytes = lockfile_path.read_bytes()
        lockfile_text = lockfile_bytes.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise CiAdmissionAssemblyError("committed Québec provider lockfile is unavailable") from exc
    provider_source = str(policy["provider_source"])
    provider_version = str(policy["provider_version"])
    match = re.search(
        rf'^provider "{re.escape(provider_source)}" \{{(?P<body>.*?)^\}}',
        lockfile_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise CiAdmissionAssemblyError("Québec lockfile omits its policy-pinned provider")
    body = match.group("body")
    if (
        re.search(
            rf'^\s*version\s*=\s*"{re.escape(provider_version)}"\s*$',
            body,
            flags=re.MULTILINE,
        )
        is None
        or re.search(
            rf'^\s*constraints\s*=\s*"(?:=\s*)?{re.escape(provider_version)}"\s*$',
            body,
            flags=re.MULTILINE,
        )
        is None
    ):
        raise CiAdmissionAssemblyError("Québec lockfile violates its exact provider version policy")
    h1_count = len(re.findall(r'"h1:[A-Za-z0-9+/=]+"', body))
    zh_count = len(re.findall(r'"zh:[a-f0-9]{64}"', body))
    if h1_count <= 0 or zh_count <= 0:
        raise CiAdmissionAssemblyError("Québec lockfile lacks signed provider checksums")
    return {
        "lock_sha256": hashlib.sha256(lockfile_bytes).hexdigest(),
        "provider_source": provider_source,
        "provider_version": provider_version,
        "h1_checksum_count": h1_count,
        "zh_checksum_count": zh_count,
    }


def _validate_quebec_summary(
    summary: Any,
    *,
    expected_provider_lock: dict[str, Any],
) -> None:
    expected_fields = {
        "terraform_root",
        "lockfile_path",
        "lockfile_committed_at_start",
        "lockfile_readonly_mode",
        "machine_readable_test_plan",
        "isolated_in_memory_test_state",
        "backend_initialized",
        "provider_or_cloud_mutation_performed",
        "provider_lock",
        "validate",
        "inert_plan",
        "lockfile_unchanged",
        "status",
        "failure_reason",
    }
    if not isinstance(summary, dict) or set(summary) != expected_fields:
        raise CiAdmissionAssemblyError("Québec stage summary has an unsafe field set")
    provider_lock = summary.get("provider_lock")
    validation = summary.get("validate")
    inert_plan = summary.get("inert_plan")
    if (
        summary.get("terraform_root") != "infra/gcp/quebec"
        or summary.get("lockfile_path") != "infra/gcp/quebec/.terraform.lock.hcl"
        or summary.get("lockfile_committed_at_start") is not True
        or summary.get("lockfile_readonly_mode") is not True
        or summary.get("machine_readable_test_plan") is not True
        or summary.get("isolated_in_memory_test_state") is not True
        or summary.get("backend_initialized") is not False
        or summary.get("provider_or_cloud_mutation_performed") is not False
        or summary.get("lockfile_unchanged") is not True
        or summary.get("status") != "success"
        or summary.get("failure_reason") is not None
        or provider_lock != expected_provider_lock
        or not isinstance(validation, dict)
        or set(validation) != {"valid", "error_count", "warning_count"}
        or validation.get("valid") is not True
        or validation.get("error_count") != 0
        or not _is_nonnegative_int(validation.get("warning_count"))
        or not isinstance(inert_plan, dict)
        or set(inert_plan)
        != {
            "managed_resource_change_count",
            "resource_drift_change_count",
            "resource_action_summary",
            "drift_action_summary",
            "output_action_summary",
            "output_metadata_change_count",
            "test_file_count",
            "test_run_count",
            "test_plan_count",
            "diagnostic_warning_count",
            "all_assertion_runs_passed",
            "machine_readable_test_plan_verified",
            "isolated_in_memory_test_state",
            "zero_managed_resource_changes",
        }
        or inert_plan.get("managed_resource_change_count") != 0
        or inert_plan.get("resource_drift_change_count") != 0
        or not _valid_action_summary(inert_plan.get("resource_action_summary"))
        or not _valid_action_summary(inert_plan.get("drift_action_summary"))
        or not _valid_action_summary(inert_plan.get("output_action_summary"))
        or sum(inert_plan["resource_action_summary"].values())
        != inert_plan["managed_resource_change_count"]
        or sum(inert_plan["drift_action_summary"].values())
        != inert_plan["resource_drift_change_count"]
        or not _is_nonnegative_int(inert_plan.get("output_metadata_change_count"))
        or inert_plan["output_metadata_change_count"]
        != sum(inert_plan["output_action_summary"].values())
        or inert_plan.get("test_file_count") != 1
        or inert_plan.get("test_run_count") != 1
        or inert_plan.get("test_plan_count") != 1
        or not _is_nonnegative_int(inert_plan.get("diagnostic_warning_count"))
        or inert_plan.get("all_assertion_runs_passed") is not True
        or inert_plan.get("machine_readable_test_plan_verified") is not True
        or inert_plan.get("isolated_in_memory_test_state") is not True
        or inert_plan.get("zero_managed_resource_changes") is not True
    ):
        raise CiAdmissionAssemblyError("Québec stage summary is not successful inert evidence")


def _validate_stage_execution(
    record: dict[str, Any],
    *,
    stage: dict[str, Any],
    release_sha: str,
    expected_provider_lock: dict[str, Any],
) -> None:
    stage_id = str(stage.get("id") or "")
    outcomes = record.get("command_outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        raise CiAdmissionAssemblyError(f"stage {stage_id} has no command evidence")

    if stage_id == "quebec_terraform_validate":
        if len(outcomes) != len(_QUEBEC_COMMAND_ROLES):
            raise CiAdmissionAssemblyError("Québec stage command evidence is incomplete")

    expected_commands = _expected_stage_commands(
        stage,
        release_sha=release_sha,
    )
    if len(outcomes) != len(expected_commands):
        raise CiAdmissionAssemblyError(f"stage {stage_id} command count is not canonical")

    expected_diagnostics = _safe_success_diagnostics(stage_id)
    expected_hashes: list[str] = []
    for index, (outcome, expected_argv) in enumerate(zip(outcomes, expected_commands)):
        if not isinstance(outcome, dict):
            raise CiAdmissionAssemblyError(f"stage {stage_id} command outcome is not an object")
        expected_fields = set(_OUTCOME_FIELDS)
        if expected_diagnostics is not None:
            expected_fields.add("sanitized_diagnostics")
        if stage_id == "quebec_terraform_validate":
            expected_fields.add("command_role")
        expected_accepted = [0]
        expected_hash = _canonical_sha256(expected_argv)
        exit_code = outcome.get("exit_code")
        if (
            set(outcome) != expected_fields
            or outcome.get("argv") != expected_argv
            or outcome.get("argv_sha256") != expected_hash
            or not SHA256.fullmatch(str(outcome.get("output_sha256") or ""))
            or isinstance(exit_code, bool)
            or not isinstance(exit_code, int)
            or exit_code not in expected_accepted
            or outcome.get("accepted_exit_codes") != expected_accepted
            or outcome.get("policy_accepted") is not True
            or (
                expected_diagnostics is not None
                and outcome.get("sanitized_diagnostics") != expected_diagnostics
            )
            or (
                stage_id == "quebec_terraform_validate"
                and outcome.get("command_role") != _QUEBEC_COMMAND_ROLES[index]
            )
        ):
            raise CiAdmissionAssemblyError(
                f"stage {stage_id} command {index} is not exact successful evidence"
            )
        expected_hashes.append(expected_hash)

    if record.get("ordered_command_digest") != _canonical_sha256(expected_hashes):
        raise CiAdmissionAssemblyError(f"stage {stage_id} ordered command digest is invalid")
    if stage_id == "quebec_terraform_validate":
        _validate_quebec_summary(
            record.get("stage_summary"),
            expected_provider_lock=expected_provider_lock,
        )
    elif "stage_summary" in record:
        raise CiAdmissionAssemblyError(f"stage {stage_id} has an unexpected stage summary")


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CiAdmissionAssemblyError(f"{label} is not readable canonical JSON") from exc
    if not isinstance(value, dict):
        raise CiAdmissionAssemblyError(f"{label} must be a JSON object")
    return value


def _verified_record_hash(record: dict[str, Any], *, label: str) -> None:
    recorded = record.get("record_sha256")
    unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
    if not isinstance(recorded, str) or recorded != _canonical_sha256(unsigned):
        raise CiAdmissionAssemblyError(f"{label} record_sha256 is invalid")


def _verified_receipt_hash(receipt: dict[str, Any], *, label: str) -> None:
    recorded = receipt.get("receipt_sha256")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if not isinstance(recorded, str) or recorded != _canonical_sha256(unsigned):
        raise CiAdmissionAssemblyError(f"{label} receipt_sha256 is invalid")


def _git_blob_bytes(object_sha: str) -> bytes:
    completed = subprocess.run(
        ["git", "cat-file", "blob", object_sha],
        cwd=REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise CiAdmissionAssemblyError("exact build-context Git blob is unavailable")
    return completed.stdout


def _build_context_tree_entries(release_sha: str) -> list[dict[str, str]]:
    completed = subprocess.run(
        [
            "git",
            "ls-tree",
            "-r",
            "-z",
            release_sha,
            "--",
            *sorted(_BUILD_CONTEXT_REQUIRED_FILES),
            "src/",
        ],
        cwd=REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise CiAdmissionAssemblyError("exact release build-context tree is unavailable")
    records: list[dict[str, str]] = []
    for raw_record in completed.stdout.split(b"\0"):
        if not raw_record:
            continue
        try:
            metadata, encoded_path = raw_record.split(b"\t", 1)
            mode, object_type, object_sha = metadata.decode("ascii").split(" ", 2)
            path = encoded_path.decode("utf-8")
        except (UnicodeError, ValueError) as exc:
            raise CiAdmissionAssemblyError("exact build-context Git tree is malformed") from exc
        relative = PurePosixPath(path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or object_type != "blob"
            or mode not in {"100644", "100755"}
            or not SHA40.fullmatch(object_sha)
            or (
                path not in _BUILD_CONTEXT_REQUIRED_FILES
                and not path.startswith("src/")
            )
        ):
            raise CiAdmissionAssemblyError("exact build-context Git entry is unsafe")
        records.append(
            {
                "path": path,
                "git_blob_sha": object_sha,
                "mode": mode,
                "sha256": hashlib.sha256(_git_blob_bytes(object_sha)).hexdigest(),
            }
        )
    records.sort(key=lambda item: item["path"])
    paths = {item["path"] for item in records}
    if (
        not _BUILD_CONTEXT_REQUIRED_FILES.issubset(paths)
        or not any(path.startswith("src/") for path in paths)
        or len(paths) != len(records)
    ):
        raise CiAdmissionAssemblyError("exact release build context is incomplete")
    return records


def _validate_build_context_receipt(
    *,
    evidence_dir: Path,
    release_sha: str,
    release_tree_sha: str,
) -> tuple[dict[str, Any], str]:
    path = evidence_dir / "nexus_build_context_receipt.json"
    manifest = _load_object(path, label="Nexus build-context receipt")
    expected_fields = {
        "schema_version",
        "repository",
        "release_sha",
        "release_tree_sha",
        "file_count",
        "files",
        "ignored_worktree_files_included",
        "manifest_sha256",
    }
    expected_records = _build_context_tree_entries(release_sha)
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if (
        set(manifest) != expected_fields
        or manifest.get("schema_version") != "aigc.nexus-build-context-manifest.v1"
        or manifest.get("repository") != REPOSITORY
        or manifest.get("release_sha") != release_sha
        or manifest.get("release_tree_sha") != release_tree_sha
        or isinstance(manifest.get("file_count"), bool)
        or manifest.get("file_count") != len(expected_records)
        or manifest.get("files") != expected_records
        or manifest.get("ignored_worktree_files_included") is not False
        or manifest.get("manifest_sha256") != _canonical_sha256(unsigned)
    ):
        raise CiAdmissionAssemblyError("Nexus build-context receipt is not exact-tree evidence")
    try:
        receipt_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CiAdmissionAssemblyError("Nexus build-context receipt is unavailable") from exc
    return manifest, receipt_sha256


def assemble_ci_admission(
    *,
    run: dict[str, Any],
    artifact: dict[str, Any],
    evidence_dir: Path,
    contract: dict[str, Any],
    lockfile_path: Path,
    provider_lock_policy_path: Path = PROVIDER_LOCK_POLICY_PATH,
    release_sha: str,
    release_tree_sha: str,
    protected_branch_verified: bool,
) -> dict[str, Any]:
    if not SHA40.fullmatch(release_sha) or not SHA40.fullmatch(release_tree_sha):
        raise CiAdmissionAssemblyError("release SHA and tree SHA must be exact 40-character hashes")
    run_id = run.get("id")
    head_repository = run.get("head_repository")
    if (
        isinstance(run_id, bool)
        or not isinstance(run_id, int)
        or run_id <= 0
        or run.get("name") != "AIGC CI"
        or run.get("path") not in {WORKFLOW_PATH, f"{WORKFLOW_PATH}@main"}
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("event") != "push"
        or run.get("head_branch") != "main"
        or run.get("head_sha") != release_sha
        or not isinstance(head_repository, dict)
        or head_repository.get("full_name") != REPOSITORY
        or run.get("html_url")
        != f"https://github.com/{REPOSITORY}/actions/runs/{run_id}"
        or protected_branch_verified is not True
    ):
        raise CiAdmissionAssemblyError(
            "workflow run is not a successful exact-head protected-main AIGC CI run"
        )

    artifact_name = f"aigc-colosseum-orchestration-exact-head-{release_sha}"
    if (
        isinstance(artifact.get("id"), bool)
        or not isinstance(artifact.get("id"), int)
        or artifact["id"] <= 0
        or not isinstance(artifact.get("workflow_run"), dict)
        or artifact["workflow_run"].get("id") != run_id
        or artifact["workflow_run"].get("head_branch") != "main"
        or artifact["workflow_run"].get("head_sha") != release_sha
        or artifact.get("name") != artifact_name
        or artifact.get("expired") is not False
        or not TAGGED_SHA256.fullmatch(str(artifact.get("digest") or ""))
    ):
        raise CiAdmissionAssemblyError("retained CI artifact identity or digest is invalid")

    stage_definitions = contract.get("stages")
    if not isinstance(stage_definitions, list) or not stage_definitions:
        raise CiAdmissionAssemblyError("canonical CI contract contains no stages")
    expected_stage_ids = [item.get("id") for item in stage_definitions if isinstance(item, dict)]
    if (
        set(contract)
        != {
            "schema_version",
            "contract_id",
            "production_activation_authorized",
            "external_action_authorized",
            "stages",
        }
        or contract.get("schema_version") != "1.2.0"
        or contract.get("contract_id") != "AIGC-CI-EXACT-SHA-V1"
        or contract.get("production_activation_authorized") is not False
        or contract.get("external_action_authorized") is not False
        or len(expected_stage_ids) != len(stage_definitions)
        or any(not isinstance(value, str) or not value for value in expected_stage_ids)
        or len(set(expected_stage_ids)) != len(expected_stage_ids)
        or expected_stage_ids != list(_EXPECTED_STAGE_IDS)
        or stage_definitions != _canonical_stage_definitions()
    ):
        raise CiAdmissionAssemblyError("canonical CI contract is invalid or grants authority")

    exact_head = _load_object(
        evidence_dir / "exact_head_admission_receipt.json",
        label="exact-head receipt",
    )
    _verified_receipt_hash(exact_head, label="exact-head receipt")
    toolchain = exact_head.get("toolchain")
    if (
        set(exact_head) != _EXACT_HEAD_FIELDS
        or exact_head.get("schema_version") != INNER_SCHEMA_VERSION
        or exact_head.get("repository") != REPOSITORY
        or exact_head.get("pr_number") != 0
        or exact_head.get("workflow_event") != "push"
        or exact_head.get("requested_head_sha") != release_sha
        or exact_head.get("observed_head_sha") != release_sha
        or exact_head.get("tested_tree_sha") != release_tree_sha
        or exact_head.get("base_sha") != ""
        or exact_head.get("workflow_revision") != release_sha
        or exact_head.get("workflow_run_id") != run_id
        or exact_head.get("artifact_name") != artifact_name
        or exact_head.get("job_status") != "success"
        or exact_head.get("expected_stage_ids") != expected_stage_ids
        or exact_head.get("successful_stage_ids") != expected_stage_ids
        or exact_head.get("all_canonical_stages_success") is not True
        or exact_head.get("quebec_provider_lockfile_committed") is not True
        or not SHA256.fullmatch(str(exact_head.get("quebec_provider_lockfile_sha256") or ""))
        or not _is_rfc3339_timestamp(exact_head.get("captured_timestamp"))
        or exact_head.get("workflow_run_number") != run.get("run_number")
        or exact_head.get("workflow_run_attempt") != run.get("run_attempt")
        or toolchain
        != {
            "runner": "ubuntu-24.04",
            "python": "3.12.13",
            "terraform": "1.10.5",
            "postgres_service_image": (
                "postgres:16.14-alpine3.24@sha256:"
                "57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777"
            ),
        }
        or exact_head.get("external_action_performed") is not False
        or any(
            exact_head.get(flag) is not False
            for flag in (
                "external_authority_granted",
                "merge_authority_granted",
                "deployment_authority_granted",
                "live_model_call_authority_granted",
                "financial_authority_granted",
            )
        )
    ):
        raise CiAdmissionAssemblyError("exact-head receipt is not bound to the completed run")
    contract_digest = _canonical_sha256(contract)
    if exact_head.get("canonical_contract_sha256") != contract_digest:
        raise CiAdmissionAssemblyError("exact-head receipt canonical contract digest is stale")
    expected_provider_lock = _provider_lock_evidence(
        lockfile_path=lockfile_path,
        policy_path=provider_lock_policy_path,
    )
    lockfile_digest = str(expected_provider_lock["lock_sha256"])
    if exact_head.get("quebec_provider_lockfile_sha256") != lockfile_digest:
        raise CiAdmissionAssemblyError("Québec provider lockfile digest is stale")

    stage_records: list[dict[str, Any]] = []
    retained_stage_receipts = exact_head.get("stage_receipts")
    if not isinstance(retained_stage_receipts, dict) or set(retained_stage_receipts) != set(expected_stage_ids):
        raise CiAdmissionAssemblyError("exact-head stage receipt inventory is incomplete")
    for stage_id in expected_stage_ids:
        path = evidence_dir / f"{stage_id}.json"
        record = _load_object(path, label=f"stage {stage_id}")
        _verified_record_hash(record, label=f"stage {stage_id}")
        retained = retained_stage_receipts.get(stage_id)
        if (
            set(record) not in (_STAGE_FIELDS, _STAGE_FIELDS | {"stage_summary"})
            or record.get("schema_version") != "1.2.0"
            or record.get("contract_id") != contract.get("contract_id")
            or record.get("contract_sha256") != contract_digest
            or record.get("stage_id") != stage_id
            or record.get("status") != "success"
            or record.get("target_sha") != release_sha
            or record.get("tested_tree_sha") != release_tree_sha
            or record.get("run_id") != run_id
            or record.get("run_number") != run.get("run_number")
            or record.get("broker_revision") != release_sha
            or record.get("external_action_performed") is not False
            or record.get("production_activation_authorized") is not False
            or record.get("merge_authority_granted") is not False
            or record.get("deployment_authority_granted") is not False
            or record.get("live_model_call_authority_granted") is not False
            or record.get("financial_authority_granted") is not False
            or not isinstance(record.get("command_outcomes"), list)
            or not SHA256.fullmatch(str(record.get("ordered_command_digest") or ""))
            or not isinstance(retained, dict)
            or set(retained) != {"present", "status", "receipt_sha256", "record_sha256"}
            or retained.get("present") is not True
            or retained.get("status") != "success"
            or retained.get("record_sha256") != record.get("record_sha256")
            or retained.get("receipt_sha256") != hashlib.sha256(path.read_bytes()).hexdigest()
        ):
            raise CiAdmissionAssemblyError(f"stage {stage_id} is not exact successful evidence")
        _validate_stage_execution(
            record,
            stage=stage_definitions[expected_stage_ids.index(stage_id)],
            release_sha=release_sha,
            expected_provider_lock=expected_provider_lock,
        )
        stage_records.append(record)

    context_manifest, context_receipt_sha256 = _validate_build_context_receipt(
        evidence_dir=evidence_dir,
        release_sha=release_sha,
        release_tree_sha=release_tree_sha,
    )
    context_files = {
        item["path"]: item
        for item in context_manifest["files"]
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    container = _load_object(
        evidence_dir / "nexus_local_container_build_receipt.json",
        label="local container receipt",
    )
    _verified_receipt_hash(container, label="local container receipt")
    runtime_smoke = container.get("runtime_smoke")
    python_base_image = container.get("python_base_image")
    if (
        set(container) != _CONTAINER_FIELDS
        or container.get("schema_version") != CONTAINER_SCHEMA_VERSION
        or container.get("repository_revision") != release_sha
        or container.get("tested_tree_sha") != release_tree_sha
        or container.get("image_config_user") != "aigc"
        or not TAGGED_SHA256.fullmatch(str(container.get("image_id") or ""))
        or not PYTHON_BASE_IMAGE_PATTERN.fullmatch(str(python_base_image or ""))
        or container.get("source_context_sha256")
        != context_manifest.get("manifest_sha256")
        or container.get("source_context_receipt_sha256")
        != context_receipt_sha256
        or container.get("dependency_lock_sha256")
        != context_files["requirements.lock"]["sha256"]
        or container.get("dockerfile_sha256")
        != context_files["Dockerfile.nexus"]["sha256"]
        or container.get("image_identity_labels")
        != {
            "org.opencontainers.image.revision": release_sha,
            "ai.aigc.source-context-sha256": container.get("source_context_sha256"),
        }
        or any(
            not SHA256.fullmatch(str(container.get(field) or ""))
            for field in (
                "source_context_sha256",
                "source_context_receipt_sha256",
                "dependency_lock_sha256",
                "dockerfile_sha256",
            )
        )
        or container.get("dockerfile") != "Dockerfile.nexus"
        or container.get("release_base_image_status") != "immutable_default_verified"
        or not _is_rfc3339_timestamp(container.get("captured_at"))
        or not isinstance(runtime_smoke, dict)
        or set(runtime_smoke)
        != {
            "health_contract_passed",
            "health_response_sha256",
            "non_root",
            "runtime_uid",
            "read_only_root_filesystem",
            "network_mode",
            "capabilities_dropped",
            "no_new_privileges",
            "live_provider_execution_enabled",
            "production_activation",
            "live_model_call_performed",
        }
        or runtime_smoke.get("health_contract_passed") is not True
        or not SHA256.fullmatch(str(runtime_smoke.get("health_response_sha256") or ""))
        or runtime_smoke.get("non_root") is not True
        or isinstance(runtime_smoke.get("runtime_uid"), bool)
        or not isinstance(runtime_smoke.get("runtime_uid"), int)
        or runtime_smoke["runtime_uid"] <= 0
        or runtime_smoke.get("read_only_root_filesystem") is not True
        or runtime_smoke.get("network_mode") != "none"
        or runtime_smoke.get("capabilities_dropped") != ["ALL"]
        or runtime_smoke.get("no_new_privileges") is not True
        or runtime_smoke.get("live_provider_execution_enabled") is not False
        or runtime_smoke.get("production_activation") is not False
        or runtime_smoke.get("live_model_call_performed") is not False
        or any(
            container.get(flag) is not False
            for flag in (
                "registry_push_performed",
                "cloud_build_performed",
                "deployment_performed",
                "external_action_performed",
            )
        )
    ):
        raise CiAdmissionAssemblyError("local container evidence is unsafe or incomplete")

    return {
        "schema_version": SCHEMA_VERSION,
        "workflow_run": {
            "id": run_id,
            "repository": REPOSITORY,
            "workflow_path": WORKFLOW_PATH,
            "status": "completed",
            "conclusion": "success",
            "head_sha": release_sha,
            "event": "push",
            "head_branch": "main",
            "head_repository_full_name": REPOSITORY,
            "protected_branch_verified": True,
            "html_url": f"https://github.com/{REPOSITORY}/actions/runs/{run_id}",
        },
        "artifact": {
            "id": artifact["id"],
            "name": artifact_name,
            "digest": artifact["digest"],
            "expired": False,
        },
        "exact_head_receipt": exact_head,
        "stage_records": stage_records,
        "container_build": container,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assemble a verified exact-head CI admission from a completed GitHub run."
    )
    parser.add_argument("--run-metadata", type=Path, required=True)
    parser.add_argument("--artifact-metadata", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--evidence-dir", type=Path)
    source.add_argument("--artifact-archive", type=Path)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--lockfile", type=Path, required=True)
    parser.add_argument(
        "--provider-lock-policy",
        type=Path,
        default=PROVIDER_LOCK_POLICY_PATH,
    )
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--release-tree-sha", required=True)
    parser.add_argument("--protected-main", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    run = _load_object(args.run_metadata, label="workflow run metadata")
    artifact = _load_object(args.artifact_metadata, label="artifact metadata")
    contract = _load_object(args.contract, label="canonical CI contract")
    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        evidence_dir = args.evidence_dir
        if args.artifact_archive is not None:
            temporary = tempfile.TemporaryDirectory(prefix="aigc-ci-admission-")
            evidence_dir = Path(temporary.name, "evidence")
            extract_verified_artifact(
                args.artifact_archive,
                artifact=artifact,
                destination=evidence_dir,
            )
        assert evidence_dir is not None
        admission = assemble_ci_admission(
            run=run,
            artifact=artifact,
            evidence_dir=evidence_dir,
            contract=contract,
            lockfile_path=args.lockfile,
            provider_lock_policy_path=args.provider_lock_policy,
            release_sha=args.release_sha,
            release_tree_sha=args.release_tree_sha,
            protected_branch_verified=args.protected_main,
        )
    finally:
        if temporary is not None:
            temporary.cleanup()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(admission, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "release_sha": args.release_sha,
                "release_tree_sha": args.release_tree_sha,
                "workflow_run_id": admission["workflow_run"]["id"],
                "artifact_id": admission["artifact"]["id"],
                "ci_admission_sha256": _canonical_sha256(admission),
                "external_action_performed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
