from __future__ import annotations

import hashlib
import json
import subprocess
from unittest.mock import patch

import pytest

from src.gh_sigstore_provenance_adapter import (
    ProvenanceVerificationError,
    verify_artifact,
)

ARTIFACT = b"canonical-evidence-bundle"
DIGEST = hashlib.sha256(ARTIFACT).hexdigest()
SOURCE = "a" * 40
WORKFLOW = "Lornt1666/AIGC/.github/workflows/aigc-ci.yml"
IDENTITY = "https://github.com/Lornt1666/AIGC/.github/workflows/aigc-ci.yml@refs/heads/main"


def result(stdout: str, returncode: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def verified_output(identity: str = IDENTITY, digest: str = DIGEST) -> str:
    return json.dumps([{
        "verificationResult": {
            "signature": {"certificate": {"subjectAlternativeName": identity}},
            "statement": {
                "predicateType": "https://slsa.dev/provenance/v1",
                "subject": [{"name": "evidence.tar.gz", "digest": {"sha256": digest}}],
                "predicate": {"buildDefinition": {"externalParameters": {"source": SOURCE}}},
            },
        },
    }])


def invoke(path, output=None):
    version = result("gh version 2.102.0 (2026-10-01)\n")
    verified = result(output if output is not None else verified_output())
    with patch("src.gh_sigstore_provenance_adapter.subprocess.run", side_effect=[version, verified]):
        return verify_artifact(
            path,
            expected_sha256=DIGEST,
            expected_signer_workflow=WORKFLOW,
            expected_certificate_identity=IDENTITY,
            expected_source_sha=SOURCE,
        )


def test_verifies_exact_artifact_and_identity(tmp_path):
    path = tmp_path / "evidence.tar.gz"
    path.write_bytes(ARTIFACT)
    receipt = invoke(path)
    assert receipt["verified"] is True
    assert receipt["artifact_sha256"] == DIGEST


def test_wrong_artifact_digest_blocks_before_cli(tmp_path):
    path = tmp_path / "evidence.tar.gz"
    path.write_bytes(b"tampered")
    with pytest.raises(ProvenanceVerificationError, match="digest"):
        invoke(path)


def test_wrong_certificate_identity_blocks(tmp_path):
    path = tmp_path / "evidence.tar.gz"
    path.write_bytes(ARTIFACT)
    with pytest.raises(ProvenanceVerificationError, match="exact signer identity"):
        invoke(path, verified_output(identity=IDENTITY + "-attacker"))


def test_wrong_attested_subject_digest_blocks(tmp_path):
    path = tmp_path / "evidence.tar.gz"
    path.write_bytes(ARTIFACT)
    with pytest.raises(ProvenanceVerificationError, match="exact signer identity"):
        invoke(path, verified_output(digest="f" * 64))


def test_cli_failure_blocks(tmp_path):
    path = tmp_path / "evidence.tar.gz"
    path.write_bytes(ARTIFACT)
    with patch(
        "src.gh_sigstore_provenance_adapter.subprocess.run",
        side_effect=[result("gh version 2.102.0"), result("", returncode=1)],
    ):
        with pytest.raises(ProvenanceVerificationError, match="verification failed"):
            verify_artifact(
                path, expected_sha256=DIGEST, expected_signer_workflow=WORKFLOW,
                expected_certificate_identity=IDENTITY, expected_source_sha=SOURCE,
            )
