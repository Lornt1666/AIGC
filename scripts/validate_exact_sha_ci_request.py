from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

REQUIRED_CHECKS = {"contracts", "redaction", "procurement_smoke", "provider_discovery", "terraform_inert", "tests", "readiness"}
ALLOWED_KEYS = {
    "schema_version", "request_id", "repository", "target_branch", "target_sha",
    "broker_revision", "requested_checks", "production_activation_authorized", "external_action_authorized",
}


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def validate_request(path: Path, expected_broker_revision: str | None = None) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != ALLOWED_KEYS:
        raise ValueError("request keys do not match the closed contract")
    if value["schema_version"] != "1.0.0": raise ValueError("unsupported schema version")
    if not re.fullmatch(r"CI-RECEIPT-[A-Z0-9-]{8,80}", value["request_id"]): raise ValueError("invalid request_id")
    if value["repository"] != "Lornt1666/AIGC" or value["target_branch"] != "main": raise ValueError("repository or branch mismatch")
    for field in ("target_sha", "broker_revision"):
        if not re.fullmatch(r"[a-f0-9]{40}", value[field]): raise ValueError(f"{field} must be full lowercase SHA")
    if expected_broker_revision and value["broker_revision"] != expected_broker_revision:
        raise ValueError("request broker revision mismatch")
    if set(value["requested_checks"]) != REQUIRED_CHECKS or len(value["requested_checks"]) != len(REQUIRED_CHECKS):
        raise ValueError("canonical checks required exactly once")
    if value["production_activation_authorized"] is not False or value["external_action_authorized"] is not False:
        raise ValueError("external or production authority prohibited")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--expected-broker-revision")
    args = parser.parse_args()
    value = validate_request(args.request, args.expected_broker_revision)
    print(json.dumps({"target_sha": value["target_sha"], "request_sha256": sha256(canonical(value)).hexdigest()}, sort_keys=True))

if __name__ == "__main__":
    main()
