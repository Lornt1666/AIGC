import base64
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from aigc_runtime.github_evidence import GitHubEvidenceError, GitHubReadOnlyClient, _safe_repo
from aigc_runtime.receipt_verifier import Ed25519ReceiptVerifier, ReceiptVerificationError, TrustedReceiptKey, canonical_bytes

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    Ed25519PrivateKey = None


class GitHubEvidenceTests(unittest.TestCase):
    def test_token_required(self):
        with self.assertRaisesRegex(GitHubEvidenceError, "github_token_required"):
            GitHubReadOnlyClient("")

    def test_repo_validation(self):
        self.assertEqual(_safe_repo("Lornt1666/AIGC"), "Lornt1666/AIGC")
        for value in ("../x", "owner/repo/extra", "owner/.."):
            with self.subTest(value=value), self.assertRaises(GitHubEvidenceError):
                _safe_repo(value)

    def test_url_allowlist(self):
        client = GitHubReadOnlyClient("token")
        with self.assertRaisesRegex(GitHubEvidenceError, "url_not_allowlisted"):
            client.get("https://example.com/steal")

    def test_pagination_loop_fails_closed(self):
        class Resp:
            status = 200
            headers = {"Link": '<https://api.github.com/repos/o/r?page=1>; rel="next"'}
            def read(self): return b"[]"
            def __enter__(self): return self
            def __exit__(self, *args): pass
        client = GitHubReadOnlyClient("token", max_pages=1, opener=lambda *a, **k: Resp())
        with self.assertRaisesRegex(GitHubEvidenceError, "pagination_limit_exceeded"):
            client.get_all("https://api.github.com/repos/o/r?page=1")


@unittest.skipIf(Ed25519PrivateKey is None, "cryptography is not installed")
class ReceiptVerifierTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        self.verifier = Ed25519ReceiptVerifier([TrustedReceiptKey(
            key_id="test-key", public_key_b64=base64.b64encode(public).decode(),
            issuer="test-issuer", allowed_purposes=("human-acceptance",))])
        now = datetime.now(timezone.utc)
        self.payload = {"issuer":"test-issuer","purpose":"human-acceptance","receipt_id":"R-1",
            "issued_at":(now-timedelta(seconds=5)).isoformat().replace("+00:00","Z"),
            "expires_at":(now+timedelta(minutes=5)).isoformat().replace("+00:00","Z"),
            "candidate_sha":"a"*40,"evidence_digest":"sha256:"+"b"*64}
    def envelope(self, payload=None):
        body = self.payload if payload is None else payload
        return {"key_id":"test-key","payload":body,
            "signature":base64.b64encode(self.private.sign(canonical_bytes(body))).decode()}
    def test_valid_signature_and_bindings(self):
        result=self.verifier.verify(self.envelope(), expected_purpose="human-acceptance",
            expected_bindings={"candidate_sha":"a"*40,"evidence_digest":"sha256:"+"b"*64})
        self.assertTrue(result["verified"])
    def test_tampered_payload_rejected(self):
        envelope=self.envelope()
        envelope["payload"]={**envelope["payload"],"candidate_sha":"c"*40}
        with self.assertRaises(ReceiptVerificationError):
            self.verifier.verify(envelope, expected_purpose="human-acceptance", expected_bindings={"candidate_sha":"a"*40})
    def test_unknown_purpose_rejected(self):
        with self.assertRaisesRegex(ReceiptVerificationError,"purpose"):
            self.verifier.verify(self.envelope(), expected_purpose="release", expected_bindings={})
    def test_wrong_binding_rejected(self):
        with self.assertRaisesRegex(ReceiptVerificationError,"binding_mismatch"):
            self.verifier.verify(self.envelope(), expected_purpose="human-acceptance", expected_bindings={"candidate_sha":"c"*40})
    def test_same_receipt_cannot_be_replayed_in_one_process(self):
        envelope = self.envelope()
        self.verifier.verify(envelope, expected_purpose="human-acceptance", expected_bindings={"candidate_sha":"a"*40})
        with self.assertRaisesRegex(ReceiptVerificationError, "replayed"):
            self.verifier.verify(envelope, expected_purpose="human-acceptance", expected_bindings={"candidate_sha":"a"*40})
    def test_revoked_receipt_rejected(self):
        verifier=Ed25519ReceiptVerifier(list(self.verifier.keys.values()), revoked_receipt_ids={"R-1"})
        with self.assertRaisesRegex(ReceiptVerificationError,"revoked"):
            verifier.verify(self.envelope(), expected_purpose="human-acceptance", expected_bindings={})


if __name__ == "__main__":
    unittest.main()
