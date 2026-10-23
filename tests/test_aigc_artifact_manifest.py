import json
import tempfile
import unittest
from pathlib import Path

from scripts.create_aigc_artifact_manifest import create_manifest


class ArtifactManifestTests(unittest.TestCase):
    def test_manifest_is_deterministic_and_binds_exact_run(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "evidence.json").write_text('{"ok":true}', encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "log.txt").write_text("test", encoding="utf-8")
            first = create_manifest(root, repository="Lornt1666/AIGC", candidate_sha="a"*40, run_id=123, run_attempt=2)
            second = create_manifest(root, repository="Lornt1666/AIGC", candidate_sha="a"*40, run_id=123, run_attempt=2)
            self.assertEqual(first, second)
            self.assertEqual(first["run_attempt"], 2)
            self.assertEqual([x["path"] for x in first["files"]], ["evidence.json", "nested/log.txt"])

    def test_manifest_rejects_invalid_candidate_sha(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "x.txt").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "candidate_sha_invalid"):
                create_manifest(root, repository="Lornt1666/AIGC", candidate_sha="bad", run_id=1, run_attempt=1)

    def test_manifest_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            outside = root.parent / ("aigc-outside-" + root.name + ".txt")
            outside.write_text("x", encoding="utf-8")
            try:
                (root / "link.txt").symlink_to(outside)
                with self.assertRaisesRegex(ValueError, "symlink_in_artifact_root"):
                    create_manifest(root, repository="Lornt1666/AIGC", candidate_sha="a"*40, run_id=1, run_attempt=1)
            finally:
                outside.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
