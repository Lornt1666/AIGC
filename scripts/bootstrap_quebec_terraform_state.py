from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Sequence

from scripts.aigc_external_release_procurement import ExternalReleaseContract, ProcurementError, discover


REGION = "northamerica-northeast1"
RETENTION_SECONDS = 30 * 24 * 60 * 60
SOFT_DELETE_SECONDS = 7 * 24 * 60 * 60
STATE_PREFIX = "aigc/nexus-v1"


class StateBootstrapError(RuntimeError):
    pass


class StateBootstrapIndeterminate(StateBootstrapError):
    pass


def _run(command: Sequence[str], *, mutating: bool = False) -> str:
    completed = subprocess.run(list(command), capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        error = StateBootstrapIndeterminate if mutating else StateBootstrapError
        raise error(f"command failed: {' '.join(command[:4])}")
    return completed.stdout.strip()


def bucket_name(contract: ExternalReleaseContract) -> str:
    return f"{contract.project_id}-{contract.prefix}-tfstate"


def _describe(bucket: str) -> dict[str, Any] | None:
    completed = subprocess.run(
        ["gcloud", "storage", "buckets", "describe", f"gs://{bucket}", "--format=json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    value = json.loads(completed.stdout or "{}")
    return value if isinstance(value, dict) else None


def _controls(payload: dict[str, Any] | None) -> dict[str, bool]:
    if payload is None:
        return {
            "exists": False,
            "montreal_location": False,
            "uniform_access": False,
            "public_access_prevention": False,
            "versioning": False,
            "retention_configured": False,
        }
    iam = payload.get("iamConfiguration") or {}
    uniform = iam.get("uniformBucketLevelAccess") or {}
    location = str(payload.get("location") or "").lower()
    retention = payload.get("retentionPolicy") or {}
    return {
        "exists": True,
        "montreal_location": location == REGION,
        "uniform_access": uniform.get("enabled") is True,
        "public_access_prevention": str(iam.get("publicAccessPrevention") or "").lower() == "enforced",
        "versioning": (payload.get("versioning") or {}).get("enabled") is True,
        "retention_configured": int(retention.get("retentionPeriod") or 0) >= RETENTION_SECONDS,
    }


def bootstrap(
    contract: ExternalReleaseContract,
    *,
    execute: bool,
    output: Path,
) -> dict[str, Any]:
    discovery = discover(contract)
    if not discovery["project_number_matches"] or not discovery["billing_link_matches"] or not discovery["billing_link_enabled"]:
        raise StateBootstrapError("verified project/billing binding is required")
    name = bucket_name(contract)
    before = _describe(name)
    before_controls = _controls(before)

    if not execute:
        result = {
            "schema_version": "aigc.quebec-terraform-state-plan.v1",
            "project_id": contract.project_id,
            "region": REGION,
            "bucket": name,
            "prefix": STATE_PREFIX,
            "observed_controls": before_controls,
            "cloud_mutation_performed": False,
        }
    else:
        if contract.template_only:
            raise StateBootstrapError("template-only procurement cannot bootstrap Terraform state")
        if contract.authority.get("state_backend_bootstrap_authorized") is not True:
            raise StateBootstrapError("state backend bootstrap is not authorized")
        if contract.payload.get("monthly_budget_cad", 0) <= 0:
            raise StateBootstrapError("nonzero reviewed staging budget is required")

        mutated = False
        try:
            if before is None:
                _run(
                    [
                        "gcloud", "storage", "buckets", "create", f"gs://{name}",
                        "--project", contract.project_id,
                        "--location", REGION,
                        "--uniform-bucket-level-access",
                        "--public-access-prevention",
                        f"--retention-period={RETENTION_SECONDS}",
                        f"--soft-delete-duration={SOFT_DELETE_SECONDS}",
                    ],
                    mutating=True,
                )
                mutated = True
            _run(
                [
                    "gcloud", "storage", "buckets", "update", f"gs://{name}",
                    "--versioning",
                    "--uniform-bucket-level-access",
                    "--public-access-prevention",
                    f"--retention-period={RETENTION_SECONDS}",
                ],
                mutating=True,
            )
            mutated = True
        except StateBootstrapIndeterminate:
            partial = {
                "schema_version": "aigc.quebec-terraform-state-receipt.v1",
                "status": "indeterminate",
                "project_id": contract.project_id,
                "region": REGION,
                "bucket": name,
                "prefix": STATE_PREFIX,
                "cloud_mutation_performed": mutated,
                "reconciliation_required": True,
                "automatic_retry": False,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(partial, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            raise

        after = _describe(name)
        controls = _controls(after)
        if not all(controls.values()):
            raise StateBootstrapError("Terraform state bucket does not satisfy all required controls")
        result = {
            "schema_version": "aigc.quebec-terraform-state-receipt.v1",
            "status": "succeeded",
            "project_id": contract.project_id,
            "region": REGION,
            "bucket": name,
            "prefix": STATE_PREFIX,
            "controls": controls,
            "cloud_mutation_performed": mutated,
            "reconciliation_required": False,
            "automatic_retry": False,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--procurement", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = bootstrap(
        ExternalReleaseContract.load(args.procurement),
        execute=args.execute,
        output=args.output,
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProcurementError, StateBootstrapError) as exc:
        raise SystemExit(f"Québec Terraform state bootstrap blocked: {exc}") from exc
