import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from scripts.verify_aigc_gh_attestation import (
    AttestationVerificationError,
    validate_verification_output,
    verify_attestation,
)


SHA = "a" * 40
PREDICATE = "https://slsa.dev/provenance/v1"


def verified_payload(digest):
    return [{
        "attestation": {"bundle": {"mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json"}},
        "verificationResult": {
            "signature": {"certificate": {"subjectAlternativeName": "https://github.com/Lornt1666/AIGC/.github/workflows/aigc-ci.yml@refs/heads/main", "sourceRepositoryIdentifier": "1287333065"}},
            "verifiedTimestamps": [{"timestamp": "2026-10-21T00:00:00Z"}],
            "statement": {
                "_type": "https://in-toto.io/Statement/v1",
                "predicateType": PREDICATE,
                "subject": [{"name": "evidence.zip", "digest": {"sha256": digest}}],
                "predicate": {"buildDefinition": {}},
            },
        },
    }]


class GitHubAttestationAdapterTests(unittest.TestCase):
    def test_requires_exact_subject_digest_and_predicate(self):
        digest = "b" * 64
        result = validate_verification_output(
            verified_payload(digest), artifact_sha256=digest, expected_predicate=PREDICATE
        )
        self.assertEqual(result["matching_verified_attestation_count"], 1)
        with self.assertRaises(AttestationVerificationError):
            validate_verification_output(
                verified_payload("c" * 64), artifact_sha256=digest, expected_predicate=PREDICATE
            )
        with self.assertRaises(AttestationVerificationError):
            validate_verification_output(
                verified_payload(digest), artifact_sha256=digest, expected_predicate="unexpected"
            )

    def test_real_cli_contract_emits_receipt_bound_to_exact_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "evidence.zip"
            artifact.write_bytes(b"exact evidence bytes")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            calls = []

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                return SimpleNamespace(returncode=0, stdout=json.dumps(verified_payload(digest)), stderr="")

            receipt, raw = verify_attestation(
                gh_path="/opt/gh/bin/gh", artifact_path=str(artifact),
                repository="Lornt1666/AIGC",
                signer_workflow="Lornt1666/AIGC/.github/workflows/aigc-ci.yml",
                source_sha=SHA, runner=runner,
            )
            self.assertEqual(receipt["status"], "VERIFIED")
            self.assertEqual(receipt["artifact_sha256"], digest)
            self.assertEqual(receipt["source_sha"], SHA)
            self.assertIs(receipt["signature_verified"], True)
            self.assertIs(receipt["transparency_verified"], True)
            self.assertIs(receipt["hash_only_fallback"], False)
            command, kwargs = calls[0]
            self.assertEqual(command[0:3], ["/opt/gh/bin/gh", "attestation", "verify"])
            self.assertIn("--signer-workflow", command)
            self.assertIn("--source-digest", command)
            self.assertIn("--predicate-type", command)
            self.assertIs(kwargs["check"], False)
            self.assertEqual(raw, json.dumps(verified_payload(digest)))

    def test_nonzero_cli_exit_fails_closed_without_output_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "evidence.zip"
            artifact.write_bytes(b"exact evidence bytes")

            def runner(command, **kwargs):
                return SimpleNamespace(returncode=1, stdout="hash matches", stderr="verification failed")

            with self.assertRaisesRegex(AttestationVerificationError, "cryptographic_attestation_verification_failed"):
                verify_attestation(
                    gh_path="gh", artifact_path=str(artifact), repository="Lornt1666/AIGC",
                    signer_workflow="Lornt1666/AIGC/.github/workflows/aigc-ci.yml",
                    source_sha=SHA, runner=runner,
                )

    def test_wrong_certificate_repository_id_or_signer_identity_blocks(self):
        digest = "b" * 64
        payload = verified_payload(digest)
        cert = payload[0]["verificationResult"]["signature"]["certificate"]
        cert["sourceRepositoryIdentifier"] = "999999"
        with self.assertRaisesRegex(AttestationVerificationError, "verified_source_repository_id_mismatch"):
            validate_verification_output(payload, artifact_sha256=digest, expected_predicate=PREDICATE)
        payload = verified_payload(digest)
        payload[0]["verificationResult"]["signature"]["certificate"]["subjectAlternativeName"] = "https://attacker.invalid/workflow"
        with self.assertRaisesRegex(AttestationVerificationError, "verified_signer_certificate_identity_mismatch"):
            validate_verification_output(payload, artifact_sha256=digest, expected_predicate=PREDICATE)

    def test_missing_certificate_or_transparency_evidence_blocks(self):
        digest = "b" * 64
        payload = verified_payload(digest)
        payload[0]["verificationResult"]["verifiedTimestamps"] = []
        with self.assertRaisesRegex(AttestationVerificationError, "verified_transparency_timestamp_missing"):
            validate_verification_output(payload, artifact_sha256=digest, expected_predicate=PREDICATE)

    def test_invalid_source_sha_blocks_before_invoking_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "evidence.zip"
            artifact.write_bytes(b"x")
            with self.assertRaisesRegex(AttestationVerificationError, "source_sha_invalid"):
                verify_attestation(
                    gh_path="gh", artifact_path=str(artifact), repository="Lornt1666/AIGC",
                    signer_workflow="workflow", source_sha="not-a-sha",
                    runner=lambda *a, **k: self.fail("runner must not execute"),
                )


if __name__ == "__main__":
    unittest.main()
