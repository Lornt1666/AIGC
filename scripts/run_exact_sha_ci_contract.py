from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

EXPECTED_STAGES = ["contracts", "redaction", "procurement_smoke", "provider_discovery", "terraform_inert", "tests", "readiness"]


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


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


def run_command(command: list[str], cwd: Path, env: dict[str, str]) -> dict:
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    outcome = {
        "argv_sha256": sha256(canonical(command)).hexdigest(),
        "exit_code": completed.returncode,
        "output_sha256": sha256(completed.stdout.encode()).hexdigest(),
    }
    if completed.returncode != 0:
        outcome["diagnostic_output_tail"] = completed.stdout[-12000:]
    return outcome


def terraform_commands() -> list[list[str]]:
    return [
        ["terraform", "-chdir=infra/terraform/gcp", "fmt", "-check", "-recursive"],
        ["terraform", "-chdir=infra/terraform/gcp", "init", "-backend=false", "-input=false"],
        ["terraform", "-chdir=infra/terraform/gcp", "validate"],
        ["terraform", "-chdir=infra/terraform/gcp", "plan", "-input=false", "-lock=false", "-refresh=false", "-var-file=staging.tfvars.example", "-out=/tmp/aigc-exact-sha.tfplan"],
        ["terraform", "-chdir=infra/terraform/gcp", "show", "-json", "/tmp/aigc-exact-sha.tfplan"],
    ]


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
    if contract.get("schema_version") != "1.0.0" or contract.get("contract_id") != "AIGC-CI-EXACT-SHA-V1":
        raise SystemExit("unsupported validation contract")
    if contract.get("production_activation_authorized") is not False or contract.get("external_action_authorized") is not False:
        raise SystemExit("validation contract grants prohibited authority")
    stages = contract.get("stages") or []
    if [item.get("id") for item in stages] != EXPECTED_STAGES:
        raise SystemExit("validation contract stage set/order mismatch")
    env = dict(os.environ)
    env["GOOGLE_OAUTH_ACCESS_TOKEN"] = "aigc-offline-inert-plan-no-provider-action"
    env["REPOSITORY_REVISION"] = args.repository_revision
    contract_sha = sha256(canonical(contract)).hexdigest()
    for stage in stages:
        stage_id = stage["id"]
        commands = terraform_commands() if stage.get("runner") == "terraform_inert" else ([["python", "-m", "pytest"]] if stage.get("runner") == "pytest" else stage.get("commands") or [])
        outcomes = []
        status = "success"
        for raw in commands:
            command = [part.replace("${REPOSITORY_REVISION}", args.repository_revision) for part in raw]
            outcome = run_command(command, args.project_root, env)
            outcomes.append(outcome)
            if outcome["exit_code"] != 0:
                status = "failure"
                break
        record = {
            "schema_version": "1.0.0",
            "contract_id": contract["contract_id"],
            "contract_sha256": contract_sha,
            "stage_id": stage_id,
            "target_sha": args.repository_revision,
            "tested_tree_sha": args.tested_tree_sha,
            "broker_revision": args.broker_revision,
            "run_number": args.run_number,
            "run_id": args.run_id,
            "ordered_command_digest": sha256(canonical([item["argv_sha256"] for item in outcomes])).hexdigest(),
            "command_outcomes": outcomes,
            "status": status,
            "external_action_performed": False,
            "production_activation_authorized": False,
        }
        record["record_sha256"] = sha256(canonical(record)).hexdigest()
        atomic_write(args.results_dir / f"{stage_id}.json", record)
        if status != "success":
            raise SystemExit(f"validation stage failed: {stage_id}")


if __name__ == "__main__":
    main()
