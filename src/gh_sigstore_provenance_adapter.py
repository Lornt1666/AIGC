"""Fail-closed GitHub/Sigstore provenance adapter for AIGC release evidence.

This adapter verifies one local artifact with the GitHub CLI, then independently
checks the returned verified statement's subject digest and signer certificate
identity. It does not approve releases or execute deployment actions.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

REPOSITORY = "Lornt1666/AIGC"
MIN_GH_VERSION = (2, 102, 0)
SLSA_PROVENANCE_V1 = "https://slsa.dev/provenance/v1"
_VERSION = re.compile(r"gh version (\d+)\.(\d+)\.(\d+)")


class ProvenanceVerificationError(RuntimeError):
    """Raised whenever provenance cannot be verified to the exact expected subject."""


def _run(argv: list[str]) -> str:
    try:
        result = subprocess.run(argv, check=False, capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProvenanceVerificationError("GitHub CLI could not be executed reliably") from exc
    if result.returncode != 0:
        raise ProvenanceVerificationError("GitHub attestation verification failed")
    return result.stdout


def _version() -> tuple[int, int, int]:
    output = _run(["gh", "version"])
    match = _VERSION.search(output)
    if not match:
        raise ProvenanceVerificationError("GitHub CLI version is unrecognized")
    version = tuple(int(part) for part in match.groups())
    if version < MIN_GH_VERSION:
        raise ProvenanceVerificationError("GitHub CLI version is below the required patched minimum")
    return version


def _contains_exact(value: Any, expected: str) -> bool:
    """Search parsed certificate fields for an exact identity; never prefix-match."""
    if isinstance(value, str):
        return value == expected
    if isinstance(value, list):
        return any(_contains_exact(item, expected) for item in value)
    if isinstance(value, dict):
        return any(_contains_exact(item, expected) for item in value.values())
    return False


def verify_artifact(
    artifact_path: str | Path,
    *,
    expected_sha256: str,
    expected_signer_workflow: str,
    expected_certificate_identity: str,
    expected_source_sha: str,
    predicate_type: str = SLSA_PROVENANCE_V1,
) -> dict[str, Any]:
    """Verify cryptographic provenance and bind it to exact source and artifact.

    A successful return is verification evidence only; release policy is evaluated
    separately by ReleaseAssuranceAgent. Any missing or ambiguous field raises BLOCK.
    """
    path = Path(artifact_path)
    if not path.is_file():
        raise ProvenanceVerificationError("artifact file is missing")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ProvenanceVerificationError("expected artifact SHA-256 is malformed")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_source_sha):
        raise ProvenanceVerificationError("expected source commit SHA is malformed")
    if not expected_signer_workflow or not expected_signer_workflow.startswith(REPOSITORY + "/"):
        raise ProvenanceVerificationError("expected signer workflow must be an exact AIGC repository workflow path")
    if not expected_certificate_identity.startswith("https://github.com/Lornt1666/AIGC/"):
        raise ProvenanceVerificationError("expected certificate identity must be a full exact GitHub OIDC SAN")

    _version()
    actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_sha != expected_sha256:
        raise ProvenanceVerificationError("local artifact digest does not match expected SHA-256")

    output = _run([
        "gh", "attestation", "verify", str(path),
        "--repo", REPOSITORY,
        "--signer-workflow", expected_signer_workflow,
        "--cert-identity", expected_certificate_identity,
        "--source-digest", expected_source_sha,
        "--predicate-type", predicate_type,
        "--format", "json",
    ])
    try:
        entries = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ProvenanceVerificationError("GitHub CLI returned malformed verification JSON") from exc
    if not isinstance(entries, list) or not entries:
        raise ProvenanceVerificationError("no cryptographically verified attestations were returned")

    accepted = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        verification = entry.get("verificationResult")
        if not isinstance(verification, dict):
            continue
        statement = verification.get("statement")
        signature = verification.get("signature")
        if not isinstance(statement, dict) or not isinstance(signature, dict):
            continue
        if statement.get("predicateType") != predicate_type:
            continue
        certificate = signature.get("certificate")
        if not isinstance(certificate, dict):
            continue
        # CLI enforces repository/workflow/signature; this exact identity check guards
        # against accidental broadening and does not accept a matching prefix.
        if not _contains_exact(certificate, expected_certificate_identity):
            continue
        subjects = statement.get("subject")
        if not isinstance(subjects, list):
            continue
        matching_subject = any(
            isinstance(subject, dict)
            and isinstance(subject.get("digest"), dict)
            and subject["digest"].get("sha256") == expected_sha256
            for subject in subjects
        )
        if not matching_subject:
            continue
        accepted.append(entry)

    if not accepted:
        raise ProvenanceVerificationError(
            "verified attestation did not bind exact signer identity, predicate type, and artifact digest"
        )
    return {
        "verified": True,
        "repository": REPOSITORY,
        "signer_workflow": expected_signer_workflow,
        "certificate_identity": expected_certificate_identity,
        "source_sha": expected_source_sha,
        "artifact_sha256": expected_sha256,
        "predicate_type": predicate_type,
        "gh_version_minimum": ".".join(str(part) for part in MIN_GH_VERSION),
        "verified_attestation_count": len(accepted),
    }



def make_release_provenance_verifier(
    *,
    receipt_bundle_path: str | Path,
    release_artifact_path: str | Path,
    receipt_signer_workflow: str,
    receipt_certificate_identity: str,
    artifact_signer_workflow: str,
    artifact_certificate_identity: str,
):
    """Create the callback contract expected by ReleaseAssuranceAgent.

    Paths and signer identities must come from trusted deployment configuration, not
    from the packet or an LLM. The receipt bundle file must contain exactly the
    canonical JSON bytes of canonical_ci.stage_receipts. Both artifacts are verified
    independently; any error returns False so the decision agent blocks.
    """
    def verify(canonical_ci: dict, subject: dict) -> bool:
        try:
            source_sha = subject["commit_sha"]
            stage_receipts = canonical_ci["stage_receipts"]
            expected_bundle_sha = hashlib.sha256(
                json.dumps(stage_receipts, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            if canonical_ci.get("stage_receipts_sha256") != expected_bundle_sha:
                return False
            if canonical_ci.get("attested_receipt_bundle_sha256") != expected_bundle_sha:
                return False
            verify_artifact(
                receipt_bundle_path,
                expected_sha256=expected_bundle_sha,
                expected_signer_workflow=receipt_signer_workflow,
                expected_certificate_identity=receipt_certificate_identity,
                expected_source_sha=source_sha,
            )
            verify_artifact(
                release_artifact_path,
                expected_sha256=subject["artifact_sha256"],
                expected_signer_workflow=artifact_signer_workflow,
                expected_certificate_identity=artifact_certificate_identity,
                expected_source_sha=source_sha,
            )
            return True
        except (KeyError, TypeError, ValueError, ProvenanceVerificationError, OSError):
            return False
    return verify
