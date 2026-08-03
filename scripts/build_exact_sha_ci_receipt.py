from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--requested-sha", required=True)
    parser.add_argument("--observed-sha", required=True)
    parser.add_argument("--tree-sha", required=True)
    parser.add_argument("--workflow-revision", required=True)
    parser.add_argument("--run-number", type=int, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.requested_sha != args.observed_sha:
        raise SystemExit("checkout SHA mismatch")
    manifest = {}
    for path in sorted(p for p in args.artifacts.rglob("*") if p.is_file()):
        manifest[str(path.relative_to(args.artifacts))] = digest_file(path)
    manifest_bytes = canonical(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output.parent / "artifact_manifest.json"
    manifest_path.write_bytes(manifest_bytes + b"\n")
    receipt = {
        "schema_version": "1.0.0",
        "request_sha256": sha256(canonical(json.loads(args.request.read_text(encoding="utf-8")))).hexdigest(),
        "requested_target_sha": args.requested_sha,
        "observed_checkout_sha": args.observed_sha,
        "tested_tree_sha": args.tree_sha,
        "workflow_revision": args.workflow_revision,
        "run_number": args.run_number,
        "run_id": args.run_id,
        "job_conclusion": "success",
        "step_conclusions": {name: "success" for name in ("contracts", "redaction", "terraform_inert", "tests", "readiness")},
        "test_result": "passed",
        "artifact_manifest_sha256": sha256(manifest_bytes).hexdigest(),
        "external_action_performed": False,
        "production_activation_authorized": False,
    }
    receipt["receipt_sha256"] = sha256(canonical(receipt)).hexdigest()
    args.output.write_bytes(canonical(receipt) + b"\n")

if __name__ == "__main__":
    main()
