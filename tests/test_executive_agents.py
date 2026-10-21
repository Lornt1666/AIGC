"""Fail-closed tests for AIGC executive role contracts and CEO approval policy."""
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aigc_executive_agents import ROLES, evaluate_ceo_approval, roster

def valid_proposal():
    return {
        "schema_version": "1.0", "decision_id": "d-1", "task_id": "t-1",
        "task_digest_sha256": "a" * 64, "source_revision": "b" * 40,
        "action_class": "write", "allowed_action_ids": ["docs.generate"],
        "denied_action_ids": ["repo.merge"], "max_usd": 0,
        "expires_at_utc": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        "required_check_ids": ["schema"], "evidence_digests": ["c" * 64],
        "risk_decision": "PASS", "human_approval_ref": None,
        "decision": "APPROVE_SCOPED", "rationale": "Exact scoped documentation action",
        "signer_identity": "ceo-agent-test-identity", "signature_ref": "test-signature-ref",
    }

class ExecutiveAgentsTests(unittest.TestCase):
    def test_roster_has_unique_ids_and_expected_roles(self):
        ids = [r.agent_id for r in ROLES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 20)
        self.assertTrue({"CEO", "COS", "CRO", "CISO", "TRUST", "RED", "BLUE", "GREEN",
                         "AER", "DOC", "QA", "AUDIT", "DISPATCH", "RELEASE"}.issubset(set(ids)))
        self.assertTrue(all(x["status"] == "SPECIFIED_NOT_OPERATIONAL" for x in roster()))

    def test_well_formed_scoped_proposal_is_advisory_only(self):
        result = evaluate_ceo_approval(valid_proposal())
        self.assertEqual(result["decision"], "APPROVE_SCOPED")
        self.assertEqual(result["authority"], "advisory_only")
        self.assertTrue(result["requires_execution_controller_revalidation"])

    def test_missing_field_fails_closed(self):
        proposal = valid_proposal()
        del proposal["source_revision"]
        self.assertEqual(evaluate_ceo_approval(proposal)["decision"], "BLOCK")

    def test_unknown_field_fails_closed(self):
        proposal = valid_proposal()
        proposal["bypass_release_gate"] = True
        self.assertEqual(evaluate_ceo_approval(proposal)["decision"], "BLOCK")

    def test_wildcard_action_fails_closed(self):
        proposal = valid_proposal()
        proposal["allowed_action_ids"] = ["*"]
        self.assertEqual(evaluate_ceo_approval(proposal)["decision"], "BLOCK")

    def test_invalid_revision_and_digest_fail_closed(self):
        proposal = valid_proposal()
        proposal["source_revision"] = "main"
        proposal["task_digest_sha256"] = "not-a-digest"
        self.assertEqual(evaluate_ceo_approval(proposal)["decision"], "BLOCK")

    def test_expired_approval_fails_closed(self):
        proposal = valid_proposal()
        proposal["expires_at_utc"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.assertEqual(evaluate_ceo_approval(proposal)["decision"], "BLOCK")

    def test_high_consequence_action_requires_human_approval(self):
        proposal = valid_proposal()
        proposal["action_class"] = "release"
        proposal["human_approval_ref"] = None
        self.assertEqual(evaluate_ceo_approval(proposal)["decision"], "BLOCK")

    def test_risk_block_cannot_be_overridden_by_ceo(self):
        proposal = valid_proposal()
        proposal["risk_decision"] = "BLOCK"
        self.assertEqual(evaluate_ceo_approval(proposal)["decision"], "BLOCK")

    def test_signature_reference_does_not_replace_external_authentication(self):
        proposal = valid_proposal()
        result = evaluate_ceo_approval(proposal)
        self.assertTrue(result["requires_execution_controller_revalidation"])
        self.assertEqual(result["authority"], "advisory_only")

if __name__ == "__main__":
    unittest.main()
