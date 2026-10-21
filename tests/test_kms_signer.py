"""Cryptographic tests for the AWS KMS adapter; test private keys are ephemeral."""
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from aigc_kms_signer import METHOD, build_aws_kms_adapters
from aigc_evidence_workflow import authenticate_report, signed_payload


class FakeKMS:
    def __init__(self, private_key):
        self.private_key = private_key
        self.calls = []

    def sign(self, **kwargs):
        self.calls.append(kwargs)
        signature = self.private_key.sign(
            kwargs["Message"],
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            Prehashed(hashes.SHA256()),
        )
        return {"Signature": signature}


class KmsSignerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_pem = cls.private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    def setUp(self):
        self.client = FakeKMS(self.private_key)
        self.signer, self.verifier = build_aws_kms_adapters(
            "arn:aws:kms:us-east-1:111122223333:key/test-key",
            "aigc-ci-test-signer", "test-trust-root", self.public_pem,
            "us-east-1", kms_client=self.client,
        )

    def test_signer_uses_kms_digest_api_and_verifies_signature(self):
        payload = b"version-bound report" * 1000
        metadata = self.signer(payload)
        self.assertEqual(metadata["method"], METHOD)
        self.assertEqual(metadata["signer_identity"], "aigc-ci-test-signer")
        self.assertEqual(self.client.calls[0]["MessageType"], "DIGEST")
        self.assertEqual(self.client.calls[0]["SigningAlgorithm"], METHOD)
        self.assertEqual(self.client.calls[0]["Message"], hashlib.sha256(payload).digest())
        auth = {**metadata, "signed_payload_sha256": hashlib.sha256(payload).hexdigest()}
        self.assertTrue(self.verifier(payload, auth)["verified"])

    def test_tampered_payload_and_wrong_identity_are_rejected(self):
        payload = b"source evidence"
        metadata = self.signer(payload)
        auth = {**metadata, "signed_payload_sha256": hashlib.sha256(payload).hexdigest()}
        self.assertFalse(self.verifier(payload + b"tampered", auth)["verified"])
        wrong_identity = {**auth, "signer_identity": "untrusted"}
        self.assertEqual(self.verifier(payload, wrong_identity)["reason"], "signer_identity_mismatch")

    def test_authenticate_report_marks_real_rsa_signature_authenticated(self):
        report = {
            "agent_id": "aer", "repository": "Lornt1666/AIGC",
            "commit_sha": "a" * 40, "tree_sha": "b" * 40,
            "policy_digest": "c" * 64, "policy_id": "aigc-team-assurance-v1",
            "invocation_id": "kms-adapter-test",
        }
        signed = authenticate_report(report, self.signer, self.verifier)
        self.assertEqual(signed["authentication"]["status"], "AUTHENTICATED")
        self.assertEqual(signed["authentication"]["method"], METHOD)
        self.assertEqual(signed["authentication"]["verification"]["trust_root_id"], "test-trust-root")

    def test_wrong_key_rejected(self):
        payload = b"source evidence"
        metadata = self.signer(payload)
        auth = {**metadata, "signed_payload_sha256": hashlib.sha256(payload).hexdigest()}
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pem = other_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("ascii")
        _, wrong_verifier = build_aws_kms_adapters(
            "arn:aws:kms:us-east-1:111122223333:key/test-key",
            "aigc-ci-test-signer", "test-trust-root", other_pem,
            "us-east-1", kms_client=self.client,
        )
        self.assertEqual(wrong_verifier(payload, auth)["reason"], "signature_invalid")


if __name__ == "__main__":
    unittest.main()
