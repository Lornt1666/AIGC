import base64
import json
import hashlib
import io
import zipfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from aigc_runtime.github_evidence import GitHubEvidenceError, GitHubReadOnlyClient, _safe_repo, acquire_live_snapshot
from aigc_runtime.receipt_verifier import Ed25519ReceiptVerifier, ReceiptVerificationError, TrustedReceiptKey, canonical_bytes
from aigc_runtime.artifact_verifier import ArtifactVerificationError, verify_artifact_zip

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


class LiveAcquisitionTests(unittest.TestCase):
    def test_live_acquisition_rechecks_head_and_marks_protection_403_unverifiable(self):
        head = "a" * 40
        base = "b" * 40
        class FakeClient:
            def __init__(self, heads):
                self.heads = list(heads)
                self.pr_calls = 0
                self.urls = []
            def get(self, url):
                self.urls.append(url)
                if "/pulls/7" in url:
                    sha = self.heads[min(self.pr_calls, len(self.heads)-1)]
                    self.pr_calls += 1
                    return {"head": {"sha": sha}, "base": {"sha": base, "ref": "main"},
                            "state": "open", "draft": True, "merged": False}, {}
                if "/commits/" in url and url.endswith("/status"):
                    return {"state": "success", "statuses": []}, {}
                if "/branches/" in url and url.endswith("/protection"):
                    raise GitHubEvidenceError("github_api_unavailable:403")
                return {}, {}
            def get_collection(self, url, collection_key=None):
                self.urls.append(url)
                if "/actions/runs?" in url:
                    return [{"id": 123, "run_attempt": 1, "head_sha": head, "status": "completed",
                             "conclusion": "success", "event": "pull_request", "workflow_id": 4}]
                if "/attempts/1/jobs" in url:
                    return [{"id": 9, "name": "validate", "status": "completed", "conclusion": "success"}]
                if "/artifacts?" in url:
                    return [{"id": 456, "name": "evidence", "digest": "sha256:" + "c"*64,
                             "size_in_bytes": 12, "expired": False,
                             "workflow_run": {"id": 123, "head_sha": head}}]
                return []
        client = FakeClient([head, head])
        snapshot = acquire_live_snapshot("owner/repo", 7, client=client, required_ci_jobs=["validate"])
        self.assertEqual(snapshot["candidate_sha"], head)
        self.assertEqual(snapshot["observed_head_sha"], head)
        self.assertFalse(snapshot["head_changed_during_acquisition"])
        self.assertIn("head_sha=", next(url for url in client.urls if "/actions/runs?" in url))
        self.assertEqual(snapshot["protection_readbacks"]["main"]["status"], "UNVERIFIABLE")
        self.assertEqual(snapshot["ci_runs"][0]["artifacts"][0]["id"], 456)

    def test_live_acquisition_marks_head_change_during_collection_stale(self):
        head, changed, base = "a"*40, "c"*40, "b"*40
        class FakeClient:
            def __init__(self): self.pr_calls = 0
            def get(self, url):
                if "/pulls/7" in url:
                    sha = head if self.pr_calls == 0 else changed
                    self.pr_calls += 1
                    return {"head": {"sha": sha}, "base": {"sha": base, "ref": "main"},
                            "state": "open", "draft": True, "merged": False}, {}
                if "/branches/" in url: raise GitHubEvidenceError("github_api_unavailable:403")
                return {}, {}
            def get_collection(self, url, collection_key=None): return []
        snapshot = acquire_live_snapshot("owner/repo", 7, client=FakeClient())
        self.assertEqual(snapshot["candidate_sha"], head)
        self.assertEqual(snapshot["observed_head_sha"], changed)
        self.assertTrue(snapshot["head_changed_during_acquisition"])


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



class ArtifactVerifierTests(unittest.TestCase):
    candidate_sha = "a" * 40

    def make_archive(self, *, candidate_sha=None, unsafe_path=None):
        evidence = b"test evidence bytes"
        member_path = unsafe_path or "evidence.txt"
        manifest = {
            "schema_version": "aigc.artifact-manifest.v1",
            "repository": "Lornt1666/AIGC",
            "candidate_sha": candidate_sha or self.candidate_sha,
            "run_id": 12345,
            "run_attempt": 1,
            "files": [{
                "path": member_path,
                "sha256": hashlib.sha256(evidence).hexdigest(),
                "size": len(evidence),
            }],
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr(member_path, evidence)
        return stream.getvalue()

    def verify(self, archive_bytes, *, expected_sha=None):
        return verify_artifact_zip(
            archive_bytes,
            expected_sha256=expected_sha or hashlib.sha256(archive_bytes).hexdigest(),
            manifest_path="manifest.json",
            repository="Lornt1666/AIGC",
            candidate_sha=self.candidate_sha,
            run_id=12345,
            run_attempt=1,
        )

    def test_valid_archive_recomputes_zip_and_member_digests(self):
        archive_bytes = self.make_archive()
        result = self.verify(archive_bytes)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertTrue(result["bytes_verified"])
        self.assertEqual(result["files"][0]["sha256"], "sha256:" + hashlib.sha256(b"test evidence bytes").hexdigest())

    def test_archive_digest_mismatch_is_rejected(self):
        archive_bytes = self.make_archive()
        with self.assertRaisesRegex(ArtifactVerificationError, "artifact_zip_sha256_mismatch"):
            self.verify(archive_bytes, expected_sha="0" * 64)

    def test_candidate_sha_mismatch_is_rejected(self):
        archive_bytes = self.make_archive(candidate_sha="b" * 40)
        with self.assertRaisesRegex(ArtifactVerificationError, "artifact_manifest_binding_mismatch:candidate_sha"):
            self.verify(archive_bytes)

    def test_path_traversal_member_is_rejected(self):
        archive_bytes = self.make_archive(unsafe_path="../escape.txt")
        with self.assertRaisesRegex(ArtifactVerificationError, "unsafe_or_duplicate_archive_path"):
            self.verify(archive_bytes)


if __name__ == "__main__":
    unittest.main()
