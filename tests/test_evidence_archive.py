"""Tests for independently retained evidence archive semantics using a fake S3 client."""
import hashlib
import io
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aigc_evidence_archive import archive_and_verify


class FakeS3:
    def __init__(self, version_id="version-123", lock_mode="COMPLIANCE", corrupt=False):
        self.version_id = version_id
        self.lock_mode = lock_mode
        self.corrupt = corrupt
        self.obj = None
        self.args = None

    def put_object(self, **kwargs):
        self.args = kwargs
        self.obj = kwargs
        return {"VersionId": self.version_id}

    def head_object(self, **kwargs):
        obj = self.obj
        body = b"tampered" if self.corrupt else obj["Body"]
        return {
            "VersionId": self.version_id,
            "ObjectLockMode": self.lock_mode,
            "ObjectLockRetainUntilDate": obj["ObjectLockRetainUntilDate"],
            "ContentLength": len(body),
            "Metadata": obj["Metadata"],
        }

    def get_object(self, **kwargs):
        body = b"tampered" if self.corrupt else self.obj["Body"]
        return {"Body": io.BytesIO(body)}


def bindings():
    return {
        "repository": "Lornt1666/AIGC", "commit_sha": "a" * 40,
        "tree_sha": "b" * 40, "policy_digest": "c" * 64,
        "invocation_id": "archive-test-001",
    }


class EvidenceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.retain_until = datetime.now(timezone.utc) + timedelta(days=365)
        self.bundle = b"canonical receipt bundle"

    def test_uploads_compliance_retention_and_verifies_versioned_readback(self):
        client = FakeS3()
        result = archive_and_verify(client, "aigc-evidence-lock", "receipts/run-001.zip",
                                    self.bundle, bindings(), self.retain_until)
        self.assertEqual(result["status"], "ARCHIVED_AND_VERIFIED")
        self.assertEqual(result["object_lock_mode"], "COMPLIANCE")
        self.assertTrue(result["remote_readback_verified"])
        self.assertEqual(result["sha256"], hashlib.sha256(self.bundle).hexdigest())
        self.assertEqual(client.args["ObjectLockMode"], "COMPLIANCE")
        self.assertEqual(client.args["Metadata"]["commit_sha"], bindings()["commit_sha"])

    def test_missing_version_id_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "version ID"):
            archive_and_verify(FakeS3(version_id="null"), "bucket", "key",
                               self.bundle, bindings(), self.retain_until)

    def test_governance_mode_is_not_accepted(self):
        with self.assertRaisesRegex(RuntimeError, "COMPLIANCE"):
            archive_and_verify(FakeS3(lock_mode="GOVERNANCE"), "bucket", "key",
                               self.bundle, bindings(), self.retain_until)

    def test_tampered_remote_readback_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "content length mismatch|content digest mismatch"):
            archive_and_verify(FakeS3(corrupt=True), "bucket", "key",
                               self.bundle, bindings(), self.retain_until)

    def test_missing_or_invalid_version_binding_rejected(self):
        env = bindings()
        del env["tree_sha"]
        with self.assertRaisesRegex(ValueError, "missing exact-version bindings"):
            archive_and_verify(FakeS3(), "bucket", "key", self.bundle, env, self.retain_until)

    def test_naive_or_expired_retention_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            archive_and_verify(FakeS3(), "bucket", "key", self.bundle, bindings(),
                               datetime.now() + timedelta(days=1))
        with self.assertRaisesRegex(ValueError, "future"):
            archive_and_verify(FakeS3(), "bucket", "key", self.bundle, bindings(),
                               datetime.now(timezone.utc) - timedelta(days=1))


if __name__ == "__main__":
    unittest.main()
