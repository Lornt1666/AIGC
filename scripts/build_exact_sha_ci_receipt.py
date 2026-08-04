from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile

EXPECTED_STAGES = ["contracts", "redaction", "procurement_smoke", "provider_discovery", "terraform_inert", "tests", "readiness"]


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical(value) + b"\n")
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def load_records(directory: Path, bindings: dict, contract_sha: str) -> dict[str, str]:
    conclusions = {}
    for stage in EXPECTED_STAGES:
        path = directory / f"{stage}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        observed = value.pop("record_sha256")
        if sha256(canonical(value)).hexdigest() != observed: raise SystemExit(f"stage record digest mismatch: {stage}")
        for key, expected in bindings.items():
            if value.get(key) != expected: raise SystemExit(f"stage record {key} mismatch: {stage}")
        if value.get("contract_sha256") != contract_sha or value.get("stage_id") != stage: raise SystemExit(f"stage binding mismatch: {stage}")
        if value.get("status") != "success" or any(item.get("exit_code") != 0 for item in value.get("command_outcomes", [])): raise SystemExit(f"stage failed: {stage}")
        if value.get("external_action_performed") is not False or value.get("production_activation_authorized") is not False: raise SystemExit(f"authority violation: {stage}")
        conclusions[stage] = "success"
    return conclusions


def create_inventory(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): digest_file(path) for path in sorted(root.rglob("*")) if path.is_file() and path.name != "upload_inventory.json"}


def verify_inventory(root: Path) -> None:
    inventory_path = root / "upload_inventory.json"
    expected = json.loads(inventory_path.read_text(encoding="utf-8"))
    observed = create_inventory(root)
    if observed != expected: raise SystemExit("final upload inventory mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path)
    parser.add_argument("--requested-sha")
    parser.add_argument("--observed-sha")
    parser.add_argument("--tree-sha")
    parser.add_argument("--broker-revision")
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--run-number", type=int)
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--stage-results", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--verify-inventory", action="store_true")
    args = parser.parse_args()
    if args.verify_inventory:
        verify_inventory(args.output_root); return
    if args.requested_sha != args.observed_sha: raise SystemExit("checkout SHA mismatch")
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if request.get("broker_revision") != args.broker_revision: raise SystemExit("broker revision mismatch")
    contract = json.loads(args.contract.read_text(encoding="utf-8")); contract_sha = sha256(canonical(contract)).hexdigest()
    bindings = {"target_sha": args.requested_sha, "tested_tree_sha": args.tree_sha, "broker_revision": args.broker_revision, "run_number": args.run_number, "run_id": args.run_id}
    conclusions = load_records(args.stage_results, bindings, contract_sha)
    if args.output_root.exists(): shutil.rmtree(args.output_root)
    (args.output_root / "stage_results").mkdir(parents=True)
    for path in sorted(args.stage_results.glob("*.json")): shutil.copy2(path, args.output_root / "stage_results" / path.name)
    (args.output_root / "request").mkdir(); shutil.copy2(args.request, args.output_root / "request" / "request.json")
    base_manifest = create_inventory(args.output_root); atomic_write(args.output_root / "artifact_manifest.json", base_manifest)
    receipt = {
        "schema_version": "1.1.0", "request_sha256": sha256(canonical(request)).hexdigest(),
        "requested_target_sha": args.requested_sha, "observed_checkout_sha": args.observed_sha,
        "tested_tree_sha": args.tree_sha, "broker_revision": args.broker_revision,
        "validation_contract_sha256": contract_sha, "run_number": args.run_number, "run_id": args.run_id,
        "broker_validation_conclusion": "success", "workflow_conclusion_at_receipt": "pending",
        "step_conclusions": conclusions, "artifact_manifest_sha256": sha256(canonical(base_manifest)).hexdigest(),
        "external_action_performed": False, "production_activation_authorized": False,
    }
    receipt["receipt_sha256"] = sha256(canonical(receipt)).hexdigest(); atomic_write(args.output_root / "exact_sha_ci_receipt.json", receipt)
    completion = {"schema_version": "1.0.0", "receipt_sha256": receipt["receipt_sha256"], "receipt_file_sha256": digest_file(args.output_root / "exact_sha_ci_receipt.json"), "artifact_manifest_file_sha256": digest_file(args.output_root / "artifact_manifest.json"), "external_action_performed": False, "production_activation_authorized": False}
    completion["completion_sha256"] = sha256(canonical(completion)).hexdigest(); atomic_write(args.output_root / "completion_manifest.json", completion)
    atomic_write(args.output_root / "upload_inventory.json", create_inventory(args.output_root))
    verify_inventory(args.output_root)


if __name__ == "__main__": main()
