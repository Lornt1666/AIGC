from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any


REQUEST_KEYS = {
    "schema_version",
    "request_id",
    "repository",
    "target_sha",
    "expected_tree_sha",
    "trusted_base_sha",
    "broker_revision",
    "contract_path",
    "contract_sha256",
    "requested_stages",
    "approved_by",
    "approved_at",
    "expires_at",
    "human_execution_approved",
    "network_policy",
    "external_action_authorized",
    "production_activation_authorized",
    "provider_call_authorized",
    "secret_access_authorized",
}
SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$")
DIGEST_PATTERN = re.compile(r"^[a-f0-9]{64}$")
REQUEST_ID_PATTERN = re.compile(r"^FORGE-[A-Z0-9-]{12,80}$")
STAGE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
ALLOWED_COMMAND_ROOTS = {"${PYTHON}"}
TERMINAL_STATUSES = {"PASS", "BLOCKED", "FAILED_SAFE"}
SENSITIVE_LINE = re.compile(
    r"(?i)(authorization|bearer|credential|password|private[_ -]?key|secret|token)"
)
EXACT_REQUIREMENT = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9._,-]+\])?==([^;\s]+)$"
)


class RunnerBlocked(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()


def digest_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def check_exact_dependencies(requirements_path: Path) -> dict[str, Any]:
    """Verify an offline, exact-pin manifest without requiring pip to be installed."""
    if not requirements_path.is_file():
        raise RunnerBlocked("dependency manifest does not exist")
    observed = 0
    for line_number, raw_line in enumerate(
        requirements_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = EXACT_REQUIREMENT.fullmatch(line)
        if match is None:
            raise RunnerBlocked(
                f"dependency manifest line {line_number} is not an exact offline pin"
            )
        distribution, expected = match.groups()
        try:
            installed = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RunnerBlocked(
                f"required distribution is not installed: {distribution}"
            ) from exc
        if installed != expected:
            raise RunnerBlocked(
                f"installed distribution does not match exact pin: {distribution}"
            )
        observed += 1
    if observed == 0:
        raise RunnerBlocked("dependency manifest contains no exact pins")
    return {
        "checked_distributions": observed,
        "manifest_sha256": digest_file(requirements_path),
        "terminal_status": "PASS",
    }


def atomic_json(path: Path, value: Any) -> None:
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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise RunnerBlocked(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RunnerBlocked(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def git(repository_root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise RunnerBlocked(
            f"git {' '.join(args)} failed: {completed.stderr.strip() or 'unknown error'}"
        )
    return completed.stdout.strip()


def resolve_commit(repository_root: Path, revision: str) -> str:
    resolved = git(repository_root, "rev-parse", "--verify", f"{revision}^{{commit}}")
    if not SHA_PATTERN.fullmatch(resolved):
        raise RunnerBlocked("revision did not resolve to a full commit SHA")
    return resolved


def resolve_tree(repository_root: Path, revision: str) -> str:
    resolved = git(repository_root, "rev-parse", "--verify", f"{revision}^{{tree}}")
    if not SHA_PATTERN.fullmatch(resolved):
        raise RunnerBlocked("revision did not resolve to a full tree SHA")
    return resolved


def assert_ancestor(repository_root: Path, base: str, target: str) -> None:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, target],
        cwd=repository_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        raise RunnerBlocked("trusted_base_sha is not an ancestor of target_sha")


def load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if set(contract) != {
        "schema_version",
        "contract_id",
        "external_action_authorized",
        "production_activation_authorized",
        "provider_call_authorized",
        "network_policy",
        "stages",
    }:
        raise RunnerBlocked("runner contract keys do not match the closed contract")
    if (
        contract["schema_version"] != "1.0.0"
        or contract["contract_id"] != "REGENEXCALIBUR-AIGC-FORGERUNNER-V1"
    ):
        raise RunnerBlocked("unsupported runner contract")
    if any(
        contract[field] is not False
        for field in (
            "external_action_authorized",
            "production_activation_authorized",
            "provider_call_authorized",
        )
    ):
        raise RunnerBlocked("runner contract grants prohibited authority")
    if contract["network_policy"] != "process_environment_guard":
        raise RunnerBlocked("unsupported network policy")
    stages = contract["stages"]
    if not isinstance(stages, list) or not stages:
        raise RunnerBlocked("runner contract must define stages")
    observed_ids: list[str] = []
    for stage in stages:
        if set(stage) != {"id", "timeout_seconds", "commands"}:
            raise RunnerBlocked("stage keys do not match the closed contract")
        stage_id = stage["id"]
        if not isinstance(stage_id, str) or not STAGE_ID_PATTERN.fullmatch(stage_id):
            raise RunnerBlocked("invalid stage id")
        if stage_id in observed_ids:
            raise RunnerBlocked("duplicate stage id")
        observed_ids.append(stage_id)
        timeout = stage["timeout_seconds"]
        if not isinstance(timeout, int) or not 1 <= timeout <= 3600:
            raise RunnerBlocked(f"invalid timeout for stage {stage_id}")
        commands = stage["commands"]
        if not isinstance(commands, list) or not commands:
            raise RunnerBlocked(f"stage {stage_id} has no commands")
        for command in commands:
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(item, str) and item for item in command)
                or command[0] not in ALLOWED_COMMAND_ROOTS
            ):
                raise RunnerBlocked(
                    f"stage {stage_id} must use argv-only trusted Python commands"
                )
    return contract


def validate_request(
    request: dict[str, Any],
    contract: dict[str, Any],
    *,
    now: datetime,
) -> None:
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        raise RunnerBlocked("request keys do not match the closed contract")
    if request["schema_version"] != "1.0.0":
        raise RunnerBlocked("unsupported request schema version")
    if not REQUEST_ID_PATTERN.fullmatch(str(request["request_id"])):
        raise RunnerBlocked("invalid request_id")
    if request["repository"] != "Lornt1666/AIGC":
        raise RunnerBlocked("repository is not authorized for this runner")
    for field in (
        "target_sha",
        "expected_tree_sha",
        "trusted_base_sha",
        "broker_revision",
    ):
        if not SHA_PATTERN.fullmatch(str(request[field])):
            raise RunnerBlocked(f"{field} must be a full lowercase SHA")
    if request["contract_path"] != "config/aigc_operator_runner_contract.v1.json":
        raise RunnerBlocked("request contract_path is not canonical")
    if not DIGEST_PATTERN.fullmatch(str(request["contract_sha256"])):
        raise RunnerBlocked("contract_sha256 is invalid")
    stage_ids = [stage["id"] for stage in contract["stages"]]
    if request["requested_stages"] != stage_ids:
        raise RunnerBlocked("request stage set/order does not match the contract")
    if request["approved_by"] != "RegenExcalibur / 1JGM":
        raise RunnerBlocked("request attribution/approval identity mismatch")
    approved_at = parse_time(request["approved_at"], "approved_at")
    expires_at = parse_time(request["expires_at"], "expires_at")
    if expires_at <= approved_at or expires_at > approved_at + timedelta(hours=2):
        raise RunnerBlocked("request expiry window must be greater than zero and at most two hours")
    if now < approved_at - timedelta(minutes=5) or now >= expires_at:
        raise RunnerBlocked("request is not currently valid")
    if request["human_execution_approved"] is not True:
        raise RunnerBlocked("human execution approval is absent")
    if request["network_policy"] != "process_environment_guard":
        raise RunnerBlocked("request network policy mismatch")
    for field in (
        "external_action_authorized",
        "production_activation_authorized",
        "provider_call_authorized",
        "secret_access_authorized",
    ):
        if request[field] is not False:
            raise RunnerBlocked(f"request grants prohibited authority: {field}")


def sanitized_environment(work_root: Path, *, local_postgres: bool) -> dict[str, str]:
    path_value = os.environ.get("PATH", "")
    environment = {
        "PATH": path_value,
        "HOME": str(work_root / "home"),
        "TMPDIR": str(work_root / "tmp"),
        "TEMP": str(work_root / "tmp"),
        "TMP": str(work_root / "tmp"),
        "CI": "true",
        "PYTHONNOUSERSITE": "1",
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "127.0.0.1,localhost",
        "AIGC_RUNNER_NETWORK_POLICY": "process_environment_guard",
        "GOOGLE_OAUTH_ACCESS_TOKEN": "aigc-offline-inert-plan-no-provider-action",
    }
    for name in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT"):
        if name in os.environ:
            environment[name] = os.environ[name]
    if local_postgres:
        environment["NEXUS_TEST_POSTGRES_DSN"] = (
            "postgresql://postgres@127.0.0.1:5432/aigc_test"
        )
    (work_root / "home").mkdir(parents=True, exist_ok=True)
    (work_root / "tmp").mkdir(parents=True, exist_ok=True)
    return environment


def safe_failure_lines(output: str) -> list[str]:
    lines: list[str] = []
    for raw in output.splitlines()[-30:]:
        line = raw.strip()
        if not line:
            continue
        lines.append(
            "[REDACTED_DIAGNOSTIC_LINE]" if SENSITIVE_LINE.search(line) else line[:500]
        )
    return lines[-12:]


def timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def export_commit(repository_root: Path, target_sha: str, destination: Path) -> None:
    archive = destination.parent / "candidate.tar"
    subprocess.run(
        ["git", "archive", "--format=tar", "--output", str(archive), target_sha],
        cwd=repository_root,
        check=True,
    )
    destination.mkdir(parents=True)
    with tarfile.open(archive) as handle:
        for member in handle.getmembers():
            resolved = (destination / member.name).resolve()
            if destination.resolve() not in resolved.parents and resolved != destination.resolve():
                raise RunnerBlocked("candidate archive contains an unsafe path")
        handle.extractall(destination, filter="data")
    archive.unlink()


def execute_contract(
    contract: dict[str, Any],
    *,
    candidate_root: Path,
    result_root: Path,
    environment: dict[str, str],
    target_sha: str,
    tree_sha: str,
    broker_revision: str,
) -> tuple[str, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    contract_sha = digest(contract)
    for stage in contract["stages"]:
        outcomes: list[dict[str, Any]] = []
        stage_status = "PASS"
        for raw_command in stage["commands"]:
            command = [
                sys.executable if item == "${PYTHON}" else item for item in raw_command
            ]
            started = time.monotonic()
            try:
                completed = subprocess.run(
                    command,
                    cwd=candidate_root,
                    env=environment,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=stage["timeout_seconds"],
                )
                output = completed.stdout
                exit_code = completed.returncode
                timed_out = False
            except subprocess.TimeoutExpired as exc:
                output = timeout_output(exc.stdout) + timeout_output(exc.stderr)
                exit_code = 124
                timed_out = True
            outcome = {
                "argv_sha256": sha256(canonical(command)).hexdigest(),
                "exit_code": exit_code,
                "timed_out": timed_out,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "output_sha256": sha256(output.encode("utf-8", errors="replace")).hexdigest(),
            }
            if exit_code != 0:
                stage_status = "FAILED_SAFE"
                outcome["sanitized_failure_tail"] = safe_failure_lines(output)
            outcomes.append(outcome)
            if exit_code != 0:
                break
        record = {
            "schema_version": "1.0.0",
            "contract_id": contract["contract_id"],
            "contract_sha256": contract_sha,
            "stage_id": stage["id"],
            "target_sha": target_sha,
            "tested_tree_sha": tree_sha,
            "broker_revision": broker_revision,
            "status": stage_status,
            "command_outcomes": outcomes,
            "external_actions_performed": 0,
            "provider_calls_performed": 0,
            "production_activation_authorized": False,
        }
        record["record_sha256"] = digest(record)
        atomic_json(result_root / "stages" / f"{stage['id']}.json", record)
        records.append(record)
        if stage_status != "PASS":
            return "FAILED_SAFE", records
    return "PASS", records


def claim_request(state_root: Path, request: dict[str, Any]) -> Path:
    state_root.mkdir(parents=True, exist_ok=True)
    claim = state_root / f"{request['request_id']}-{digest(request)}.claim.json"
    payload = {
        "request_id": request["request_id"],
        "request_sha256": digest(request),
        "claimed_at": isoformat(utc_now()),
    }
    try:
        descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RunnerBlocked("request has already been consumed") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical(payload) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def create_inventory(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): digest_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "inventory.json"
    }


def plan_request(args: argparse.Namespace) -> dict[str, Any]:
    repository_root = args.repository_root.resolve()
    target_sha = resolve_commit(repository_root, args.target_sha)
    target_tree = resolve_tree(repository_root, target_sha)
    trusted_base = resolve_commit(repository_root, args.trusted_base_sha)
    assert_ancestor(repository_root, trusted_base, target_sha)
    broker_revision = resolve_commit(repository_root, "HEAD")
    contract_path = repository_root / "config/aigc_operator_runner_contract.v1.json"
    contract = load_contract(contract_path)
    approved_at = utc_now()
    request = {
        "schema_version": "1.0.0",
        "request_id": f"FORGE-{approved_at.strftime('%Y%m%dT%H%M%SZ')}-{target_sha[:12].upper()}",
        "repository": "Lornt1666/AIGC",
        "target_sha": target_sha,
        "expected_tree_sha": target_tree,
        "trusted_base_sha": trusted_base,
        "broker_revision": broker_revision,
        "contract_path": "config/aigc_operator_runner_contract.v1.json",
        "contract_sha256": digest(contract),
        "requested_stages": [stage["id"] for stage in contract["stages"]],
        "approved_by": "RegenExcalibur / 1JGM",
        "approved_at": isoformat(approved_at),
        "expires_at": isoformat(approved_at + timedelta(minutes=args.expires_minutes)),
        "human_execution_approved": True,
        "network_policy": "process_environment_guard",
        "external_action_authorized": False,
        "production_activation_authorized": False,
        "provider_call_authorized": False,
        "secret_access_authorized": False,
    }
    validate_request(request, contract, now=approved_at)
    atomic_json(args.output.resolve(), request)
    return request


def run_request(args: argparse.Namespace) -> dict[str, Any]:
    repository_root = args.repository_root.resolve()
    output_root = args.output_root.resolve()
    state_root = args.state_root.resolve()
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise RunnerBlocked("output_root must be absent or empty")
    output_root.mkdir(parents=True, exist_ok=True)
    request = json.loads(args.request.read_text(encoding="utf-8"))
    contract_path = repository_root / request.get("contract_path", "")
    contract = load_contract(contract_path)
    validate_request(request, contract, now=utc_now())
    observed_target = resolve_commit(repository_root, request["target_sha"])
    observed_tree = resolve_tree(repository_root, observed_target)
    observed_broker = resolve_commit(repository_root, "HEAD")
    if observed_target != request["target_sha"]:
        raise RunnerBlocked("target SHA resolution drift")
    if observed_tree != request["expected_tree_sha"]:
        raise RunnerBlocked("target tree does not match the approved tree")
    if observed_broker != request["broker_revision"]:
        raise RunnerBlocked("broker revision changed after request approval")
    if digest(contract) != request["contract_sha256"]:
        raise RunnerBlocked("runner contract changed after request approval")
    assert_ancestor(repository_root, request["trusted_base_sha"], observed_target)
    if git(repository_root, "status", "--porcelain"):
        raise RunnerBlocked("trusted broker worktree must be clean")
    claim = claim_request(state_root, request)
    started_at = utc_now()
    atomic_json(output_root / "request.json", request)
    atomic_json(output_root / "contract.json", contract)
    with tempfile.TemporaryDirectory(prefix="aigc-forgerunner-") as temporary:
        work_root = Path(temporary)
        candidate_root = work_root / "candidate"
        export_commit(repository_root, observed_target, candidate_root)
        environment = sanitized_environment(
            work_root, local_postgres=args.local_postgres
        )
        terminal_status, records = execute_contract(
            contract,
            candidate_root=candidate_root,
            result_root=output_root,
            environment=environment,
            target_sha=observed_target,
            tree_sha=observed_tree,
            broker_revision=observed_broker,
        )
    receipt = {
        "schema_version": "1.0.0",
        "runner_id": "REGENEXCALIBUR-AIGC-FORGERUNNER-V1",
        "business_identity": "RegenExcalibur",
        "employee_attribution": "1JGM",
        "request_id": request["request_id"],
        "request_sha256": digest(request),
        "contract_sha256": digest(contract),
        "target_sha": observed_target,
        "tested_tree_sha": observed_tree,
        "trusted_base_sha": request["trusted_base_sha"],
        "broker_revision": observed_broker,
        "runner_source_sha256": digest_file(Path(__file__)),
        "started_at": isoformat(started_at),
        "completed_at": isoformat(utc_now()),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "stage_statuses": {record["stage_id"]: record["status"] for record in records},
        "network_isolation": "PROCESS_ENVIRONMENT_GUARD_ONLY",
        "network_isolation_os_enforced": False,
        "external_actions_performed": 0,
        "provider_calls_performed": 0,
        "costs_incurred_usd": 0,
        "merge_authority_granted": False,
        "deployment_authority_granted": False,
        "terminal_status": terminal_status,
        "limitations": [
            "Process environment guards discourage network access but do not provide kernel-level isolation.",
            "This receipt is local evidence and is not a GitHub-hosted check or merge authorization.",
        ],
    }
    if receipt["terminal_status"] not in TERMINAL_STATUSES:
        raise AssertionError("invalid terminal status")
    receipt["receipt_sha256"] = digest(receipt)
    atomic_json(output_root / "receipt.json", receipt)
    atomic_json(output_root / "inventory.json", create_inventory(output_root))
    claim_value = json.loads(claim.read_text(encoding="utf-8"))
    claim_value["terminal_status"] = terminal_status
    claim_value["receipt_sha256"] = receipt["receipt_sha256"]
    claim_value["completed_at"] = receipt["completed_at"]
    atomic_json(claim, claim_value)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run exact-SHA AIGC checks on operator-owned compute without GitHub billing."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--repository-root", type=Path, default=Path("."))
    plan.add_argument("--target-sha", required=True)
    plan.add_argument("--trusted-base-sha", required=True)
    plan.add_argument("--expires-minutes", type=int, default=30, choices=range(1, 121))
    plan.add_argument("--output", type=Path, required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--repository-root", type=Path, default=Path("."))
    run.add_argument("--request", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument("--state-root", type=Path, required=True)
    run.add_argument("--local-postgres", action="store_true")
    dependencies = subparsers.add_parser("dependency-check")
    dependencies.add_argument("--requirements", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "plan":
            value = plan_request(args)
            summary = {
                "request_id": value["request_id"],
                "target_sha": value["target_sha"],
                "expected_tree_sha": value["expected_tree_sha"],
                "terminal_status": "PASS",
            }
            exit_code = 0
        elif args.command == "run":
            value = run_request(args)
            summary = {
                "request_id": value["request_id"],
                "target_sha": value["target_sha"],
                "tested_tree_sha": value["tested_tree_sha"],
                "receipt_sha256": value["receipt_sha256"],
                "terminal_status": value["terminal_status"],
            }
            exit_code = 0 if value["terminal_status"] == "PASS" else 1
        else:
            summary = check_exact_dependencies(args.requirements)
            exit_code = 0
    except RunnerBlocked as exc:
        summary = {"terminal_status": "BLOCKED", "reason": str(exc)}
        exit_code = 2
    print(json.dumps(summary, sort_keys=True))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
