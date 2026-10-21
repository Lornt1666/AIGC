"""Unit tests for the bounded CEO action approval policy."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aigc_ceo_agent import REQUIRED_BINDINGS, evaluate_action, POLICY_ID


def envelope():
    return {
        "repository": "Lornt1666/AIGC",
        "commit_sha": "a" * 40,
        "tree_sha": "b" * 40,
        "policy_digest": "c" * 64,
        "invocation_id": "ceo-test-001",
    }


def verify_evidence(item, env):
    return (
        item.get("authentication_status") == "AUTHENTICATED"
        and item.get("evidence_ref") is not None
        and all(item.get(key) == env.get(key) for key in REQUIRED_BINDINGS)
    )


def valid_request():
    env = envelope()
    return {
        **env,
        "action_id": "doc-index-refresh-001",
        "action_type": "regenerate_internal_index",
        "risk_level": "low",
        "reversible": True,
        "external_effect": False,
        "estimated_cost": 0,
        "permission_change": False,
        "secret_access": False,
        "execution_scope": "internal-only",
        "independent_review": True,
        "evidence": [{
            **env,
            "evidence_ref": "sha256:" + "d" * 64,
            "authentication_status": "AUTHENTICATED",
        }],
    }


class CEOAgentTests(unittest.TestCase):
    def test_approves_only_bounded_low_risk_internal_reversible_action(self):
        result = evaluate_action(valid_request(), envelope(), verify_evidence)
        self.assertEqual(result["decision"], "APPROVE")
        self.assertEqual(result["policy_id"], POLICY_ID)
        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["release_decision"], "NOT_MADE")
        self.assertEqual(len(result["receipt_digest_sha256"]), 64)

    def test_no_trusted_verifier_holds_even_if_caller_claims_authenticated(self):
        result = evaluate_action(valid_request(), envelope())
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason_code"], "trusted_evidence_verifier_unavailable")

    def test_trusted_verifier_failure_holds(self):
        result = evaluate_action(valid_request(), envelope(), lambda _item, _env: False)
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason_code"], "trusted_evidence_verification_failed")

    def test_missing_binding_holds(self):
        env = envelope()
        del env["tree_sha"]
        result = evaluate_action(valid_request(), env, verify_evidence)
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason_code"], "missing_version_binding")

    def test_mismatched_revision_holds(self):
        req = valid_request()
        req["commit_sha"] = "e" * 40
        result = evaluate_action(req, envelope(), verify_evidence)
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason_code"], "request_envelope_binding_mismatch")

    def test_unauthenticated_evidence_holds(self):
        req = valid_request()
        req["evidence"][0]["authentication_status"] = "UNAUTHENTICATED"
        result = evaluate_action(req, envelope())
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason_code"], "evidence_not_authenticated")

    def test_evidence_from_another_commit_holds(self):
        req = valid_request()
        req["evidence"][0]["commit_sha"] = "f" * 40
        result = evaluate_action(req, envelope())
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason_code"], "evidence_version_binding_mismatch")

    def test_deploy_merge_and_release_require_human(self):
        for action in ("deploy", "merge", "release", "secret_access", "financial_commitment"):
            with self.subTest(action=action):
                req = valid_request()
                req["action_type"] = action
                result = evaluate_action(req, envelope())
                self.assertEqual(result["decision"], "REQUIRES_HUMAN")
                self.assertTrue(result["requires_human_authorization"])
                self.assertFalse(result["execution_performed"])

    def test_external_effect_or_cost_requires_human(self):
        req = valid_request()
        req["external_effect"] = True
        self.assertEqual(evaluate_action(req, envelope())["decision"], "REQUIRES_HUMAN")
        req = valid_request()
        req["estimated_cost"] = 0.01
        self.assertEqual(evaluate_action(req, envelope())["decision"], "REQUIRES_HUMAN")

    def test_medium_or_high_risk_requires_human(self):
        for risk in ("medium", "high", "critical"):
            req = valid_request()
            req["risk_level"] = risk
            self.assertEqual(evaluate_action(req, envelope())["decision"], "REQUIRES_HUMAN")

    def test_missing_independent_review_holds(self):
        req = valid_request()
        req["independent_review"] = False
        result = evaluate_action(req, envelope())
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason_code"], "independent_review_missing")

    def test_no_action_execution_side_effect(self):
        req = valid_request()
        with tempfile.TemporaryDirectory() as temp:
            before = list(Path(temp).iterdir())
            result = evaluate_action(req, envelope())
            self.assertEqual(list(Path(temp).iterdir()), before)
            self.assertFalse(result["execution_performed"])


if __name__ == "__main__":
    unittest.main()
