import unittest
from datetime import datetime, timezone, timedelta

from aigc_governor_milestones import STAGES, evaluate_milestones

SHA = "a" * 40


def valid_record():
    stages = {}
    for name in STAGES:
        stages[name] = {
            "status": "PASS",
            "subject_sha": SHA,
            "evidence_ref": f"evidence://{name}/sha256-{'b' * 64}",
            "verifier_identity": f"verifier:{name}",
            "verified": True,
        }
    return {
        "schema_version": "aigc-governor-milestones/1.0",
        "subject_sha": SHA,
        "stages": stages,
        "human_acceptance": {
            "accepted": True,
            "subject_sha": SHA,
            "approver_identity": "human:authorized-reviewer",
            "authenticated": True,
        },
    }


class GovernorMilestonesTests(unittest.TestCase):
    def test_complete_record_is_only_eligible_for_external_review(self):
        result = evaluate_milestones(valid_record(), expected_sha=SHA)
        self.assertEqual(result["decision"], "ELIGIBLE_FOR_EXTERNAL_PRODUCTION_REVIEW")
        self.assertFalse(result["production_enabled"])
        self.assertFalse(result["cryptographic_verification_performed"])
        self.assertFalse(result["execution_performed"])
        self.assertFalse(result["release_decision_authority"])

    def test_missing_stage_blocks(self):
        record = valid_record()
        del record["stages"][STAGES[0]]
        result = evaluate_milestones(record, expected_sha=SHA)
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("authenticated_policy_inputs:missing_record", result["reasons"])

    def test_wrong_subject_blocks(self):
        record = valid_record()
        record["stages"][STAGES[1]]["subject_sha"] = "c" * 40
        result = evaluate_milestones(record, expected_sha=SHA)
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("cryptographic_evidence_validation:subject_sha_mismatch", result["reasons"])

    def test_missing_verifier_blocks(self):
        record = valid_record()
        record["stages"][STAGES[2]]["verifier_identity"] = ""
        result = evaluate_milestones(record, expected_sha=SHA)
        self.assertEqual(result["decision"], "BLOCK")

    def test_boolean_claim_without_evidence_ref_blocks(self):
        record = valid_record()
        record["stages"][STAGES[3]]["evidence_ref"] = ""
        result = evaluate_milestones(record, expected_sha=SHA)
        self.assertEqual(result["decision"], "BLOCK")

    def test_human_acceptance_must_bind_to_exact_subject(self):
        record = valid_record()
        record["human_acceptance"]["subject_sha"] = "d" * 40
        result = evaluate_milestones(record, expected_sha=SHA)
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("human_acceptance_subject_mismatch", result["reasons"])

    def test_unauthenticated_human_acceptance_blocks(self):
        record = valid_record()
        record["human_acceptance"]["authenticated"] = False
        result = evaluate_milestones(record, expected_sha=SHA)
        self.assertEqual(result["decision"], "BLOCK")

    def test_explicit_failure_blocks(self):
        record = valid_record()
        record["stages"][STAGES[4]]["status"] = "FAIL"
        result = evaluate_milestones(record, expected_sha=SHA)
        self.assertEqual(result["decision"], "BLOCK")

    def test_invalid_expected_sha_blocks(self):
        result = evaluate_milestones(valid_record(), expected_sha="main")
        self.assertEqual(result["decision"], "BLOCK")

    def test_unknown_stage_blocks(self):
        record = valid_record()
        record["stages"]["magic_override"] = {"status": "PASS"}
        result = evaluate_milestones(record, expected_sha=SHA)
        self.assertEqual(result["decision"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
