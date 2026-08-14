from __future__ import annotations

import argparse
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


def provision(
    *,
    project: str,
    purpose: str,
    secret_id: str,
    value_file: Path | None = None,
    execute: bool,
) -> dict[str, object]:
    if execute:
        raise SecretProvisionError(
            "direct secret mutation is prohibited; route the request through "
            "Omega-X -> Ultra-Secrets Agent -> Secret Broker -> Google Cloud Secret Manager"
        )
    _run(["gcloud", "secrets", "describe", secret_id, "--project", project, "--location", REGION, "--format=value(name)"])
    prior = latest_exact_reference(project=project, secret_id=secret_id)
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


def validate_broker_receipt(
    receipt: dict[str, object],
    *,
    project: str,
    purpose: str,
    secret_id: str,
) -> dict[str, object]:
    reference = str(receipt.get("exact_version_ref") or "")
    expected_prefix = (
        f"projects/{project}/locations/{REGION}/secrets/{secret_id}/versions/"
    )
    metadata = receipt.get("version_metadata")
    if (
        receipt.get("schema_version") != "aigc.secret-broker-regional-version-receipt.v1"
        or receipt.get("broker_path")
        != "Omega-X/Ultra-Secrets-Agent/Secret-Broker/Google-Cloud-Secret-Manager"
        or receipt.get("project_id") != project
        or receipt.get("region") != REGION
        or receipt.get("purpose") != purpose
        or receipt.get("secret_id") != secret_id
        or not reference.startswith(expected_prefix)
        or REFERENCE.fullmatch(reference) is None
        or not isinstance(metadata, dict)
        or metadata.get("name") != reference
        or metadata.get("state") != "ENABLED"
        or not isinstance(metadata.get("create_time"), str)
        or not metadata.get("create_time")
        or not isinstance(metadata.get("etag"), str)
        or not metadata.get("etag")
        or receipt.get("secret_value_exposed_to_agent") is not False
        or not re.fullmatch(
            r"[a-f0-9]{64}",
            str(receipt.get("broker_attestation_sha256") or ""),
        )
    ):
        raise SecretProvisionError(
            "Secret Broker receipt does not prove the exact enabled numeric Montréal version"
        )
    return {
        "schema_version": receipt["schema_version"],
        "project_id": project,
        "region": REGION,
        "purpose": purpose,
        "secret_id": secret_id,
        "exact_version_ref": reference,
        "version_state": "ENABLED",
        "version_create_time": metadata["create_time"],
        "version_etag": metadata["etag"],
        "broker_attestation_sha256": receipt["broker_attestation_sha256"],
        "secret_value_exposed_to_agent": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--secret-id", required=True)
    parser.add_argument(
        "--broker-receipt",
        type=Path,
        help="validate a Secret Broker receipt without reading secret material",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.broker_receipt is None:
        result = provision(
            project=args.project,
            purpose=args.purpose,
            secret_id=args.secret_id,
            execute=False,
        )
    else:
        result = validate_broker_receipt(
            json.loads(args.broker_receipt.read_text(encoding="utf-8")),
            project=args.project,
            purpose=args.purpose,
            secret_id=args.secret_id,
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
