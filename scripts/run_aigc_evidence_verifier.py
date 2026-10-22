#!/usr/bin/env python3
"""CLI wrapper for the AIGC evidence verifier policy engine.

This command evaluates a pre-collected evidence bundle; it does not claim to collect or
cryptographically verify external evidence itself. Trusted adapters must supply receipts
whose provenance has been independently validated. BLOCK exits with status 2.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from aigc_release_evidence_verifier import VerifierPolicy, evaluate_evidence

MAX_INPUT_BYTES = 16 * 1024 * 1024


def _read_json(path: Path):
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input_too_large")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("top_level_json_object_required")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        policy_data = _read_json(args.policy)
        bundle = _read_json(args.bundle)
        policy = VerifierPolicy(
            policy_id=policy_data["policy_id"],
            policy_version=policy_data["policy_version"],
            policy_digest=policy_data["policy_digest"],
            repository=policy_data["repository"],
            repository_id=str(policy_data["repository_id"]),
            owner_id=str(policy_data["owner_id"]),
            workflow_path=policy_data["workflow_path"],
            allowed_events=frozenset(policy_data["allowed_events"]),
            allowed_refs=frozenset(policy_data["allowed_refs"]),
            required_checks=frozenset(policy_data["required_checks"]),
            required_adversarial_cases=frozenset(policy_data["required_adversarial_cases"]),
            attestation_predicate=policy_data["attestation_predicate"],
            attestation_verifier=policy_data["attestation_verifier"],
            attestation_verifier_version=policy_data["attestation_verifier_version"],
            max_evidence_age_seconds=int(policy_data.get("max_evidence_age_seconds", 3600)),
        )
        result = evaluate_evidence(policy, bundle)
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(json.dumps({
            "disposition": result["disposition"],
            "release_decision": result["release_decision"],
            "reason_count": len(result["reasons"]),
            "receipt_sha256": result["receipt_sha256"],
            "output": str(args.output),
        }, sort_keys=True))
        return 0 if result["disposition"] == "READY_FOR_CANONICAL_REVIEW" else 2
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        # Do not echo arbitrary exception text that could contain input data.
        print(json.dumps({"disposition": "BLOCK", "reason": "invalid_input_or_io",
                          "error_type": type(exc).__name__}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
