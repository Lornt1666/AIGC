from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
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
    "tests",
    "false_authority",
    "readiness",
]

_SCANNER_LINE = re.compile(
    r"^(critical|high):\s+(.+):(\d+)\s+matched\s+(.+)$"
)


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
        signatures: list[dict[str, str]] = []
        seen_signatures: set[tuple[str, str, str]] = set()
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if line.startswith(("FAILED ", "ERROR ")):
                remainder = line.split(" ", 1)[1]
                node_id = remainder.split(" - ", 1)[0].strip()
                if node_id and node_id not in node_ids:
                    node_ids.append(node_id)
            if not line.startswith("E   "):
                continue
            detail = line[4:].strip()
            exception_match = re.match(
                r"^(?:[A-Za-z_][\w.]*\.)?([A-Za-z_][\w]*(?:Error|Exception|Warning))(?::\s*(.*))?$",
                detail,
            )
            if not exception_match:
                continue
            kind, message = exception_match.group(1), exception_match.group(2) or ""
            signature = {"kind": kind, "module": "", "symbol": ""}
            missing_module = re.search(r"No module named ['\"]([A-Za-z0-9_.-]{1,160})['\"]", message)
            cannot_import = re.search(
                r"cannot import name ['\"]([A-Za-z0-9_]{1,120})['\"] from ['\"]([A-Za-z0-9_.]{1,160})['\"]",
                message,
            )
            missing_attribute = re.search(
                r"module ['\"]([A-Za-z0-9_.]{1,160})['\"] has no attribute ['\"]([A-Za-z0-9_]{1,120})['\"]",
                message,
            )
            if missing_module:
                signature["module"] = missing_module.group(1)
            elif cannot_import:
                signature["symbol"], signature["module"] = cannot_import.group(1), cannot_import.group(2)
            elif missing_attribute:
                signature["module"], signature["symbol"] = missing_attribute.group(1), missing_attribute.group(2)
            key = (signature["kind"], signature["module"], signature["symbol"])
            if key not in seen_signatures:
                seen_signatures.add(key)
                signatures.append(signature)
        return {
            "failed_or_error_test_count": len(node_ids),
            "failed_or_error_tests": node_ids[:100],
            "failure_signatures": signatures[:50],
            "truncated": len(node_ids) > 100 or len(signatures) > 50,
        }
    return None


def run_command(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    *,
    stage_id: str,
) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    outcome: dict[str, object] = {
        "argv_sha256": sha256(canonical(command)).hexdigest(),
        "exit_code": completed.returncode,
        "output_sha256": sha256(completed.stdout.encode()).hexdigest(),
    }
    diagnostics = _safe_diagnostics(stage_id, completed.stdout)
    if diagnostics is not None:
        outcome["sanitized_diagnostics"] = diagnostics
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


def stage_commands(stage: dict) -> list[list[str]]:
    runner = stage.get("runner")
    if runner == "terraform_inert":
        return terraform_commands()
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
        contract.get("schema_version") != "1.1.0"
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
        commands = stage_commands(stage)
        if not commands:
            raise SystemExit(f"validation stage has no commands: {stage_id}")
        outcomes: list[dict[str, object]] = []
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
            if outcome["exit_code"] != 0:
                status = "failure"
                break
        record = {
            "schema_version": "1.1.0",
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
        record["record_sha256"] = sha256(canonical(record)).hexdigest()
        atomic_write(args.results_dir / f"{stage_id}.json", record)
        if status != "success":
            raise SystemExit(f"validation stage failed: {stage_id}")


if __name__ == "__main__":
    main()
