from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

EXPECTED_STAGES = ["contracts", "redaction", "procurement_smoke", "provider_discovery", "terraform_inert", "tests", "readiness"]


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def write_result(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


def run_command(command: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, str]:
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return completed.returncode, completed.stdout


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
        outputs: list[str] = []
        commands: list[list[str]]
        if stage.get("runner") == "terraform_inert":
            commands = terraform_commands()
        elif stage.get("runner") == "pytest":
            commands = [["python", "-m", "pytest"]]
        else:
            commands = stage.get("commands") or []
        status = "success"
        exit_code = 0
        for raw in commands:
            command = [part.replace("${REPOSITORY_REVISION}", args.repository_revision) for part in raw]
            code, output = run_command(command, args.project_root, env)
            outputs.append(output)
            if stage_id == "terraform_inert" and command[:3] == ["terraform", "-chdir=infra/terraform/gcp", "show"] and code == 0:
                plan = json.loads(output)
                if plan.get("resource_changes"):
                    code, output = 1, output + "\nresource changes detected"
            if code != 0:
                status, exit_code = "failure", code
                break
        combined = "\n".join(outputs)
        record = {
            "schema_version": "1.0.0",
            "contract_id": contract["contract_id"],
            "contract_sha256": contract_sha,
            "stage_id": stage_id,
            "status": status,
            "exit_code": exit_code,
            "output_sha256": sha256(combined.encode()).hexdigest(),
            "external_action_performed": False,
            "production_activation_authorized": False,
        }
        record["record_sha256"] = sha256(canonical(record)).hexdigest()
        write_result(args.results_dir / f"{stage_id}.json", record)
        if status != "success":
            raise SystemExit(f"validation stage failed: {stage_id}")


if __name__ == "__main__":
    main()
