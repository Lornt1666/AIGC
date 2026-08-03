from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

REQUIRED_CHECKS = {"contracts", "redaction", "terraform_inert", "tests", "readiness"}
ALLOWED_KEYS = {
    "schema_version", "request_id", "repository", "target_branch", "target_sha",
    "requested_checks", "production_activation_authorized", "external_action_authorized",
}


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def validate_request(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != ALLOWED_KEYS:
        raise ValueError("request keys do not match the closed contract")
    if value["schema_version"] != "1.0.0": raise ValueError("unsupported schema version")
    if not re.fullmatch(r"CI-RECEIPT-[A-Z0-9-]{8,80}", value["request_id"]): raise ValueError("invalid request_id")
    if value["repository"] != "Lornt1666/AIGC" or value["target_branch"] != "main": raise ValueError("repository or branch mismatch")
    if not re.fullmatch(r"[a-f0-9]{40}", value["target_sha"]): raise ValueError("target_sha must be full lowercase SHA")
    if set(value["requested_checks"]) != REQUIRED_CHECKS or len(value["requested_checks"]) != 5: raise ValueError("canonical checks required exactly once")
    if value["production_activation_authorized"] is not False or value["external_action_authorized"] is not False: raise ValueError("external or production authority prohibited")
    return value


def verify_target(target_sha: str) -> tuple[str, str]:
    subprocess.run(["git", "cat-file", "-e", f"{target_sha}^{{commit}}"], check=True)
    subprocess.run(["git", "merge-base", "--is-ancestor", target_sha, "origin/main"], check=True)
    observed = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if observed != target_sha: raise ValueError("exact checkout mismatch")
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip()
    return observed, tree


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--validate-target", action="store_true")
    args = parser.parse_args()
    value = validate_request(args.request)
    output = {"target_sha": value["target_sha"], "request_sha256": sha256(canonical(value)).hexdigest()}
    if args.validate_target:
        output["observed_checkout_sha"], output["tested_tree_sha"] = verify_target(value["target_sha"])
    print(json.dumps(output, sort_keys=True))

if __name__ == "__main__":
    main()
