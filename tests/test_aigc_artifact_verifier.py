import hashlib
import io
import json
import unittest
import zipfile

from aigc_runtime.artifact_verifier import ArtifactVerificationError, verify_artifact_zip


class ArtifactVerifierTests(unittest.TestCase):
    def archive(self, *, candidate_sha="a"*40, run_id=1001, run_attempt=1, unsafe_path=False):
        file_path = "../evil.txt" if unsafe_path else "receipt.json"
        file_bytes = b'{"status":"success"}'
        manifest = {
            "schema_version": "aigc.artifact-manifest.v1",
            "repository": "Lornt1666/AIGC",
            "candidate_sha": candidate_sha,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "files": [{"path": file_path, "sha256": hashlib.sha256(file_bytes).hexdigest(), "size": len(file_bytes)}],
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
            z.writestr(file_path, file_bytes)
        return buffer.getvalue()

    def verify(self, data, expected=None, **kwargs):
        return verify_artifact_zip(data, expected_sha256=expected or hashlib.sha256(data).hexdigest(),
            manifest_path="manifest.json", repository="Lornt1666/AIGC", candidate_sha="a"*40,
            run_id=1001, run_attempt=1, **kwargs)

    def test_valid_archive_recomputes_zip_and_file_digests(self):
        data = self.archive()
        result = self.verify(data)
        self.assertTrue(result["bytes_verified"])
        self.assertTrue(result["manifest_verified"])
        self.assertEqual(result["files"][0]["path"], "receipt.json")

    def test_archive_digest_mismatch_blocks(self):
        with self.assertRaisesRegex(ArtifactVerificationError, "zip_sha256_mismatch"):
            self.verify(self.archive(), expected="0"*64)

    def test_unsafe_path_blocks(self):
        data = self.archive(unsafe_path=True)
        with self.assertRaises(ArtifactVerificationError):
            self.verify(data)

    def test_manifest_candidate_mismatch_blocks(self):
        data = self.archive(candidate_sha="b"*40)
        with self.assertRaisesRegex(ArtifactVerificationError, "binding_mismatch"):
            self.verify(data)


if __name__ == "__main__":
    unittest.main()
