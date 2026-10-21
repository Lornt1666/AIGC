"""MVP++ Documentation Architect tests; deterministic, offline, and side-effect-bounded."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aigc_documentation_architect import (
    POLICY_ID, generate_document_pack, select_documents, sha256,
)

class DocumentationArchitectTests(unittest.TestCase):
    def test_core_pack_generated_with_draft_status_and_hashes(self):
        brief = {"project_name": "Test Project", "purpose": "Governed agent orchestration",
                 "requirements": ["version-bound tasks"], "risk_level": "high"}
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "docs"
            manifest = generate_document_pack(brief, out)
            self.assertEqual(manifest["status"], "GENERATED_DRAFT")
            self.assertEqual(manifest["authority"]["release_decision"], "BLOCK")
            self.assertFalse(manifest["authority"]["approvals_inferred"])
            self.assertGreaterEqual(manifest["document_count"], 10)
            for item in manifest["documents"]:
                p = out / item["path"]
                self.assertTrue(p.is_file(), item["path"])
                self.assertEqual(sha256(p.read_text(encoding="utf-8")), item["sha256"])
                if item["path"] != "README.md":
                    self.assertIn("GENERATED DRAFT — NOT APPROVED", p.read_text(encoding="utf-8"))

    def test_optional_documents_selected_from_brief_signals(self):
        docs = {item[2] for item in select_documents({
            "project_name": "Agent API", "purpose": "AI agent with REST API and database",
            "constraints": ["Cloud deployment"], "risk_level": "high",
        })}
        self.assertTrue({"api", "ai", "data", "infra", "security", "compliance"}.issubset(docs))

    def test_source_digest_changes_when_input_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            first = generate_document_pack({"project_name": "A", "purpose": "one"}, Path(temp) / "a")
            second = generate_document_pack({"project_name": "A", "purpose": "two"}, Path(temp) / "b")
            self.assertNotEqual(first["source_digest_sha256"], second["source_digest_sha256"])

    def test_empty_or_non_object_brief_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "non-empty JSON object"):
                generate_document_pack({}, Path(temp) / "empty")
            with self.assertRaisesRegex(ValueError, "non-empty JSON object"):
                generate_document_pack(["not", "an", "object"], Path(temp) / "list")

    def test_evidence_inventory_is_in_source_digest_but_not_accepted_as_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            brief = {"project_name": "Evidence Demo", "purpose": "Evidence governance"}
            a = generate_document_pack(brief, Path(temp) / "a", {"receipt": "claim-A"})
            b = generate_document_pack(brief, Path(temp) / "b", {"receipt": "claim-B"})
            self.assertNotEqual(a["source_digest_sha256"], b["source_digest_sha256"])
            self.assertEqual(a["authority"]["release_decision"], "BLOCK")

    def test_cli_creates_index_manifest_and_documents(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "brief.json"
            output = root / "out"
            source.write_text(json.dumps({"project_name": "CLI Project", "purpose": "Test CLI",
                                          "requirements": ["must run"]}), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ROOT / "src" / "aigc_documentation_architect.py"),
                                   "--input", str(source), "--output-dir", str(output)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((output / "README.md").is_file())
            self.assertTrue((output / "documentation_manifest.json").is_file())
            manifest = json.loads((output / "documentation_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["policy_id"], POLICY_ID)
            self.assertEqual(manifest["authority"]["release_decision"], "BLOCK")

if __name__ == "__main__":
    unittest.main()
