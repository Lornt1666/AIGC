from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Sequence


REGION = "northamerica-northeast1"
REFERENCE = re.compile(
    r"^projects/(?P<project>[a-z][a-z0-9-]{4,28}[a-z0-9])/locations/"
    r"northamerica-northeast1/secrets/(?P<secret>[A-Za-z0-9_-]+)/versions/(?P<version>[1-9][0-9]*)$"
)


class SecretProvisionError(RuntimeError):
    pass


class SecretMutationIndeterminate(SecretProvisionError):
    pass


def _run(command: Sequence[str], *, capture: bool = True, mutating: bool = False) -> str:
    completed = subprocess.run(list(command), capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        error = SecretMutationIndeterminate if mutating else SecretProvisionError
        raise error(f"command failed: {' '.join(command[:3])}")
    return completed.stdout.strip() if capture else ""


def latest_exact_reference(*, project: str, secret_id: str) -> str | None:
    try:
        version = _run([
            "gcloud", "secrets", "versions", "list", secret_id,
            "--project", project,
            "--location", REGION,
            "--filter", "state=ENABLED",
            "--sort-by", "~createTime",
            "--limit", "1",
            "--format", "value(name)",
        ])
    except SecretProvisionError:
        return None
    if not version:
        return None
    candidate = f"projects/{project}/locations/{REGION}/secrets/{secret_id}/versions/{version.split('/')[-1]}"
    return candidate if REFERENCE.fullmatch(candidate) else None


def provision(*, project: str, purpose: str, secret_id: str, value_file: Path, execute: bool) -> dict[str, object]:
    _run(["gcloud", "secrets", "describe", secret_id, "--project", project, "--location", REGION, "--format=value(name)"])
    prior = latest_exact_reference(project=project, secret_id=secret_id)
    if not execute:
        return {
            "schema_version": "aigc.regional-secret-version-plan.v1",
            "project_id": project,
            "region": REGION,
            "purpose": purpose,
            "secret_id": secret_id,
            "existing_exact_version_ref": prior,
            "new_version_authorized": False,
            "secret_value_read_by_script": False,
            "secret_value_emitted": False,
        }
    if not value_file.is_file():
        raise SecretProvisionError("value file does not exist")
    if value_file.stat().st_size <= 0:
        raise SecretProvisionError("value file is empty")
    value_digest = hashlib.sha256(value_file.read_bytes()).hexdigest()
    created = _run([
        "gcloud", "secrets", "versions", "add", secret_id,
        "--project", project,
        "--location", REGION,
        f"--data-file={value_file}",
        "--format=value(name)",
    ], mutating=True)
    version = created.split("/")[-1]
    reference = f"projects/{project}/locations/{REGION}/secrets/{secret_id}/versions/{version}"
    if not REFERENCE.fullmatch(reference):
        raise SecretProvisionError("provider returned a non-canonical regional secret version")
    return {
        "schema_version": "aigc.regional-secret-version-receipt.v1",
        "project_id": project,
        "region": REGION,
        "purpose": purpose,
        "secret_id": secret_id,
        "exact_version_ref": reference,
        "source_value_sha256": value_digest,
        "previous_exact_version_ref": prior,
        "secret_value_emitted": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--secret-id", required=True)
    parser.add_argument("--value-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = provision(
        project=args.project,
        purpose=args.purpose,
        secret_id=args.secret_id,
        value_file=args.value_file,
        execute=args.execute,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SecretProvisionError as exc:
        raise SystemExit(f"regional secret provisioning blocked: {exc}") from exc
