import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from datetime import datetime, timezone, timedelta

from aigc_governor import POLICY_VERSION, digest, evaluate_governance


NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
SOURCE_SHA = "a" * 40
TASK_DIGEST = "b" * 64


def valid_request(**overrides):
    request = {
        "request_id": "req-001",
        "task_id": "task-001",
        "source_sha": SOURCE_SHA,
        "task_digest": TASK_DIGEST,
        "action_ids": ["read_repository"],
        "risk_tier": "low",
        "requested_capabilities": ["read"],
        "policy_version": POLICY_VERSION,
        "expires_at": (NOW + timedelta(minutes=10)).isoformat(),
        "evidence": [{
            "id": "evidence-001",
            "sha256": "c" * 64,
            "source_sha": SOURCE_SHA,
            "authenticated": True,
            "issuer": "test-verifier",
            "purpose": "bind test evidence to exact source revision",
        }],
        "human_approval": {"approved": False},
    }
    request.update(overrides)
    return request


class GovernorPolicyTests(unittest.TestCase):
    def test_low_risk_scoped_read_only_request_passes_policy(self):
        result = evaluate_governance(valid_request(), now=NOW)
        self.assertEqual(result["decision"], "ALLOW_SCOPED")
        self.assertEqual(result["permitted_action_ids"], ["read_repository"])
        self.assertFalse(result["release_decision_authority"])
        self.assertTrue(result["execution_controller_revalidation_required"])

    def test_missing_field_blocks(self):
        request = valid_request()
        del request["evidence"]
        self.assertEqual(evaluate_governance(request, now=NOW)["decision"], "BLOCK")

    def test_unknown_field_blocks(self):
        request = valid_request(unreviewed_override=True)
        self.assertEqual(evaluate_governance(request, now=NOW)["decision"], "BLOCK")

    def test_expired_request_blocks(self):
        request = valid_request(expires_at=(NOW - timedelta(seconds=1)).isoformat())
        self.assertIn("expired_request", evaluate_governance(request, now=NOW)["reasons"])

    def test_bad_or_short_source_revision_blocks(self):
        request = valid_request(source_sha="main")
        self.assertIn("invalid_source_sha", evaluate_governance(request, now=NOW)["reasons"])

    def test_mismatched_evidence_revision_blocks(self):
        request = valid_request()
        request["evidence"][0]["source_sha"] = "d" * 40
        self.assertIn("evidence_0_source_sha_mismatch", evaluate_governance(request, now=NOW)["reasons"])

    def test_unauthenticated_evidence_blocks(self):
        request = valid_request()
        request["evidence"][0]["authenticated"] = False
        self.assertIn("evidence_0_not_authenticated_by_upstream_verifier", evaluate_governance(request, now=NOW)["reasons"])

    def test_wildcard_action_blocks(self):
        request = valid_request(action_ids=["*"])
        self.assertIn("invalid_or_wildcard_action_id", evaluate_governance(request, now=NOW)["reasons"])

    def test_production_action_requires_authenticated_subject_bound_human_approval(self):
        request = valid_request(action_ids=["deploy"], requested_capabilities=["production"])
        result = evaluate_governance(request, now=NOW)
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("explicit_human_approval_required", result["reasons"])
        approval_subject = {
            "request_id": request["request_id"],
            "task_id": request["task_id"],
            "source_sha": request["source_sha"],
            "task_digest": request["task_digest"],
            "action_ids": request["action_ids"],
            "requested_capabilities": request["requested_capabilities"],
        }
        request["human_approval"] = {
            "approved": True,
            "request_digest": digest(approval_subject),
            "approver_id": "authorized-human-001",
            "authenticated": True,
        }
        self.assertEqual(evaluate_governance(request, now=NOW)["decision"], "ALLOW_SCOPED")

    def test_mismatched_human_approval_subject_blocks(self):
        request = valid_request(action_ids=["deploy"], requested_capabilities=["production"])
        request["human_approval"] = {
            "approved": True,
            "request_digest": "e" * 64,
            "approver_id": "authorized-human-001",
            "authenticated": True,
        }
        self.assertIn("human_approval_subject_mismatch", evaluate_governance(request, now=NOW)["reasons"])

    def test_moderate_risk_requires_review_not_allow(self):
        result = evaluate_governance(valid_request(risk_tier="moderate"), now=NOW)
        self.assertEqual(result["decision"], "REVIEW_REQUIRED")
        self.assertEqual(result["permitted_action_ids"], [])

    def test_unknown_risk_fails_closed(self):
        result = evaluate_governance(valid_request(risk_tier="unknown"), now=NOW)
        self.assertEqual(result["decision"], "BLOCK")

    def test_signature_or_authentication_is_not_created_by_governor(self):
        result = evaluate_governance(valid_request(), now=NOW)
        self.assertEqual(result["authority"], "governance_policy_advisory")
        self.assertTrue(result["execution_controller_revalidation_required"])


if __name__ == "__main__":
    unittest.main()
