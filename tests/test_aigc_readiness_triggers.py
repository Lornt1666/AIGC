import unittest

from aigc_runtime.readiness_triggers import assess_release_readiness


SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64


def baseline():
    return {
        "candidate_sha": SHA,
        "observed_ci_sha": SHA,
        "ci_status": "success",
        "evidence_digest": DIGEST,
        "independent_review_count": 0,
        "review_exact_sha": None,
        "review_findings_status": "OPEN_OR_UNKNOWN",
        "reviewer_qualified_independent": False,
        "protection_readback_status": "UNVERIFIED",
        "acceptance_authenticated": False,
        "acceptance_sha": None,
        "acceptance_evidence_digest": None,
        "merged": False,
        "post_merge_provenance_status": "NOT_RUN",
        "retention_retrieval_status": "NOT_RUN",
    }


class ReadinessTriggerTests(unittest.TestCase):
    def test_current_ci_pass_does_not_override_external_blocks(self):
        result = assess_release_readiness(baseline())
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["gate_results"][0]["status"], "PASS")
        self.assertEqual(set(result["blocked_gates"]), {
            "independent_human_review", "repository_protection",
            "authenticated_acceptance", "post_merge_provenance", "independent_retention",
        })
        self.assertEqual(result["canonical_release_authority"], "RX-19")
        self.assertFalse(result["production_authorization"])
        self.assertFalse(result["merge_authorization"])

    def test_new_commit_invalidates_ci_and_acceptance_binding(self):
        state = baseline()
        state["candidate_sha"] = "c" * 40
        result = assess_release_readiness(state)
        self.assertEqual(result["gate_results"][0]["status"], "BLOCK")
        self.assertIn("exact_head_ci", result["blocked_gates"])

    def test_all_gates_pass_only_with_authorized_evidence(self):
        state = baseline()
        state.update({
            "independent_review_count": 1,
            "review_exact_sha": SHA,
            "review_findings_status": "CLOSED_OR_NONE_WITH_EVIDENCE",
            "reviewer_qualified_independent": True,
            "protection_readback_status": "VERIFIED",
            "acceptance_authenticated": True,
            "acceptance_sha": SHA,
            "acceptance_evidence_digest": DIGEST,
            "merged": True,
            "post_merge_provenance_status": "VERIFIED",
            "retention_retrieval_status": "VERIFIED",
        })
        result = assess_release_readiness(state)
        self.assertEqual(result["status"], "READY_FOR_RX19_DECISION")
        self.assertEqual(result["blocked_gates"], [])
        self.assertFalse(result["production_authorization"])

    def test_unauthenticated_or_wrong_digest_acceptance_blocks(self):
        state = baseline()
        state.update({
            "acceptance_authenticated": True,
            "acceptance_sha": SHA,
            "acceptance_evidence_digest": "sha256:" + "c" * 64,
        })
        result = assess_release_readiness(state)
        self.assertIn("authenticated_acceptance", result["blocked_gates"])

    def test_invalid_candidate_sha_and_digest_raise(self):
        state = baseline()
        state["candidate_sha"] = "not-a-sha"
        with self.assertRaisesRegex(ValueError, "candidate_sha_invalid"):
            assess_release_readiness(state)
        state = baseline()
        state["evidence_digest"] = "bad"
        with self.assertRaisesRegex(ValueError, "evidence_digest_invalid"):
            assess_release_readiness(state)


if __name__ == "__main__":
    unittest.main()
