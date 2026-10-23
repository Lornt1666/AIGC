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
from typing import Any, Mapping

from aigc_runtime.receipt_verifier import canonical_bytes

from aigc_runtime.closure_workflow import evaluate_closure
from aigc_runtime.artifact_verifier import ArtifactVerificationError, download_and_verify_artifact
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
                     token_env: str = "GITHUB_TOKEN", release_branch: str = "main", prepare: bool = False) -> dict[str, Any]:
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
    artifact_verification: dict[str, Any] = {"status": "UNVERIFIABLE", "bytes_verified": False, "manifest_verified": False}
    artifact_claim = verified.get("artifact")
    if artifact_claim:
        try:
            artifact_id = artifact_claim.get("artifact_id")
            run_id = artifact_claim.get("run_id")
            run_attempt = artifact_claim.get("run_attempt")
            manifest_path = artifact_claim.get("manifest_path")
            archive_sha = artifact_claim.get("sha256")
            if not isinstance(artifact_id, int) or not isinstance(run_id, int) or not isinstance(run_attempt, int):
                raise ArtifactVerificationError("signed_artifact_receipt_missing_artifact_run_attempt_binding")
            if not isinstance(manifest_path, str) or not isinstance(archive_sha, str):
                raise ArtifactVerificationError("signed_artifact_receipt_missing_archive_digest_or_manifest_path")
            run = next((item for item in snapshot.get("ci_runs", []) if isinstance(item, dict)
                and item.get("run_id") == run_id and item.get("run_attempt") == run_attempt
                and item.get("head_sha") == snapshot.get("candidate_sha") and item.get("status") == "completed"
                and item.get("conclusion") == "success"), None)
            if run is None:
                raise ArtifactVerificationError("artifact_run_attempt_not_successful_for_live_candidate")
            metadata = next((item for item in run.get("artifacts", []) if isinstance(item, dict)
                and item.get("id") == artifact_id and item.get("workflow_run_id") == run_id
                and item.get("workflow_run_head_sha") == snapshot.get("candidate_sha") and item.get("expired") is False), None)
            if metadata is None:
                raise ArtifactVerificationError("artifact_id_not_found_on_verified_exact_head_run")
            artifact_verification = download_and_verify_artifact(repository, artifact_id,
                expected_sha256=archive_sha, manifest_path=manifest_path,
                candidate_sha=snapshot["candidate_sha"], run_id=run_id, run_attempt=run_attempt,
                token_env=token_env, api_digest=metadata.get("digest"))
            snapshot["artifact"] = {**artifact_claim, **artifact_verification}
        except (ArtifactVerificationError, ValueError, TypeError, KeyError) as exc:
            errors["artifact_bytes"] = str(exc)
            artifact_verification = {"status": "UNVERIFIABLE", "reason": str(exc),
                "bytes_verified": False, "manifest_verified": False}
            snapshot["artifact"] = {**artifact_claim, "bytes_verified": False,
                "manifest_verified": False, "verification_error": str(exc)}
    else:
        snapshot["artifact"] = {"status": "UNVERIFIABLE", "bytes_verified": False,
            "manifest_verified": False, "verification_error": errors.get("artifact", "signed_artifact_receipt_missing")}
        core_evidence = {
        "schema_version": snapshot.get("schema_version"), "repository": repository, "pr_number": pr_number,
        "candidate_sha": snapshot.get("candidate_sha"), "observed_head_sha": snapshot.get("observed_head_sha"),
        "base_branch": snapshot.get("base_branch"), "base_sha": snapshot.get("base_sha"),
        "pr_state": snapshot.get("pr_state"), "pr_draft": snapshot.get("pr_draft"),
        "pr_merged": snapshot.get("pr_merged"), "head_changed_during_acquisition": snapshot.get("head_changed_during_acquisition"),
        "policy_version": receipt_doc.get("policy_version"),
        "ci_runs": snapshot.get("ci_runs"), "commit_status": snapshot.get("commit_status"),
        "commit_statuses": snapshot.get("commit_statuses"), "check_runs": snapshot.get("check_runs"),
        "reviews": snapshot.get("reviews"), "review_comments": snapshot.get("review_comments"),
        "protection_readbacks": snapshot.get("protection_readbacks"),
        "artifact_verification": artifact_verification,
        "signed_core_receipts": {name: {"payload": {k: v for k, v in value.items() if k != "verification_receipt"},
            "verification_receipt_digest": value["verification_receipt"]["payload_digest"]} for name, value in sorted(verified.items())},
    }
    computed_digest = "sha256:" + hashlib.sha256(canonical_bytes(core_evidence)).hexdigest()
    claimed_digest = receipt_doc.get("evidence_digest")
    claimed_normalized = claimed_digest if isinstance(claimed_digest, str) and claimed_digest.startswith("sha256:") else ("sha256:" + claimed_digest if isinstance(claimed_digest, str) else None)
    digest_claim_matches = claimed_normalized == computed_digest
    digest_matches = digest_claim_matches or prepare
    policy_version = receipt_doc.get("policy_version")
    snapshot["computed_evidence_digest"] = computed_digest
    snapshot["evidence_digest"] = computed_digest if digest_matches else None
    snapshot["policy_version"] = policy_version if isinstance(policy_version, str) else None
    if not digest_claim_matches and not prepare:
        errors["evidence_digest"] = "claimed_packet_digest_does_not_match_canonical_live_evidence"
    for target in ("acceptance", "rx19_handoff", "rx19_decision"):
        if prepare:
            continue
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
    # Artifact byte and manifest claims are replaced by the independent ZIP verifier result above.
    if "protection" in verified:
        protection = snapshot["protection"]
        if protection.get("base_branch") != snapshot.get("base_branch") or protection.get("release_branch") != release_branch:
            protection["authenticated"] = False
            protection["status"] = "UNVERIFIABLE"
            errors["protection"] = "signed_protection_receipt_branch_binding_mismatch"
    snapshot["acquisition"]["signed_receipts_verified"] = sorted(verified)
    snapshot["acquisition"]["receipt_errors"] = dict(sorted(errors.items()))
    snapshot["acquisition"]["trust_store_id"] = key_doc.get("trust_store_id", "UNNAMED_TRUST_STORE")
    snapshot["acquisition"]["evidence_digest_matches"] = "PREPARATION_ONLY" if prepare else digest_claim_matches
    result = evaluate_closure(snapshot)
    result["acquisition"] = snapshot["acquisition"]
    result["computed_evidence_digest"] = computed_digest
    result["evidence_digest_claim_matches"] = "PREPARATION_ONLY" if prepare else digest_claim_matches
    result["observed_at"] = snapshot["observed_at"]
    result["pr_state"] = snapshot["pr_state"]
    result["pr_draft"] = snapshot["pr_draft"]
    result["pr_merged"] = snapshot["pr_merged"]
    return result

def _failure_report(error: Exception, *, repository: str, pr_number: int) -> dict[str, Any]:
    """Return a full fail-closed gate matrix even when live acquisition or trust input fails."""
    definitions = [
        ("G0_LIVE_RECONCILIATION", "closure-orchestrator", "Fetch authenticated PR metadata twice and confirm the head/base stayed stable."),
        ("G1_EXACT_HEAD_CI", "engineering/CI owner", "Acquire complete run/attempt/job pagination and prove all policy-required jobs passed together."),
        ("G2_ARTIFACT_INTEGRITY", "engineering/evidence owner", "Download the exact-run artifact and independently verify ZIP bytes and embedded manifest."),
        ("G3_EFFECTIVE_PROTECTION", "authorized repository administrator", "Supply authenticated effective branch/ruleset protection readback; API denial is not PASS."),
        ("G4_INDEPENDENT_REVIEW", "authorized administrator and qualified independent reviewer", "Bind independent review, review-thread reconciliation, findings and retests to the exact SHA."),
        ("G5_TRUSTED_PROVENANCE", "build/security owner", "Verify signed provenance, trusted builder identity, source SHA and artifact digest."),
        ("G6_HUMAN_ACCEPTANCE", "authorized human approver", "Sign acceptance for the final SHA, policy version and canonical evidence digest."),
        ("G7_RX19_HANDOFF", "release engineering / RX-144 coordinator", "Use the verified RX-19 interface and retain an authenticated exact-packet receipt."),
        ("G8_RX19_DECISION", "RX-19 sole release decision authority", "Obtain an authenticated RX-19 decision bound to the final SHA and evidence digest."),
    ]
    safe_detail = str(error) if isinstance(error, (GitHubEvidenceError, ArtifactVerificationError, ReceiptVerificationError)) else "details_redacted"
    gates = [{"gate_id": gate_id, "status": "UNVERIFIABLE", "accountable_role": role,
              "reason": "live_acquisition_or_trust_input_failed:" + type(error).__name__,
              "required_action": action, "depends_on": [], "dependency_blocked": True} for gate_id, role, action in definitions]
    return {"schema_version": "rx148.closure.v1", "repository": repository, "pr_number": pr_number,
            "candidate_sha": None, "observed_head_sha": None, "gate_results": gates,
            "blockers": [{"gate_id": g["gate_id"], "status": g["status"],
                "accountable_role": g["accountable_role"], "required_action": g["required_action"],
                "reason": g["reason"]} for g in gates],
            "acquisition": {"complete": False, "error_type": type(error).__name__, "error": safe_detail},
            "release_authority": "RX-19", "coordinator_authority": "RX-144_COORDINATION_ONLY",
            "merge_authorization": False, "deployment_authorization": False, "release_authorization": False,
            "disposition": "BLOCK"}

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
    parser.add_argument("--prepare", action="store_true", help="Compute core evidence digest only; downstream gates remain blocked.")
    args = parser.parse_args()
    try:
        result = run_live_closure(args.repository, args.pr, trusted_keys_path=args.trusted_keys,
            receipts_path=args.receipts, required_ci_jobs=args.required_ci_job,
            token_env=args.token_env, release_branch=args.release_branch, prepare=args.prepare)
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        if args.prepare:
            required_core = {"G0_LIVE_RECONCILIATION", "G1_EXACT_HEAD_CI", "G2_ARTIFACT_INTEGRITY",
                             "G3_EFFECTIVE_PROTECTION", "G4_INDEPENDENT_REVIEW", "G5_TRUSTED_PROVENANCE"}
            gate_status = {item["gate_id"]: item["status"] for item in result.get("gate_results", [])}
            preparation_passed = (result.get("evidence_digest_claim_matches") == "PREPARATION_ONLY"
                and required_core.issubset(gate_status)
                and all(gate_status[name] == "PASS" for name in required_core)
                and result.get("acquisition", {}).get("complete") is True)
            return 0 if preparation_passed else 2
        return 0 if result["disposition"] == "RX19_APPROVED_EVIDENCE_ONLY_NO_ACTION" else 2
    except Exception as exc:
        report = _failure_report(exc, repository=args.repository, pr_number=args.pr)
        rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        sys.stderr.write(rendered)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
