from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Sequence

from scripts.aigc_external_release_procurement import (
    ExternalReleaseContract,
    ProcurementError,
    assert_git_identity,
    build_resource_manifest,
    canonical_sha256,
    discover,
    terraform_inputs,
)


ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "infra" / "gcp" / "quebec"


class TerraformFoundationError(RuntimeError):
    pass


class TerraformApplyIndeterminate(TerraformFoundationError):
    pass


def _run(command: Sequence[str], *, capture: bool = True, mutating: bool = False) -> str:
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        error = TerraformApplyIndeterminate if mutating else TerraformFoundationError
        raise error(f"command failed: {' '.join(command[:4])}")
    return completed.stdout.strip() if capture else ""


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TerraformFoundationError(f"{path} must contain a JSON object")
    return value


def _digest_file(path: Path) -> str:
    if not path.is_file():
        raise TerraformFoundationError(f"required file does not exist: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_binding(contract: ExternalReleaseContract, state_receipt: dict[str, Any]) -> tuple[str, str]:
    if state_receipt.get("schema_version") != "aigc.quebec-terraform-state-receipt.v1":
        raise TerraformFoundationError("invalid Terraform state receipt schema")
    if state_receipt.get("status") != "succeeded":
        raise TerraformFoundationError("Terraform state backend is not verified successful")
    if state_receipt.get("project_id") != contract.project_id:
        raise TerraformFoundationError("Terraform state receipt project mismatch")
    if state_receipt.get("region") != contract.payload["region"]:
        raise TerraformFoundationError("Terraform state receipt region mismatch")
    if state_receipt.get("reconciliation_required") is not False:
        raise TerraformFoundationError("Terraform state backend requires reconciliation")
    bucket = str(state_receipt.get("bucket") or "")
    prefix = str(state_receipt.get("prefix") or "")
    if not bucket or not prefix:
        raise TerraformFoundationError("Terraform state receipt omitted backend bucket/prefix")
    return bucket, prefix


def _init_backend(*, bucket: str, prefix: str) -> None:
    _run(
        [
            "terraform", f"-chdir={TF_DIR}", "init",
            "-reconfigure",
            "-input=false",
            f"-backend-config=bucket={bucket}",
            f"-backend-config=prefix={prefix}",
        ]
    )


def _plan_summary(plan_file: Path) -> dict[str, Any]:
    raw = _run(["terraform", f"-chdir={TF_DIR}", "show", "-json", str(plan_file.resolve())])
    payload = json.loads(raw or "{}")
    if not isinstance(payload, dict):
        raise TerraformFoundationError("terraform show returned invalid JSON")
    changes = payload.get("resource_changes") or []
    summary = {"create": 0, "update": 0, "delete": 0, "replace": 0, "no_op": 0, "read": 0}
    addresses: list[str] = []
    for item in changes:
        if not isinstance(item, dict):
            continue
        actions = list(((item.get("change") or {}).get("actions") or []))
        address = str(item.get("address") or "")
        if address:
            addresses.append(address)
        if actions == ["create"]:
            summary["create"] += 1
        elif actions == ["update"]:
            summary["update"] += 1
        elif actions == ["delete"]:
            summary["delete"] += 1
        elif "delete" in actions and "create" in actions:
            summary["replace"] += 1
        elif actions == ["read"]:
            summary["read"] += 1
        elif actions == ["no-op"]:
            summary["no_op"] += 1
    if summary["delete"] or summary["replace"]:
        raise TerraformFoundationError("current Québec foundation gate prohibits destroy/replace actions")
    return {"counts": summary, "addresses": tuple(sorted(addresses))}


def create_plan(
    *,
    contract: ExternalReleaseContract,
    state_receipt: dict[str, Any],
    plan_file: Path,
    receipt_file: Path,
) -> dict[str, Any]:
    assert_git_identity(contract)
    if contract.authority["terraform_plan_authorized"] is not True:
        raise TerraformFoundationError("Terraform plan authority is absent")
    manifest = build_resource_manifest(contract)
    variables = terraform_inputs(contract, manifest)
    discovery = discover(contract)
    if not discovery["project_number_matches"] or not discovery["billing_link_matches"] or not discovery["billing_link_enabled"]:
        raise TerraformFoundationError("verified project/billing binding is required before Terraform plan")
    bucket, prefix = _state_binding(contract, state_receipt)
    _init_backend(bucket=bucket, prefix=prefix)

    plan_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".tfvars.json", encoding="utf-8", delete=False) as handle:
        var_path = Path(handle.name)
        json.dump(variables, handle, sort_keys=True)
    try:
        _run(
            [
                "terraform", f"-chdir={TF_DIR}", "plan",
                "-input=false",
                "-lock=true",
                "-lock-timeout=60s",
                f"-var-file={var_path}",
                f"-out={plan_file.resolve()}",
            ]
        )
    finally:
        var_path.unlink(missing_ok=True)

    summary = _plan_summary(plan_file)
    plan_sha256 = _digest_file(plan_file)
    receipt = {
        "schema_version": "aigc.quebec-terraform-foundation-plan-receipt.v1",
        "repository": "Lornt1666/AIGC",
        "project_id": contract.project_id,
        "region": contract.payload["region"],
        "release_sha": contract.payload["release_sha"],
        "release_tree_sha": contract.payload["release_tree_sha"],
        "procurement_sha256": canonical_sha256(contract.payload),
        "resource_manifest_sha256": canonical_sha256(manifest),
        "state_receipt_sha256": canonical_sha256(state_receipt),
        "backend_bucket": bucket,
        "backend_prefix": prefix,
        "plan_sha256": plan_sha256,
        "resource_change_counts": summary["counts"],
        "planned_resource_addresses": summary["addresses"],
        "terraform_apply_performed": False,
        "cloud_mutation_performed": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    receipt_file.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return receipt


def apply_plan(
    *,
    contract: ExternalReleaseContract,
    state_receipt: dict[str, Any],
    plan_file: Path,
    plan_receipt: dict[str, Any],
    receipt_file: Path,
) -> dict[str, Any]:
    assert_git_identity(contract)
    if contract.authority["terraform_apply_authorized"] is not True:
        raise TerraformFoundationError("Terraform apply authority is absent")
    if contract.authority["resource_creation_authorized"] is not True:
        raise TerraformFoundationError("resource-creation authority is absent")
    bucket, prefix = _state_binding(contract, state_receipt)
    _init_backend(bucket=bucket, prefix=prefix)

    if plan_receipt.get("schema_version") != "aigc.quebec-terraform-foundation-plan-receipt.v1":
        raise TerraformFoundationError("invalid Terraform plan receipt schema")
    checks = {
        "project_id": contract.project_id,
        "release_sha": contract.payload["release_sha"],
        "release_tree_sha": contract.payload["release_tree_sha"],
        "procurement_sha256": canonical_sha256(contract.payload),
        "state_receipt_sha256": canonical_sha256(state_receipt),
        "backend_bucket": bucket,
        "backend_prefix": prefix,
    }
    for name, expected in checks.items():
        if plan_receipt.get(name) != expected:
            raise TerraformFoundationError(f"Terraform plan receipt {name} mismatch")
    if plan_receipt.get("plan_sha256") != _digest_file(plan_file):
        raise TerraformFoundationError("saved Terraform plan digest mismatch")
    counts = plan_receipt.get("resource_change_counts") or {}
    if int(counts.get("delete", 0)) or int(counts.get("replace", 0)):
        raise TerraformFoundationError("saved Terraform plan contains prohibited destructive actions")

    try:
        _run(
            [
                "terraform", f"-chdir={TF_DIR}", "apply",
                "-input=false",
                "-lock=true",
                "-lock-timeout=60s",
                "-auto-approve",
                str(plan_file.resolve()),
            ],
            mutating=True,
        )
    except TerraformApplyIndeterminate:
        partial = {
            "schema_version": "aigc.quebec-terraform-foundation-apply-receipt.v1",
            "status": "indeterminate",
            "project_id": contract.project_id,
            "release_sha": contract.payload["release_sha"],
            "plan_sha256": _digest_file(plan_file),
            "terraform_apply_performed": True,
            "outcome_known": False,
            "reconciliation_required": True,
            "automatic_retry": False,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        receipt_file.parent.mkdir(parents=True, exist_ok=True)
        receipt_file.write_text(json.dumps(partial, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        raise

    outputs_raw = _run(["terraform", f"-chdir={TF_DIR}", "output", "-json"])
    outputs = json.loads(outputs_raw or "{}")
    discovery = discover(contract)
    required = {
        "wif_pool_exists": discovery["wif_pool_exists"],
        "wif_provider_exists": discovery["wif_provider_exists"],
        "artifact_registry_exists": discovery["artifact_registry_exists"],
        "cloud_sql_exists": discovery["cloud_sql_exists"],
        "all_service_accounts_exist": all(discovery["service_accounts"].values()),
        "all_regional_secret_metadata_exist": all(discovery["regional_secret_metadata"].values()),
    }
    if not all(required.values()):
        raise TerraformFoundationError("Terraform apply completed but required foundation reconciliation failed")
    receipt = {
        "schema_version": "aigc.quebec-terraform-foundation-apply-receipt.v1",
        "status": "succeeded",
        "project_id": contract.project_id,
        "region": contract.payload["region"],
        "release_sha": contract.payload["release_sha"],
        "release_tree_sha": contract.payload["release_tree_sha"],
        "procurement_sha256": canonical_sha256(contract.payload),
        "plan_sha256": _digest_file(plan_file),
        "state_receipt_sha256": canonical_sha256(state_receipt),
        "terraform_outputs_sha256": canonical_sha256(outputs),
        "foundation_reconciliation": required,
        "terraform_apply_performed": True,
        "outcome_known": True,
        "reconciliation_required": False,
        "automatic_retry": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    receipt_file.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--procurement", type=Path, required=True)
    parser.add_argument("--state-receipt", type=Path, required=True)
    parser.add_argument("--mode", choices=("plan", "apply"), required=True)
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--plan-receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = ExternalReleaseContract.load(args.procurement)
    state_receipt = _object(args.state_receipt)
    if args.mode == "plan":
        result = create_plan(
            contract=contract,
            state_receipt=state_receipt,
            plan_file=args.plan_file,
            receipt_file=args.output,
        )
    else:
        if args.plan_receipt is None:
            raise TerraformFoundationError("--plan-receipt is required for apply")
        result = apply_plan(
            contract=contract,
            state_receipt=state_receipt,
            plan_file=args.plan_file,
            plan_receipt=_object(args.plan_receipt),
            receipt_file=args.output,
        )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProcurementError, TerraformFoundationError) as exc:
        raise SystemExit(f"Québec Terraform foundation blocked: {exc}") from exc
