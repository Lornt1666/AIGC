"""Integrated read-only RX-148 closure runner: live GitHub snapshot + signed receipts.

The caller must provision a trusted-key file through a separately protected trust
channel. This command never mutates GitHub or authorizes merge/deploy/release.
"""
from __future__ import annotations

import argparse
import hashlib
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

from aigc_runtime.receipt_verifier import canonical_bytes

from aigc_runtime.closure_workflow import evaluate_closure
from aigc_runtime.github_evidence import GitHubEvidenceError, acquire_live_snapshot
from aigc_runtime.receipt_verifier import Ed25519ReceiptVerifier, ReceiptVerificationError, TrustedReceiptKey


PURPOSES = {
    "protection": "repository-protection-readback",
    "review": "independent-review",
    "provenance": "build-provenance",
    "acceptance": "human-acceptance",
    "rx19_handoff": "rx19-handoff",
    "rx19_decision": "rx19-release-decision",
    "artifact": "artifact-manifest",
}


def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_live_closure(repository: str, pr_number: int, *, trusted_keys_path: str,
                     receipts_path: str, required_ci_jobs: list[str],
                     token_env: str = "GITHUB_TOKEN", release_branch: str = "main") -> dict[str, Any]:
    """Acquire current GitHub state, verify signed receipts, and fail closed on digest drift."""
    snapshot = acquire_live_snapshot(repository, pr_number, token_env=token_env,
                                     required_ci_jobs=required_ci_jobs, release_branch=release_branch)
    key_doc = _read_json(trusted_keys_path)
    receipt_doc = _read_json(receipts_path)
    if not isinstance(key_doc, dict) or key_doc.get("schema_version") != "rx148.trusted-keys.v1" or not isinstance(key_doc.get("keys"), list):
        raise ReceiptVerificationError("trusted_key_document_schema_invalid")
    if not isinstance(receipt_doc, dict) or receipt_doc.get("schema_version") != "rx148.receipts.v1":
        raise ReceiptVerificationError("external_receipt_document_schema_invalid")
    keys = []
    for item in key_doc["keys"]:
        if not isinstance(item, dict):
            raise ReceiptVerificationError("trusted_key_entry_invalid")
        keys.append(TrustedReceiptKey(key_id=item.get("key_id"), public_key_b64=item.get("public_key_b64"),
            issuer=item.get("issuer"), allowed_purposes=tuple(item.get("allowed_purposes", [])),
            status=item.get("status", "ACTIVE")))
    verifier = Ed25519ReceiptVerifier(keys, revoked_receipt_ids=set(key_doc.get("revoked_receipt_ids", [])))
    verified: dict[str, Any] = {}
    errors: dict[str, str] = {}
    receipt_ids: dict[str, str] = {}
    for target in PURPOSES:
        envelope = receipt_doc.get(target)
        if isinstance(envelope, dict) and isinstance(envelope.get("payload"), dict):
            receipt_id = envelope["payload"].get("receipt_id")
            if isinstance(receipt_id, str):
                if receipt_id in receipt_ids.values():
                    errors[target] = "duplicate_receipt_id_in_bundle"
                else:
                    receipt_ids[target] = receipt_id
    # Verify upstream evidence first. Human acceptance and RX-19 receipts must bind to
    # the digest computed from the exact live observation plus these signed evidence claims.
    core_targets = ("protection", "review", "provenance", "artifact")
    for target in core_targets:
        envelope = receipt_doc.get(target)
        if not isinstance(envelope, dict) or target in errors:
            continue
        expected = {"candidate_sha": snapshot["candidate_sha"]}
        if target in {"provenance", "artifact"}:
            expected["repository"] = repository
        try:
            receipt = verifier.verify(envelope, expected_purpose=PURPOSES[target], expected_bindings=expected)
            payload = dict(envelope["payload"])
            verified[target] = {**payload, "authenticated": True, "verified": True,
                                "receipt_id": payload["receipt_id"], "verification_receipt": receipt}
        except (ReceiptVerificationError, ValueError, TypeError) as exc:
            errors[target] = str(exc)
    core_evidence = {
        "schema_version": snapshot.get("schema_version"), "repository": repository, "pr_number": pr_number,
        "candidate_sha": snapshot.get("candidate_sha"), "observed_head_sha": snapshot.get("observed_head_sha"),
        "base_branch": snapshot.get("base_branch"), "base_sha": snapshot.get("base_sha"),
        "pr_state": snapshot.get("pr_state"), "pr_draft": snapshot.get("pr_draft"),
        "pr_merged": snapshot.get("pr_merged"), "observed_at": snapshot.get("observed_at"),
        "ci_runs": snapshot.get("ci_runs"), "commit_status": snapshot.get("commit_status"),
        "commit_statuses": snapshot.get("commit_statuses"), "check_runs": snapshot.get("check_runs"),
        "reviews": snapshot.get("reviews"), "review_comments": snapshot.get("review_comments"),
        "protection_readbacks": snapshot.get("protection_readbacks"),
        "signed_core_receipts": {name: {"payload": {k: v for k, v in value.items() if k != "verification_receipt"},
            "verification_receipt_digest": value["verification_receipt"]["payload_digest"]} for name, value in sorted(verified.items())},
    }
    computed_digest = "sha256:" + hashlib.sha256(canonical_bytes(core_evidence)).hexdigest()
    claimed_digest = receipt_doc.get("evidence_digest")
    claimed_normalized = claimed_digest if isinstance(claimed_digest, str) and claimed_digest.startswith("sha256:") else ("sha256:" + claimed_digest if isinstance(claimed_digest, str) else None)
    digest_matches = claimed_normalized == computed_digest
    policy_version = receipt_doc.get("policy_version")
    snapshot["computed_evidence_digest"] = computed_digest
    snapshot["evidence_digest"] = computed_digest if digest_matches else None
    snapshot["policy_version"] = policy_version if isinstance(policy_version, str) else None
    if not digest_matches:
        errors["evidence_digest"] = "claimed_packet_digest_does_not_match_canonical_live_evidence"
    for target in ("acceptance", "rx19_handoff", "rx19_decision"):
        envelope = receipt_doc.get(target)
        if not isinstance(envelope, dict) or target in errors:
            continue
        expected = {"candidate_sha": snapshot["candidate_sha"], "evidence_digest": computed_digest}
        if target == "acceptance" and isinstance(policy_version, str):
            expected["policy_version"] = policy_version
        try:
            receipt = verifier.verify(envelope, expected_purpose=PURPOSES[target], expected_bindings=expected)
            payload = dict(envelope["payload"])
            verified[target] = {**payload, "authenticated": True, "verified": True,
                                "receipt_id": payload["receipt_id"], "verification_receipt": receipt}
        except (ReceiptVerificationError, ValueError, TypeError) as exc:
            errors[target] = str(exc)
    for name in ("protection", "review", "provenance", "acceptance", "rx19_handoff", "rx19_decision"):
        if name in verified:
            snapshot[name] = verified[name]
        elif name in errors:
            snapshot[name] = {"authenticated": False, "verified": False, "status": "UNVERIFIABLE",
                              "verification_error": errors[name]}
    # A signed manifest claim is not independent byte verification. This adapter does
    # not download artifact bytes, so the artifact gate is forcibly UNVERIFIABLE.
    if "artifact" in verified:
        artifact = dict(verified["artifact"])
        artifact["bytes_verified"] = False
        artifact["manifest_verified"] = False
        artifact["independent_byte_verification"] = False
        snapshot["artifact"] = artifact
    elif "artifact" in errors:
        snapshot["artifact"] = {"status": "UNVERIFIABLE", "bytes_verified": False,
                                "manifest_verified": False, "verification_error": errors["artifact"]}
    if "protection" in verified:
        protection = snapshot["protection"]
        if protection.get("base_branch") != snapshot.get("base_branch") or protection.get("release_branch") != release_branch:
            protection["authenticated"] = False
            protection["status"] = "UNVERIFIABLE"
            errors["protection"] = "signed_protection_receipt_branch_binding_mismatch"
    snapshot["acquisition"]["signed_receipts_verified"] = sorted(verified)
    snapshot["acquisition"]["receipt_errors"] = dict(sorted(errors.items()))
    snapshot["acquisition"]["trust_store_id"] = key_doc.get("trust_store_id", "UNNAMED_TRUST_STORE")
    snapshot["acquisition"]["evidence_digest_matches"] = digest_matches
    result = evaluate_closure(snapshot)
    result["acquisition"] = snapshot["acquisition"]
    result["computed_evidence_digest"] = computed_digest
    result["evidence_digest_claim_matches"] = digest_matches
    result["observed_at"] = snapshot["observed_at"]
    result["pr_state"] = snapshot["pr_state"]
    result["pr_draft"] = snapshot["pr_draft"]
    result["pr_merged"] = snapshot["pr_merged"]
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire live GitHub evidence and evaluate RX-148 closure without side effects.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--trusted-keys", required=True, help="Protected, administrator-managed trust-store JSON.")
    parser.add_argument("--receipts", required=True, help="Signed external evidence receipt bundle JSON.")
    parser.add_argument("--required-ci-job", action="append", default=[], help="Required job name; repeat per job.")
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--release-branch", default="main")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = run_live_closure(args.repository, args.pr, trusted_keys_path=args.trusted_keys,
            receipts_path=args.receipts, required_ci_jobs=args.required_ci_job,
            token_env=args.token_env, release_branch=args.release_branch)
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0 if result["disposition"] == "RX19_APPROVED_EVIDENCE_ONLY_NO_ACTION" else 2
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, GitHubEvidenceError, ReceiptVerificationError) as exc:
        print(json.dumps({"disposition": "BLOCK", "error": str(exc), "side_effects_performed": False}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
