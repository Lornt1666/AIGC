"""Tests for the evidence-driven workflow; all evidence and keys are synthetic."""
import base64
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aigc_evidence_workflow import (
    HashChainLedger, make_ed25519_verifier, run_workflow, signed_payload, verify_ledger,
)
from aigc_team_agents import POLICY_ID, canonical_json, sha256_hex


def envelope():
    return {
        "schema_version": "1.0", "policy_id": POLICY_ID,
        "repository": "Lornt1666/AIGC", "commit_sha": "a" * 40, "tree_sha": "b" * 40,
        "policy_digest": "c" * 64, "invocation_id": "synthetic-run-001",
        "producer_identity": "test-fixture", "issued_at_utc": "2026-10-21T00:00:00Z",
        "expires_at_utc": "2026-10-21T01:00:00Z", "evidence_refs": [],
    }


def synthetic_test_signer(payload):
    return {"signer_identity": "synthetic-test-signer",
            "signature_b64": base64.b64encode(hashlib.sha256(payload).digest()).decode("ascii")}


def synthetic_test_verifier(payload, auth):
    expected = base64.b64encode(hashlib.sha256(payload).digest()).decode("ascii")
    return {"verified": auth.get("signer_identity") == "synthetic-test-signer"
            and auth.get("signature_b64") == expected,
            "signer_identity": "synthetic-test-signer", "trust_root_id": "test-only"}


class EvidenceWorkflowTests(unittest.TestCase):
    def test_without_authentication_real_specialists_run_but_handoffs_block(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run_workflow(envelope(), {}, Path(temp))
            self.assertEqual(result["release_decision"], "BLOCK")
            self.assertEqual(len(result["reports"]), 3)
            self.assertFalse(result["authentication_configured"])
            stages = {s["stage_id"]: s["status"] for s in result["stages"]}
            self.assertEqual(stages["aer-review"], "BLOCK")
            self.assertEqual(stages["red-review"], "BLOCK")
            self.assertEqual(stages["blue-review"], "BLOCK")
            self.assertEqual(stages["green-remediation"], "BLOCKED_DEPENDENCY")
            self.assertTrue((Path(temp) / "aer-review.json").is_file())
            self.assertTrue((Path(temp) / "evidence.jsonl").is_file())
            self.assertTrue(verify_ledger(Path(temp) / "evidence.jsonl")["valid"])

    def test_authenticated_version_bound_specialists_enable_green_but_not_release(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run_workflow(envelope(), {}, Path(temp), synthetic_test_signer, synthetic_test_verifier)
            self.assertTrue(result["authentication_configured"])
            self.assertIn("green-remediation", result["reports"])
            self.assertEqual(result["release_decision"], "BLOCK")
            report = json.loads((Path(temp) / "aer-review.json").read_text(encoding="utf-8"))
            self.assertEqual(report["authentication"]["status"], "AUTHENTICATED")
            self.assertTrue(report["binding_valid"])
            self.assertTrue(report["trusted_for_handoff"])
            self.assertEqual(report["task"]["commit_sha"], envelope()["commit_sha"])
            self.assertTrue(verify_ledger(Path(temp) / "evidence.jsonl")["valid"])

    def test_bad_signature_blocks_handoff(self):
        def bad_verifier(_payload, _auth):
            return {"verified": False, "reason": "invalid"}
        with tempfile.TemporaryDirectory() as temp:
            result = run_workflow(envelope(), {}, Path(temp), synthetic_test_signer, bad_verifier)
            self.assertEqual(result["stages"][0]["trusted_for_handoff"], False)
            self.assertEqual(next(s for s in result["stages"] if s["stage_id"] == "green-remediation")["status"],
                             "BLOCKED_DEPENDENCY")
            self.assertEqual(result["release_decision"], "BLOCK")

    def test_missing_or_empty_ledger_is_not_valid_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "missing.jsonl"
            with self.assertRaisesRegex(ValueError, "missing or empty"):
                verify_ledger(path)
            path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing or empty"):
                verify_ledger(path)

    def test_hash_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "evidence.jsonl"
            ledger = HashChainLedger(path)
            ledger.append({"type": "fixture", "value": "original"})
            self.assertTrue(verify_ledger(path)["valid"])
            data = path.read_text(encoding="utf-8").replace("original", "tampered")
            path.write_text(data, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_ledger(path)

    def test_missing_exact_version_binding_is_rejected(self):
        bad = envelope()
        bad.pop("tree_sha")
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "tree_sha"):
                run_workflow(bad, {}, Path(temp))

    def test_ed25519_verifier_checks_real_signature(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
        except ImportError:
            self.skipTest("cryptography not installed")
        private = Ed25519PrivateKey.generate()
        public_pem = private.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
        payload = b"synthetic exact report payload"
        signature = base64.b64encode(private.sign(payload)).decode()
        verifier = make_ed25519_verifier(public_pem, "fixture-signer", "fixture-root")
        accepted = verifier(payload, {"signer_identity": "fixture-signer",
                                      "signature_b64": signature,
                                      "signed_payload_sha256": sha256_hex(payload)})
        self.assertTrue(accepted["verified"])
        self.assertFalse(verifier(payload + b"!", {"signer_identity": "fixture-signer",
            "signature_b64": signature, "signed_payload_sha256": sha256_hex(payload + b"!")})["verified"])
        self.assertFalse(verifier(payload, {"signer_identity": "untrusted-signer",
            "signature_b64": signature, "signed_payload_sha256": sha256_hex(payload)})["verified"])


if __name__ == "__main__":
    unittest.main()
