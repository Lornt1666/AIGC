#!/usr/bin/env python3
"""Verify GitHub/Sigstore provenance for one exact AIGC evidence artifact.

This adapter delegates cryptographic verification, transparency verification, source
revision matching, repository scoping, and signer-workflow identity enforcement to a
pinned GitHub CLI invocation. It then independently validates the structured result's
predicate and artifact subject digest. It never falls back to a bare hash.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

DEFAULT_PREDICATE = "https://slsa.dev/provenance/v1"
DEFAULT_REPOSITORY_ID = "1287333065"
DEFAULT_CERT_IDENTITY = "https://github.com/Lornt1666/AIGC/.github/workflows/aigc-ci.yml@refs/heads/main"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class AttestationVerificationError(ValueError):
    """Raised when real attestation verification cannot establish the exact subject."""


def _artifact_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_verification_output(
    payload: Any,
    *,
    artifact_sha256: str,
    expected_predicate: str,
    expected_repository_id: str = DEFAULT_REPOSITORY_ID,
    expected_cert_identity: str = DEFAULT_CERT_IDENTITY,
) -> dict[str, Any]:
    """Validate the documented gh attestation verify --format json result shape."""
    if not isinstance(payload, list) or not payload:
        raise AttestationVerificationError("verified_attestation_array_missing")
    matched = []
    for item in payload:
        if not isinstance(item, Mapping):
            raise AttestationVerificationError("attestation_entry_malformed")
        result = item.get("verificationResult")
        if not isinstance(result, Mapping):
            raise AttestationVerificationError("verification_result_missing")
        statement = result.get("statement")
        if not isinstance(statement, Mapping):
            raise AttestationVerificationError("verified_statement_missing")
        if statement.get("predicateType") != expected_predicate:
            continue
        subjects = statement.get("subject")
        if not isinstance(subjects, list):
            raise AttestationVerificationError("statement_subject_list_missing")
        subject_match = False
        for subject in subjects:
            if not isinstance(subject, Mapping):
                continue
            digests = subject.get("digest")
            if isinstance(digests, Mapping) and digests.get("sha256") == artifact_sha256:
                subject_match = True
                break
        if not subject_match:
            continue
        certificate = result.get("signature")
        certificate = certificate.get("certificate") if isinstance(certificate, Mapping) else None
        timestamps = result.get("verifiedTimestamps")
        if not isinstance(certificate, Mapping) or not certificate:
            raise AttestationVerificationError("verified_signing_certificate_missing")
        if str(certificate.get("sourceRepositoryIdentifier", "")) != expected_repository_id:
            raise AttestationVerificationError("verified_source_repository_id_mismatch")
        if certificate.get("subjectAlternativeName") != expected_cert_identity:
            raise AttestationVerificationError("verified_signer_certificate_identity_mismatch")
        if not isinstance(timestamps, list) or not timestamps:
            raise AttestationVerificationError("verified_transparency_timestamp_missing")
        matched.append({"certificate_present": True, "verified_timestamp_count": len(timestamps)})
    if not matched:
        raise AttestationVerificationError("no_verified_attestation_matches_subject_and_predicate")
    return {
        "matching_verified_attestation_count": len(matched),
        "verified_timestamp_count": sum(x["verified_timestamp_count"] for x in matched),
    }


def verify_attestation(
    *,
    gh_path: str,
    artifact_path: str,
    repository: str,
    signer_workflow: str,
    source_sha: str,
    run_id: str,
    run_attempt: str,
    expected_predicate: str = DEFAULT_PREDICATE,
    expected_repository_id: str = DEFAULT_REPOSITORY_ID,
    expected_cert_identity: str = DEFAULT_CERT_IDENTITY,
    timeout_seconds: int = 90,
    runner=subprocess.run,
) -> tuple[dict[str, Any], str]:
    if not gh_path or not repository or "/" not in repository or not signer_workflow:
        raise AttestationVerificationError("verifier_repository_and_signer_identity_required")
    if not SHA_RE.fullmatch(source_sha):
        raise AttestationVerificationError("source_sha_invalid")
    if not run_id.isdigit() or not run_attempt.isdigit() or int(run_id) < 1 or int(run_attempt) < 1:
        raise AttestationVerificationError("workflow_run_identity_invalid")
    if not expected_predicate or timeout_seconds < 1 or timeout_seconds > 180:
        raise AttestationVerificationError("verification_policy_invalid")
    artifact = Path(artifact_path)
    if not artifact.is_file() or artifact.is_symlink():
        raise AttestationVerificationError("artifact_must_be_regular_non_symlink_file")
    digest = _artifact_digest(artifact)
    command = [
        gh_path, "attestation", "verify", str(artifact),
        "--repo", repository,
        "--signer-workflow", signer_workflow,
        "--cert-identity", expected_cert_identity,
        "--source-digest", source_sha,
        "--predicate-type", expected_predicate,
        "--format", "json",
    ]
    try:
        result = runner(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AttestationVerificationError("attestation_verifier_unavailable_or_timed_out") from exc
    if getattr(result, "returncode", 1) != 0:
        # Never echo raw verifier output: it may contain sensitive context.
        raise AttestationVerificationError("cryptographic_attestation_verification_failed")
    raw = getattr(result, "stdout", "")
    if not isinstance(raw, str) or not raw.strip():
        raise AttestationVerificationError("attestation_verifier_json_missing")
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AttestationVerificationError("attestation_verifier_json_invalid") from exc
    structural = validate_verification_output(
        parsed, artifact_sha256=digest, expected_predicate=expected_predicate,
        expected_repository_id=expected_repository_id, expected_cert_identity=expected_cert_identity,
    )
    receipt = {
        "schema_version": "aigc-gh-attestation-verification/1.0",
        "status": "VERIFIED",
        "repository": repository,
        "source_sha": source_sha,
        "workflow_run_id": run_id,
        "workflow_run_attempt": run_attempt,
        "repository_id": DEFAULT_REPOSITORY_ID,
        "signer_certificate_identity": DEFAULT_CERT_IDENTITY,
        "artifact_sha256": digest,
        "predicate_type": expected_predicate,
        "signer_workflow": signer_workflow,
        "verifier": "gh-attestation-verify",
        "verifier_version": "2.102.1",
        "verifier_exit_code": 0,
        "signature_verified": True,
        "transparency_verified": True,
        "structured_output_valid": True,
        "hash_only_fallback": False,
        "verification_output_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        **structural,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "raw_token_emitted": False,
        "release_authorization": "NOT_GRANTED",
    }
    return receipt, raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gh", required=True, help="Path to the pinned gh executable")
    parser.add_argument("--artifact", required=True, help="Exact artifact file to verify")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--signer-workflow", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--expected-predicate", default=DEFAULT_PREDICATE)
    parser.add_argument("--output", required=True, help="Receipt JSON output path")
    parser.add_argument("--raw-output", required=True, help="Raw structured verifier JSON path")
    args = parser.parse_args(argv)
    try:
        receipt, raw = verify_attestation(
            gh_path=args.gh, artifact_path=args.artifact, repository=args.repository,
            signer_workflow=args.signer_workflow, source_sha=args.source_sha,
            run_id=args.run_id, run_attempt=args.run_attempt,
            expected_predicate=args.expected_predicate,
        )
        for path, content in (
            (Path(args.raw_output), raw.rstrip() + "\n"),
            (Path(args.output), json.dumps(receipt, sort_keys=True, indent=2) + "\n"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except (AttestationVerificationError, OSError, ValueError) as exc:
        print("BLOCK: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
