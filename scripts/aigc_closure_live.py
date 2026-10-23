"""Integrated read-only RX-148 closure runner: live GitHub snapshot + signed receipts.

The caller must provision a trusted-key file through a separately protected trust
channel. This command never mutates GitHub or authorizes merge/deploy/release.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

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
    """Acquire live state, verify signed receipts, then evaluate all gates fail-closed."""
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
        keys.append(TrustedReceiptKey(
            key_id=item.get("key_id"), public_key_b64=item.get("public_key_b64"),
            issuer=item.get("issuer"), allowed_purposes=tuple(item.get("allowed_purposes", [])),
            status=item.get("status", "ACTIVE")))
    verifier = Ed25519ReceiptVerifier(keys, revoked_receipt_ids=set(key_doc.get("revoked_receipt_ids", [])))
    verified: dict[str, Any] = {}
    for target, purpose in PURPOSES.items():
        envelope = receipt_doc.get(target)
        if not isinstance(envelope, dict):
            continue
        # Signed receipt must bind to the live head. Additional purpose-specific
        # claims are checked by evaluate_closure after signature verification.
        expected = {"candidate_sha": snapshot["candidate_sha"]}
        if target in {"provenance", "artifact"}:
            expected["repository"] = repository
        result = verifier.verify(envelope, expected_purpose=purpose, expected_bindings=expected)
        payload = envelope["payload"]
        verified[target] = {**payload, "authenticated": True, "verified": True,
                            "receipt_id": payload["receipt_id"],
                            "verification_receipt": result}
    # A signed artifact manifest is not proof that bytes were downloaded and hashed.
    # Require a separate local verifier receipt before setting these flags.
    artifact = verified.get("artifact")
    if artifact:
        artifact["bytes_verified"] = artifact.get("bytes_verified") is True
        artifact["manifest_verified"] = artifact.get("manifest_verified") is True
        snapshot["artifact"] = artifact
    for name in ("protection", "review", "provenance", "acceptance", "rx19_handoff", "rx19_decision"):
        if name in verified:
            snapshot[name] = verified[name]
    snapshot["evidence_digest"] = receipt_doc.get("evidence_digest")
    snapshot["policy_version"] = receipt_doc.get("policy_version")
    # A GitHub readback response is not itself a signed admin receipt.
    # A signed receipt must additionally prove both branch bindings.
    if "protection" in verified:
        p = verified["protection"]
        if p.get("base_branch") != snapshot.get("base_branch") or p.get("release_branch") != release_branch:
            p["authenticated"] = False
            p["status"] = "UNVERIFIABLE"
    snapshot["acquisition"]["signed_receipts_verified"] = sorted(verified)
    snapshot["acquisition"]["trust_store_id"] = key_doc.get("trust_store_id", "UNNAMED_TRUST_STORE")
    result = evaluate_closure(snapshot)
    result["acquisition"] = snapshot["acquisition"]
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
