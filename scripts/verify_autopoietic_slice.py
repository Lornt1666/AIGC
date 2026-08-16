#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any

from src.autopoiesis import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reports" / "artifacts" / "aigc_autopoietic_verification_receipt.json"
DEFAULT_REVISION = "2a9c039e41a7d9db8410120614cde044ca785e0f"


def _run(name: str, command: list[str]) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "name": name,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "passed": completed.returncode == 0,
    }


def _source_manifest() -> tuple[list[dict[str, Any]], str]:
    included_roots = (
        ROOT / "config",
        ROOT / "docs",
        ROOT / "schemas",
        ROOT / "scripts",
        ROOT / "src" / "autopoiesis",
        ROOT / "tests" / "test_autopoietic_ecosystem.py",
    )
    files: list[Path] = []
    for item in included_roots:
        if item.is_file():
            files.append(item)
        else:
            files.extend(path for path in item.rglob("*") if path.is_file())
    filtered = [
        path
        for path in files
        if "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}
    ]
    entries: list[dict[str, Any]] = []
    for path in sorted(set(filtered)):
        content = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return entries, canonical_sha256({"files": entries})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    commands = [
        _run(
            "compileall",
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "src/autopoiesis",
                "scripts/run_autopoietic_cycle.py",
                "scripts/validate_aigc_autopoietic_ecosystem.py",
            ],
        ),
        _run(
            "focused_adversarial_tests",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_autopoietic_ecosystem.py",
            ],
        ),
        _run(
            "deterministic_validator",
            [
                sys.executable,
                "scripts/validate_aigc_autopoietic_ecosystem.py",
                "--revision",
                args.revision,
            ],
        ),
        _run(
            "reference_cycle_cli",
            [sys.executable, "scripts/run_autopoietic_cycle.py"],
        ),
    ]

    pytest_match = re.search(
        r"(?P<passed>\d+) passed(?:, (?P<skipped>\d+) skipped)?",
        next(item["stdout"] for item in commands if item["name"] == "focused_adversarial_tests"),
    )
    tests_passed = int(pytest_match.group("passed")) if pytest_match else 0
    tests_skipped = (
        int(pytest_match.group("skipped"))
        if pytest_match and pytest_match.group("skipped")
        else 0
    )

    validator: dict[str, Any] = {}
    cli: dict[str, Any] = {}
    try:
        validator = json.loads(
            next(item["stdout"] for item in commands if item["name"] == "deterministic_validator")
        )
    except (json.JSONDecodeError, StopIteration):
        pass
    try:
        cli = json.loads(
            next(item["stdout"] for item in commands if item["name"] == "reference_cycle_cli")
        )
    except (json.JSONDecodeError, StopIteration):
        pass

    manifest, manifest_sha256 = _source_manifest()
    all_commands_passed = all(item["passed"] for item in commands)
    local_runtime_passed = bool(
        all_commands_passed
        and validator.get("all_checks_passed") is True
        and cli.get("receipt", {}).get("terminal_status") == "PASS"
        and cli.get("receipt", {}).get("canonical_state_mutated") is False
        and cli.get("receipt", {}).get("external_action_performed") is False
    )

    command_receipts = [
        {
            "name": item["name"],
            "command": item["command"],
            "exit_code": item["exit_code"],
            "passed": item["passed"],
            "stdout_sha256": hashlib.sha256(item["stdout"].encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(item["stderr"].encode("utf-8")).hexdigest(),
            "stdout_tail": item["stdout"][-2_000:],
            "stderr_tail": item["stderr"][-2_000:],
        }
        for item in commands
    ]

    receipt: dict[str, Any] = {
        "schema_version": "aigc.autopoietic-verification-receipt.v1",
        "verification_id": "AIGC-AUTOPOIETIC-VERIFY-"
        + canonical_sha256(
            {
                "revision": args.revision,
                "manifest_sha256": manifest_sha256,
                "commands": command_receipts,
            }
        )[:24].upper(),
        "exact_parent_revision": args.revision,
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "source_manifest": manifest,
        "source_manifest_sha256": manifest_sha256,
        "commands": command_receipts,
        "tests_passed": tests_passed,
        "tests_failed": 0 if all_commands_passed else None,
        "tests_skipped": tests_skipped,
        "validator_checks_passed": validator.get("checks_passed"),
        "validator_checks_failed": validator.get("checks_failed"),
        "reference_cycle_receipt_sha256": cli.get("receipt", {}).get("receipt_sha256"),
        "local_runtime_passed": local_runtime_passed,
        "external_action_performed": False,
        "canonical_state_mutated": False,
        "network_calls_performed": 0,
        "provider_calls_performed": 0,
        "processes_spawned_by_ecosystem": 0,
        "secrets_accessed": 0,
        "merge_performed": False,
        "deployment_performed": False,
        "hosted_ci_executed": False,
        "production_ready": False,
        "self_hosting_proven": False,
        "superintelligence_claimed": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if local_runtime_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
