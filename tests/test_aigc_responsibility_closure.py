import unittest

from aigc_responsibility_closure import BLOCK, READY, evaluate_closure, canonical_digest

SHA = "a" * 40
DIGEST = "b" * 64
MANIFEST = "c" * 64
NOW = 1_800_000_000

FLAGS = {
    "effective_protection": {"effective_settings_readback": True, "administrator_authorized": True},
    "reviewer_assignment": {"reviewer_qualified": True, "reviewer_independent": True, "administrator_authorized": True},
    "independent_review": {"reviewer_independent": True, "review_bound_to_sha": True, "findings_dispositioned": True},
    "remediation_retest": {"all_findings_retested": True, "retester_independent": True, "retest_bound_to_sha": True},
    "trusted_provenance": {"signature_verified": True, "issuer_verified": True, "repository_verified": True, "workflow_verified": True, "artifact_digest_verified": True},
    "human_acceptance": {"approver_authorized": True, "acceptance_signature_verified": True, "bound_to_manifest": True, "evidence_manifest_sha256": MANIFEST},
    "rx19_handoff": {"receipt_authenticated": True, "packet_digest_matches": True, "recipient_is_rx19": True, "evidence_manifest_sha256": MANIFEST},
}
TYPES = {
    "effective_protection": "effective-repository-protection",
    "reviewer_assignment": "independent-reviewer-assignment",
    "independent_review": "independent-security-review",
    "remediation_retest": "independent-remediation-retest",
    "trusted_provenance": "trusted-build-provenance",
    "human_acceptance": "human-acceptance",
    "rx19_handoff": "rx19-handoff-receipt",
}


def receipt(gate, **overrides):
    value = {
        "evidence_type": TYPES[gate],
        "subject_sha": SHA,
        "authenticated": True,
        "revoked": False,
        "content_sha256": DIGEST,
        "evidence_uri": "evidence://aigc/" + gate,
        "producer_identity": "trusted-test-adapter",
        "verification_method": "test-verifier/1.0",
        "verified_at": NOW,
    }
    value.update(FLAGS[gate])
    value.update(overrides)
    return value


def snapshot():
    return {
        "pr": {"number": 330, "state": "open", "draft": True, "merged": False, "head_sha": SHA},
        "ci": {"status": "completed", "conclusion": "success", "head_sha": SHA, "required_checks_complete": True},
        "evidence": {gate: receipt(gate) for gate in TYPES},
        "evidence_manifest_sha256": MANIFEST,
    }


class ResponsibilityClosureTests(unittest.TestCase):
    def test_complete_packet_is_only_ready_for_rx19_review(self):
        result = evaluate_closure(snapshot(), evaluation_time=NOW)
        self.assertEqual(result["disposition"], READY)
        self.assertEqual(result["release_decision"], BLOCK)
        self.assertFalse(result["rx19_decision_evaluated"])
        self.assertFalse(result["automatic_mutations_performed"])
        self.assertEqual(result["blocked_gates"], [])
        self.assertEqual(len(result["report_sha256"]), 71)

    def test_missing_evidence_blocks(self):
        data = snapshot()
        data["evidence"].pop("trusted_provenance")
        result = evaluate_closure(data, evaluation_time=NOW)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("trusted_provenance", result["blocked_gates"])

    def test_stale_ci_head_blocks(self):
        data = snapshot()
        data["ci"]["head_sha"] = "d" * 40
        result = evaluate_closure(data, evaluation_time=NOW)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("exact_head_ci", result["blocked_gates"])

    def test_stale_receipt_blocks(self):
        data = snapshot()
        data["evidence"]["effective_protection"]["verified_at"] = NOW - 3601
        result = evaluate_closure(data, evaluation_time=NOW)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("effective_protection", result["blocked_gates"])

    def test_wrong_commit_receipt_blocks(self):
        data = snapshot()
        data["evidence"]["independent_review"]["subject_sha"] = "d" * 40
        result = evaluate_closure(data, evaluation_time=NOW)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("independent_review", result["blocked_gates"])

    def test_unauthenticated_receipt_blocks(self):
        data = snapshot()
        data["evidence"]["human_acceptance"]["authenticated"] = False
        result = evaluate_closure(data, evaluation_time=NOW)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("human_acceptance", result["blocked_gates"])

    def test_wrong_manifest_blocks_acceptance_and_handoff(self):
        data = snapshot()
        data["evidence_manifest_sha256"] = "e" * 64
        result = evaluate_closure(data, evaluation_time=NOW)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("human_acceptance", result["blocked_gates"])
        self.assertIn("rx19_handoff", result["blocked_gates"])

    def test_pr_must_remain_draft_open_and_unmerged(self):
        data = snapshot()
        data["pr"]["draft"] = False
        result = evaluate_closure(data, evaluation_time=NOW)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("live_pr_state", result["blocked_gates"])

    def test_missing_pr_or_ci_snapshot_blocks(self):
        data = snapshot()
        data.pop("pr")
        data.pop("ci")
        result = evaluate_closure(data, evaluation_time=NOW)
        self.assertEqual(result["disposition"], BLOCK)
        self.assertIn("live_pr_state", result["blocked_gates"])
        self.assertIn("exact_head_ci", result["blocked_gates"])

    def test_report_digest_is_deterministic(self):
        first = evaluate_closure(snapshot(), evaluation_time=NOW)
        second = evaluate_closure(snapshot(), evaluation_time=NOW)
        self.assertEqual(first, second)
        self.assertEqual(canonical_digest({"b": 2, "a": 1}), canonical_digest({"a": 1, "b": 2}))


if __name__ == "__main__":
    unittest.main()
