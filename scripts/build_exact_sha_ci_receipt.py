from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

EXPECTED_STAGES = ["contracts", "redaction", "procurement_smoke", "provider_discovery", "terraform_inert", "tests", "readiness"]


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_stage_records(directory: Path, contract_sha: str) -> dict[str, str]:
    conclusions = {}
    for stage in EXPECTED_STAGES:
        path = directory / f"{stage}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        observed_digest = value.pop("record_sha256")
        if sha256(canonical(value)).hexdigest() != observed_digest:
            raise SystemExit(f"stage record digest mismatch: {stage}")
        if value.get("stage_id") != stage or value.get("contract_sha256") != contract_sha:
            raise SystemExit(f"stage record binding mismatch: {stage}")
        if value.get("status") != "success" or value.get("exit_code") != 0:
            raise SystemExit(f"stage did not succeed: {stage}")
        if value.get("external_action_performed") is not False or value.get("production_activation_authorized") is not False:
            raise SystemExit(f"stage authority violation: {stage}")
        conclusions[stage] = "success"
    return conclusions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--requested-sha", required=True)
    parser.add_argument("--observed-sha", required=True)
    parser.add_argument("--tree-sha", required=True)
    parser.add_argument("--broker-revision", required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--run-number", type=int, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.requested_sha != args.observed_sha: raise SystemExit("checkout SHA mismatch")
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if request.get("broker_revision") != args.broker_revision: raise SystemExit("broker revision mismatch")
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    contract_sha = sha256(canonical(contract)).hexdigest()
    conclusions = load_stage_records(args.artifacts / "stage_results", contract_sha)
    manifest = {}
    for path in sorted(p for p in args.artifacts.rglob("*") if p.is_file() and "receipt" not in p.parts):
        manifest[str(path.relative_to(args.artifacts))] = digest_file(path)
    manifest_bytes = canonical(manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "artifact_manifest.json"
    manifest_path.write_bytes(manifest_bytes + b"\n")
    receipt = {
        "schema_version": "1.0.0", "request_sha256": sha256(canonical(request)).hexdigest(),
        "requested_target_sha": args.requested_sha, "observed_checkout_sha": args.observed_sha,
        "tested_tree_sha": args.tree_sha, "broker_revision": args.broker_revision,
        "validation_contract_sha256": contract_sha, "run_number": args.run_number, "run_id": args.run_id,
        "job_conclusion": "success", "step_conclusions": conclusions, "test_result": "passed",
        "artifact_manifest_sha256": sha256(manifest_bytes).hexdigest(),
        "external_action_performed": False, "production_activation_authorized": False,
    }
    receipt["receipt_sha256"] = sha256(canonical(receipt)).hexdigest()
    receipt_path = args.output_dir / "exact_sha_ci_receipt.json"
    receipt_path.write_bytes(canonical(receipt) + b"\n")
    completion = {
        "schema_version": "1.0.0", "receipt_sha256": receipt["receipt_sha256"],
        "receipt_file_sha256": digest_file(receipt_path), "artifact_manifest_file_sha256": digest_file(manifest_path),
        "uploaded_root": "reports/artifacts/exact_sha_ci", "external_action_performed": False,
        "production_activation_authorized": False,
    }
    completion["completion_sha256"] = sha256(canonical(completion)).hexdigest()
    (args.output_dir / "completion_manifest.json").write_bytes(canonical(completion) + b"\n")

if __name__ == "__main__":
    main()
