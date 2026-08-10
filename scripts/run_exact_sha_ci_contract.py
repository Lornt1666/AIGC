from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


EXPECTED_STAGES = [
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
]

_SCANNER_LINE = re.compile(
    r"^(critical|high):\s+(.+):(\d+)\s+matched\s+(.+)$"
)
_QUEBEC_ROOT = Path("infra/gcp/quebec")
_QUEBEC_LOCK = _QUEBEC_ROOT / ".terraform.lock.hcl"
_QUEBEC_LOCK_POLICY = _QUEBEC_ROOT / "ci/lock/provider_lock_policy.json"
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


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def atomic_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _safe_diagnostics(stage_id: str, output: str) -> dict[str, object] | None:
    """Retain only non-sensitive identifiers; never retain matched/asserted values."""
    if stage_id == "redaction":
        findings: list[dict[str, object]] = []
        for raw_line in output.splitlines():
            match = _SCANNER_LINE.match(raw_line.strip())
            if not match:
                continue
            severity, path, line_number, pattern = match.groups()
            findings.append(
                {
                    "severity": severity,
                    "path": path,
                    "line_number": int(line_number),
                    "pattern": pattern,
                }
            )
        return {
            "finding_count": len(findings),
            "findings": findings[:100],
            "truncated": len(findings) > 100,
        }
    if stage_id == "release_secret_scan":
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return {
                "finding_count": None,
                "findings": [],
                "parse_error": True,
            }
        safe_findings = [
            {
                "severity": item.get("severity"),
                "path": item.get("path"),
                "line_number": item.get("line_number"),
                "pattern": item.get("pattern"),
            }
            for item in (payload.get("findings") or [])[:100]
            if isinstance(item, dict)
        ]
        count = payload.get("finding_count")
        return {
            "finding_count": count,
            "findings": safe_findings,
            "truncated": isinstance(count, int) and count > len(safe_findings),
        }
    if stage_id == "tests":
        node_ids: list[str] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line.startswith(("FAILED ", "ERROR ")):
                continue
            remainder = line.split(" ", 1)[1]
            node_id = remainder.split(" - ", 1)[0].strip()
            if node_id and node_id not in node_ids:
                node_ids.append(node_id)
        return {
            "failed_or_error_test_count": len(node_ids),
            "failed_or_error_tests": node_ids[:100],
            "truncated": len(node_ids) > 100,
        }
    return None


def _execute_command(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    *,
    stage_id: str,
    accepted_exit_codes: frozenset[int] = frozenset({0}),
) -> tuple[dict[str, object], str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    outcome: dict[str, object] = {
        "argv": command,
        "argv_sha256": sha256(canonical(command)).hexdigest(),
        "exit_code": completed.returncode,
        "output_sha256": sha256(completed.stdout.encode()).hexdigest(),
        "accepted_exit_codes": sorted(accepted_exit_codes),
        "policy_accepted": completed.returncode in accepted_exit_codes,
    }
    diagnostics = _safe_diagnostics(stage_id, completed.stdout)
    if diagnostics is not None:
        outcome["sanitized_diagnostics"] = diagnostics
    return outcome, completed.stdout


def run_command(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    *,
    stage_id: str,
) -> dict[str, object]:
    outcome, _ = _execute_command(
        command,
        cwd,
        env,
        stage_id=stage_id,
    )
    return outcome


def terraform_commands() -> list[list[str]]:
    return [
        [
            "terraform",
            "-chdir=infra/terraform/gcp",
            "fmt",
            "-check",
            "-recursive",
        ],
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


def quebec_terraform_commands(*, lockfile_readonly: bool) -> list[list[str]]:
    """Return the native, backend-free Québec validation command sequence.

    The production root intentionally declares a GCS backend. ``init
    -backend=false`` is sufficient for ``validate`` and ``terraform test``, but
    a subsequent standalone ``plan`` refuses to run until that backend is
    initialized. The plan-only test uses Terraform's isolated in-memory test
    state and emits its plan as machine-readable JSON, so CI can verify the
    inert graph without contacting or configuring the production backend.
    """
    init_command = [
        "terraform",
        "-chdir=infra/gcp/quebec",
        "init",
        "-backend=false",
        "-input=false",
        "-no-color",
    ]
    if lockfile_readonly:
        init_command.append("-lockfile=readonly")
    return [
        [
            "terraform",
            "-chdir=infra/gcp/quebec",
            "fmt",
            "-check",
            "-recursive",
        ],
        init_command,
        [
            "terraform",
            "-chdir=infra/gcp/quebec",
            "validate",
            "-json",
        ],
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


def stage_commands(
    stage: dict,
    *,
    lockfile_readonly: bool = True,
) -> list[list[str]]:
    runner = stage.get("runner")
    if runner == "terraform_inert":
        return terraform_commands()
    if runner == "quebec_terraform_validate":
        return quebec_terraform_commands(lockfile_readonly=lockfile_readonly)
    if runner == "pytest":
        return [["python", "-m", "pytest"]]
    if runner == "pip_check":
        return [["python", "-m", "pip", "check"]]
    if runner == "compileall":
        return [
            [
                "python",
                "-m",
                "compileall",
                "-q",
                "src",
                "scripts",
                "tests",
            ]
        ]
    return stage.get("commands") or []


def _git_tracks(project_root: Path, relative_path: Path) -> bool:
    completed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative_path.as_posix()],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def validate_provider_lock(
    lock_path: Path,
    policy_path: Path,
) -> dict[str, object]:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("schema_version") != "aigc.terraform-provider-lock-policy.v1":
        raise ValueError("unsupported Québec provider-lock policy")
    text = lock_path.read_text(encoding="utf-8")
    provider = policy["provider_source"]
    expected_version = policy["provider_version"]
    match = re.search(
        rf'^provider "{re.escape(provider)}" \{{(?P<body>.*?)^\}}',
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise ValueError("Québec lockfile is missing the required Google provider")
    body = match.group("body")
    if re.search(
        rf'^\s*version\s*=\s*"{re.escape(expected_version)}"\s*$',
        body,
        flags=re.MULTILINE,
    ) is None:
        raise ValueError("Québec lockfile does not pin the required provider version")
    if re.search(
        rf'^\s*constraints\s*=\s*"(?:=\s*)?{re.escape(expected_version)}"\s*$',
        body,
        flags=re.MULTILINE,
    ) is None:
        raise ValueError("Québec lockfile does not retain the exact provider constraint")
    h1_hashes = re.findall(r'"h1:[A-Za-z0-9+/=]+"', body)
    zh_hashes = re.findall(r'"zh:[a-f0-9]{64}"', body)
    if not h1_hashes or not zh_hashes:
        raise ValueError("Québec lockfile must contain signed h1 and zh checksums")
    return {
        "lock_sha256": sha256(lock_path.read_bytes()).hexdigest(),
        "provider_source": provider,
        "provider_version": expected_version,
        "h1_checksum_count": len(h1_hashes),
        "zh_checksum_count": len(zh_hashes),
    }


def parse_validate_json(output: str) -> dict[str, object]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError("terraform validate did not emit valid JSON") from exc
    if payload.get("valid") is not True:
        raise ValueError("terraform validate reported an invalid configuration")
    return {
        "valid": True,
        "error_count": int(payload.get("error_count", 0)),
        "warning_count": int(payload.get("warning_count", 0)),
    }


def _action_summary(changes: object) -> tuple[dict[str, int], int]:
    summary: dict[str, int] = {}
    changed = 0
    if not isinstance(changes, list):
        raise ValueError("terraform plan change collection must be a list")
    for item in changes:
        if not isinstance(item, dict):
            raise ValueError("terraform plan change entry must be an object")
        change = item.get("change")
        if not isinstance(change, dict):
            raise ValueError("terraform plan change entry is missing change metadata")
        actions = change.get("actions")
        if not isinstance(actions, list) or not all(
            isinstance(action, str) for action in actions
        ):
            raise ValueError("terraform plan actions must be strings")
        action_key = ",".join(actions)
        summary[action_key] = summary.get(action_key, 0) + 1
        if actions not in ([], ["no-op"]):
            changed += 1
    return summary, changed


_QUEBEC_TEST_FILE = "ci/tftest/inert_authority.tftest.hcl"
_QUEBEC_TEST_RUN = "inert_authority_boundary"


def parse_quebec_test_json(output: str) -> dict[str, object]:
    """Validate Terraform's line-delimited, verbose test-plan evidence.

    Only a compact, non-sensitive summary is retained. The raw provider schema,
    planned values, diagnostics text, and output values never enter the receipt.
    """
    records: list[dict[str, object]] = []
    for line_number, raw_line in enumerate(output.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"terraform test line {line_number} is not valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError("terraform test records must be JSON objects")
        records.append(payload)
    if not records:
        raise ValueError("terraform test emitted no machine-readable evidence")

    def of_type(record_type: str) -> list[dict[str, object]]:
        return [record for record in records if record.get("type") == record_type]

    allowed_types = {
        "version",
        "test_abstract",
        "test_file",
        "test_run",
        "test_plan",
        "test_summary",
        "diagnostic",
    }
    unknown_types = sorted(
        {
            str(record.get("type"))
            for record in records
            if record.get("type") not in allowed_types
        }
    )
    if unknown_types:
        raise ValueError("terraform test emitted a prohibited event type")

    versions = of_type("version")
    abstracts = of_type("test_abstract")
    if (
        records[0].get("type") != "version"
        or len(versions) != 1
        or versions[0].get("terraform") != "1.10.5"
        or versions[0].get("ui") != "1.2"
        or len(abstracts) != 1
        or abstracts[0].get("test_abstract")
        != {_QUEBEC_TEST_FILE: [_QUEBEC_TEST_RUN]}
    ):
        raise ValueError("terraform test version or abstract contract is not exact")

    plans = of_type("test_plan")
    summaries = of_type("test_summary")
    file_records = of_type("test_file")
    run_records = of_type("test_run")
    if any(
        record.get("@testfile") != _QUEBEC_TEST_FILE
        or not isinstance(record.get("test_file"), dict)
        or record["test_file"].get("path") != _QUEBEC_TEST_FILE
        or record["test_file"].get("progress")
        not in {"starting", "teardown", "complete"}
        for record in file_records
    ):
        raise ValueError("terraform test file events are not exactly bound")
    if (
        [record["test_file"].get("progress") for record in file_records].count(
            "starting"
        )
        != 1
        or [record["test_file"].get("progress") for record in file_records].count(
            "teardown"
        )
        != 1
        or [record["test_file"].get("progress") for record in file_records].count(
            "complete"
        )
        != 1
    ):
        raise ValueError("terraform test file lifecycle is not exact")
    if any(
        record.get("@testfile") != _QUEBEC_TEST_FILE
        or record.get("@testrun") != _QUEBEC_TEST_RUN
        or not isinstance(record.get("test_run"), dict)
        or record["test_run"].get("path") != _QUEBEC_TEST_FILE
        or record["test_run"].get("run") != _QUEBEC_TEST_RUN
        or record["test_run"].get("progress")
        not in {"starting", "running", "teardown", "complete"}
        for record in run_records
    ):
        raise ValueError("terraform test run events are not exactly bound")
    if (
        [record["test_run"].get("progress") for record in run_records].count(
            "starting"
        )
        != 1
        or [record["test_run"].get("progress") for record in run_records].count(
            "complete"
        )
        != 1
    ):
        raise ValueError("terraform test run lifecycle is not exact")
    files = [
        record
        for record in file_records
        if isinstance(record.get("test_file"), dict)
        and record["test_file"].get("progress") == "complete"
    ]
    runs = [
        record
        for record in run_records
        if isinstance(record.get("test_run"), dict)
        and record["test_run"].get("progress") == "complete"
    ]
    if len(plans) != 1 or len(summaries) != 1 or len(files) != 1 or len(runs) != 1:
        raise ValueError("terraform test did not emit exactly one complete plan run")

    plan_record = plans[0]
    plan = plan_record.get("test_plan")
    summary = summaries[0].get("test_summary")
    file_result = files[0].get("test_file")
    run_result = runs[0].get("test_run")
    if not all(
        isinstance(item, dict)
        for item in (plan, summary, file_result, run_result)
    ):
        raise ValueError("terraform test evidence has an invalid payload")
    if (
        records[-1].get("type") != "test_summary"
        or plan_record.get("@testfile") != _QUEBEC_TEST_FILE
        or plan_record.get("@testrun") != _QUEBEC_TEST_RUN
        or files[0].get("@testfile") != _QUEBEC_TEST_FILE
        or file_result.get("path") != _QUEBEC_TEST_FILE
        or file_result.get("status") != "pass"
        or runs[0].get("@testfile") != _QUEBEC_TEST_FILE
        or runs[0].get("@testrun") != _QUEBEC_TEST_RUN
        or run_result.get("path") != _QUEBEC_TEST_FILE
        or run_result.get("run") != _QUEBEC_TEST_RUN
        or run_result.get("status") != "pass"
        or set(summary) != {"status", "passed", "failed", "errored", "skipped"}
        or summary.get("status") != "pass"
        or summary.get("passed") != 1
        or summary.get("failed") != 0
        or summary.get("errored") != 0
        or summary.get("skipped") != 0
    ):
        raise ValueError("terraform test did not pass the exact inert test contract")

    provider_schemas = plan.get("provider_schemas")
    if (
        plan.get("plan_format_version") != "1.2"
        or plan.get("provider_format_version") != "1.0"
        or not isinstance(provider_schemas, dict)
        or set(provider_schemas)
        != {"registry.terraform.io/hashicorp/google"}
        or (
            "relevant_attributes" in plan
            and not isinstance(plan["relevant_attributes"], list)
        )
    ):
        raise ValueError("terraform test-plan metadata is not exact")

    resource_changes = plan.get("resource_changes", [])
    resource_drift = plan.get("resource_drift", [])
    if resource_changes != []:
        raise ValueError("Québec inert test plan contains managed-resource entries")
    if resource_drift != []:
        raise ValueError("Québec inert test plan contains resource-drift entries")
    resource_summary, resource_change_count = _action_summary(resource_changes)
    drift_summary, drift_change_count = _action_summary(resource_drift)
    output_changes = plan.get("output_changes", {})
    if not isinstance(output_changes, dict):
        raise ValueError("terraform test-plan output_changes must be an object")
    output_summary: dict[str, int] = {}
    for change in output_changes.values():
        if not isinstance(change, dict) or not isinstance(change.get("actions"), list):
            raise ValueError("terraform test-plan output change lacks actions")
        key = ",".join(change["actions"])
        output_summary[key] = output_summary.get(key, 0) + 1
    if resource_change_count or drift_change_count:
        raise ValueError("Québec inert test plan is not empty")

    diagnostics = of_type("diagnostic")
    if any(
        not isinstance(record.get("diagnostic"), dict)
        or record["diagnostic"].get("severity") not in {"warning"}
        for record in diagnostics
    ):
        raise ValueError("terraform test emitted an unsafe diagnostic")
    diagnostic_warnings = sum(
        1
        for record in diagnostics
        if isinstance(record.get("diagnostic"), dict)
        and record["diagnostic"].get("severity") == "warning"
    )

    return {
        "managed_resource_change_count": 0,
        "resource_drift_change_count": 0,
        "resource_action_summary": resource_summary,
        "drift_action_summary": drift_summary,
        "output_action_summary": output_summary,
        "output_metadata_change_count": sum(output_summary.values()),
        "test_file_count": 1,
        "test_run_count": 1,
        "test_plan_count": 1,
        "diagnostic_warning_count": diagnostic_warnings,
        "all_assertion_runs_passed": True,
        "machine_readable_test_plan_verified": True,
        "isolated_in_memory_test_state": True,
        "zero_managed_resource_changes": True,
    }


def run_quebec_terraform_stage(
    *,
    project_root: Path,
    results_dir: Path,
    env: dict[str, str],
    run_id: int,
    repository_revision: str,
) -> tuple[list[dict[str, object]], dict[str, object], str, str | None]:
    lock_path = project_root / _QUEBEC_LOCK
    policy_path = project_root / _QUEBEC_LOCK_POLICY
    lock_was_tracked = _git_tracks(project_root, _QUEBEC_LOCK)
    lock_hash_before = (
        sha256(lock_path.read_bytes()).hexdigest()
        if lock_was_tracked and lock_path.is_file()
        else None
    )
    del run_id
    commands = quebec_terraform_commands(lockfile_readonly=lock_was_tracked)
    roles = ("fmt", "init", "validate", "test")
    outcomes: list[dict[str, object]] = []
    summary: dict[str, object] = {
        "terraform_root": _QUEBEC_ROOT.as_posix(),
        "lockfile_path": _QUEBEC_LOCK.as_posix(),
        "lockfile_committed_at_start": lock_was_tracked,
        "lockfile_readonly_mode": lock_was_tracked,
        "machine_readable_test_plan": True,
        "isolated_in_memory_test_state": True,
        "backend_initialized": False,
        "provider_or_cloud_mutation_performed": False,
    }
    failure_reason: str | None = None

    try:
        for index, command in enumerate(commands):
            role = roles[index]
            outcome, stdout = _execute_command(
                command,
                project_root,
                env,
                stage_id="quebec_terraform_validate",
                accepted_exit_codes=frozenset({0}),
            )
            outcome["command_role"] = role
            outcomes.append(outcome)
            if outcome["policy_accepted"] is not True:
                failure_reason = f"terraform_{role}_failed"
                break

            try:
                if role == "init":
                    if not lock_path.is_file():
                        raise ValueError("terraform init did not produce a provider lockfile")
                    lock_summary = validate_provider_lock(lock_path, policy_path)
                    summary["provider_lock"] = lock_summary
                    if not lock_was_tracked:
                        bootstrap_dir = results_dir / "quebec_terraform_lock_bootstrap"
                        bootstrap_dir.mkdir(parents=True, exist_ok=True)
                        generated_path = bootstrap_dir / "terraform.lock.hcl.generated"
                        shutil.copyfile(lock_path, generated_path)
                        bootstrap_receipt = {
                            "schema_version": "aigc.terraform-lock-bootstrap.v1",
                            "generated_from_repository_revision": repository_revision,
                            "install_path": _QUEBEC_LOCK.as_posix(),
                            "generated_artifact": generated_path.name,
                            **lock_summary,
                            "committed_lockfile_required_for_pass": True,
                            "external_action_performed": False,
                        }
                        bootstrap_receipt["receipt_sha256"] = sha256(
                            canonical(bootstrap_receipt)
                        ).hexdigest()
                        atomic_write(
                            bootstrap_dir / "bootstrap_receipt.json",
                            bootstrap_receipt,
                        )
                elif role == "validate":
                    summary["validate"] = parse_validate_json(stdout)
                elif role == "test":
                    summary["inert_plan"] = parse_quebec_test_json(stdout)
            except (KeyError, OSError, TypeError, ValueError) as exc:
                failure_reason = f"terraform_{role}_policy_failed:{exc}"
                break

        if lock_was_tracked:
            if not lock_path.is_file():
                failure_reason = failure_reason or "committed_lockfile_disappeared"
            else:
                lock_hash_after = sha256(lock_path.read_bytes()).hexdigest()
                summary["lockfile_unchanged"] = lock_hash_after == lock_hash_before
                if lock_hash_after != lock_hash_before:
                    failure_reason = failure_reason or "committed_lockfile_changed"
        else:
            summary["lock_bootstrap_artifact_emitted"] = lock_path.is_file()
            failure_reason = failure_reason or "provider_lockfile_not_committed"
    finally:
        pass

    status = "success" if failure_reason is None else "failure"
    summary["status"] = status
    summary["failure_reason"] = failure_reason
    return outcomes, summary, status, failure_reason


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--repository-revision", required=True)
    parser.add_argument("--tested-tree-sha", required=True)
    parser.add_argument("--broker-revision", required=True)
    parser.add_argument("--run-number", type=int, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if (
        contract.get("schema_version") != "1.2.0"
        or contract.get("contract_id") != "AIGC-CI-EXACT-SHA-V1"
    ):
        raise SystemExit("unsupported validation contract")
    if (
        contract.get("production_activation_authorized") is not False
        or contract.get("external_action_authorized") is not False
    ):
        raise SystemExit("validation contract grants prohibited authority")

    stages = contract.get("stages") or []
    if [item.get("id") for item in stages] != EXPECTED_STAGES:
        raise SystemExit("validation contract stage set/order mismatch")

    env = dict(os.environ)
    env["GOOGLE_OAUTH_ACCESS_TOKEN"] = (
        "aigc-offline-inert-plan-no-provider-action"
    )
    env["REPOSITORY_REVISION"] = args.repository_revision
    contract_sha = sha256(canonical(contract)).hexdigest()

    for stage in stages:
        stage_id = stage["id"]
        stage_summary: dict[str, object] | None = None
        failure_reason: str | None = None
        if stage_id == "quebec_terraform_validate":
            if stage.get("policy") != _QUEBEC_STAGE_POLICY:
                raise SystemExit("Québec Terraform stage policy mismatch")
            outcomes, stage_summary, status, failure_reason = (
                run_quebec_terraform_stage(
                    project_root=args.project_root,
                    results_dir=args.results_dir,
                    env=env,
                    run_id=args.run_id,
                    repository_revision=args.repository_revision,
                )
            )
        else:
            commands = stage_commands(stage)
            if not commands:
                raise SystemExit(f"validation stage has no commands: {stage_id}")
            outcomes = []
            status = "success"
            for raw in commands:
                command = [
                    part.replace(
                        "${REPOSITORY_REVISION}",
                        args.repository_revision,
                    )
                    for part in raw
                ]
                outcome = run_command(
                    command,
                    args.project_root,
                    env,
                    stage_id=stage_id,
                )
                outcomes.append(outcome)
                if outcome["policy_accepted"] is not True:
                    status = "failure"
                    failure_reason = "command_failed"
                    break
        record = {
            "schema_version": "1.2.0",
            "contract_id": contract["contract_id"],
            "contract_sha256": contract_sha,
            "stage_id": stage_id,
            "target_sha": args.repository_revision,
            "tested_tree_sha": args.tested_tree_sha,
            "broker_revision": args.broker_revision,
            "run_number": args.run_number,
            "run_id": args.run_id,
            "ordered_command_digest": sha256(
                canonical([item["argv_sha256"] for item in outcomes])
            ).hexdigest(),
            "command_outcomes": outcomes,
            "status": status,
            "external_action_performed": False,
            "production_activation_authorized": False,
            "merge_authority_granted": False,
            "deployment_authority_granted": False,
            "live_model_call_authority_granted": False,
            "financial_authority_granted": False,
        }
        if stage_summary is not None:
            record["stage_summary"] = stage_summary
        if failure_reason is not None:
            record["failure_reason"] = failure_reason
        record["record_sha256"] = sha256(canonical(record)).hexdigest()
        atomic_write(args.results_dir / f"{stage_id}.json", record)
        if status != "success":
            raise SystemExit(f"validation stage failed: {stage_id}")


if __name__ == "__main__":
    main()
