import unittest

from aigc_ci_validation_agent import normalize_observation, diagnose_failure, sanitize_diagnostic

SHA = "a" * 40
TREE = "b" * 40


def fixture(**overrides):
    data = {
        "repository": "Lornt1666/AIGC",
        "expected_sha": SHA,
        "run": {"id": 123, "head_sha": SHA, "status": "completed", "conclusion": "success"},
        "jobs": [{"id": 456, "name": "validate", "status": "completed", "conclusion": "success",
                  "steps": [{"name": "canonical runner", "status": "completed", "conclusion": "success", "number": 9}]}],
        "artifacts": [{"id": 789, "name": f"aigc-evidence-{SHA}", "digest": "sha256:" + "c" * 64,
                       "expired": False, "workflow_run": {"head_sha": SHA}}],
        "stage_records": {"tests": {"status": "success", "target_sha": SHA, "run_id": 123,
                                    "tested_tree_sha": TREE, "record_sha256": "d" * 64}},
        "independent_review": {"approved": True, "subject_sha": SHA, "reviewer_identity": "reviewer:independent",
                               "authenticated": True},
    }
    data.update(overrides)
    return data


class CIValidationAgentTests(unittest.TestCase):
    def test_normalizes_consistent_exact_head_evidence(self):
        result = normalize_observation(**fixture())
        self.assertEqual(result["decision"], "OBSERVATION_COMPLETE")
        self.assertEqual(result["expected_sha"], SHA)
        self.assertEqual(result["workflow_run_id"], 123)
        self.assertFalse(result["automatic_changes_performed"])
        self.assertEqual(result["release_decision"], "BLOCK")

    def test_missing_artifact_blocks(self):
        data = fixture(artifacts=[])
        result = normalize_observation(**data)
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("exact_head_artifact_missing", result["reasons"])

    def test_stale_commit_blocks(self):
        data = fixture(run={"id": 123, "head_sha": "e" * 40, "status": "completed", "conclusion": "success"})
        result = normalize_observation(**data)
        self.assertIn("stale_or_mismatched_commit", result["reasons"])
        self.assertEqual(result["release_decision"], "BLOCK")

    def test_forged_success_indicator_cannot_override_failed_step(self):
        data = fixture(
            jobs=[{"id": 456, "name": "validate", "status": "completed", "conclusion": "failure",
                   "steps": [{"name": "milestone gate", "status": "completed", "conclusion": "failure", "number": 12}]}],
            stage_records={"milestone": {"status": "success", "target_sha": SHA, "run_id": 123,
                                         "tested_tree_sha": TREE, "record_sha256": "d" * 64}},
        )
        result = normalize_observation(**data)
        self.assertIn("workflow_step_failure", result["reasons"])
        self.assertIn("claimed_stage_success_conflicts_with_workflow_failure", result["reasons"])
        self.assertEqual(result["decision"], "BLOCK")

    def test_failed_independent_review_blocks(self):
        data = fixture(independent_review={"approved": False, "subject_sha": SHA,
                                          "reviewer_identity": "reviewer:independent", "authenticated": True})
        result = normalize_observation(**data)
        self.assertIn("independent_review_missing_or_invalid", result["reasons"])
        self.assertEqual(result["decision"], "BLOCK")

    def test_expired_artifact_is_not_accepted(self):
        data = fixture(artifacts=[{"id": 789, "name": f"aigc-evidence-{SHA}", "digest": "sha256:" + "c" * 64,
                                   "expired": True, "workflow_run": {"head_sha": SHA}}])
        result = normalize_observation(**data)
        self.assertIn("exact_head_artifact_missing", result["reasons"])

    def test_diagnosis_proposes_not_applies_repair(self):
        obs = normalize_observation(**fixture(run={"id": 123, "head_sha": SHA, "status": "completed", "conclusion": "failure"}))
        proposal = diagnose_failure(obs, "ModuleNotFoundError: No module named 'example'")
        self.assertEqual(proposal["classification"], "python_import_path")
        self.assertTrue(proposal["proposals"][0]["approval_required"])
        self.assertFalse(proposal["automatic_changes_performed"])
        self.assertEqual(proposal["release_decision"], "BLOCK")

    def test_sanitizer_redacts_authorization_like_values(self):
        text = sanitize_diagnostic("Author" + "ization: Bearer abc.def.secret")
        self.assertNotIn("abc.def.secret", text)

    def test_missing_run_blocks_even_if_other_signals_look_green(self):
        result = normalize_observation(**fixture(run=None))
        self.assertIn("workflow_run_missing", result["reasons"])
        self.assertEqual(result["decision"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
