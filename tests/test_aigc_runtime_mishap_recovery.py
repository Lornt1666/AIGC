import unittest

from aigc_runtime.recovery_gates import (
    GATE_SEQUENCE,
    RecoveryGateError,
    assess_root_cause,
    side_effect_retry_allowed,
    validate_exact_head_ci_receipt,
    validate_gate_progress,
    validate_incident_record,
)


SHA = "a" * 40
OTHER_SHA = "b" * 40
DIGEST = "sha256:" + "c" * 64


class RecoveryGateTests(unittest.TestCase):
    def test_incident_record_binds_to_candidate_and_preserves_unconfirmed_root_cause(self):
        record = {
            "incident_id": "INC-1",
            "severity": "high",
            "failure_signature": "test assertion failed",
            "detected_at": "2026-10-22T12:00:00Z",
            "owner": "runtime-ops",
            "source_commit_sha": SHA,
            "evidence_refs": ["job-log:1", "artifact:2"],
            "evidence_digest": DIGEST,
        }
        result = validate_incident_record(record, SHA)
        self.assertEqual(result["status"], "VALID")
        self.assertEqual(result["root_cause_status"], "UNCONFIRMED")
        with self.assertRaisesRegex(RecoveryGateError, "incident_evidence_commit_mismatch"):
            validate_incident_record(record, OTHER_SHA)

    def test_incident_record_missing_evidence_blocks(self):
        with self.assertRaisesRegex(RecoveryGateError, "incident_evidence_refs_missing"):
            validate_incident_record({
                "incident_id": "INC-2", "severity": "medium",
                "failure_signature": "unknown", "detected_at": "now", "owner": "ops",
                "source_commit_sha": SHA, "evidence_refs": [], "evidence_digest": DIGEST,
            }, SHA)

    def test_root_cause_remains_hypothesis_without_reproduction(self):
        result = assess_root_cause({
            "hypothesis": "database constraint caused failure",
            "supporting_evidence_refs": ["log:postgres"],
        })
        self.assertEqual(result["status"], "HYPOTHESIS")

    def test_root_cause_requires_reproduction_to_confirm(self):
        result = assess_root_cause({
            "hypothesis": "known assertion mismatch caused failure",
            "supporting_evidence_refs": ["log:test"],
            "reproduction_id": "repro-1",
            "reproduction_outcome": "REPRODUCED",
        })
        self.assertEqual(result["status"], "CONFIRMED_BY_REPRODUCTION")
        falsified = assess_root_cause({
            "hypothesis": "database warning caused failure",
            "supporting_evidence_refs": ["log:postgres"],
            "reproduction_id": "repro-2",
            "reproduction_outcome": "FALSIFIED",
        })
        self.assertEqual(falsified["status"], "FALSIFIED")

    def test_exact_head_receipt_requires_all_jobs_and_artifacts(self):
        receipt = {
            "observed_sha": SHA, "workflow_run_id": 42, "workflow_run_attempt": 2,
            "status": "completed", "conclusion": "success",
            "required_jobs": ["validate", "artifact-inspection"],
            "job_results": {"validate": "success", "artifact-inspection": "success"},
            "skipped_required_stages": [], "failed_or_error_test_count": 0,
            "artifact_digest": DIGEST, "evidence_digest": DIGEST,
        }
        decision = validate_exact_head_ci_receipt(receipt, SHA)
        self.assertEqual(decision.status, "PASS")
        self.assertEqual(decision.gate_id, "exact_head_evidence")
        with self.assertRaisesRegex(RecoveryGateError, "ci_receipt_commit_mismatch"):
            validate_exact_head_ci_receipt(receipt, OTHER_SHA)

    def test_failed_or_skipped_ci_stage_blocks(self):
        base = {
            "observed_sha": SHA, "workflow_run_id": 42, "workflow_run_attempt": 1,
            "status": "completed", "conclusion": "success",
            "required_jobs": ["validate"], "job_results": {"validate": "success"},
            "skipped_required_stages": ["runtime-tests"], "failed_or_error_test_count": 0,
            "artifact_digest": DIGEST, "evidence_digest": DIGEST,
        }
        self.assertEqual(validate_exact_head_ci_receipt(base, SHA).status, "BLOCK")
        base["skipped_required_stages"] = []
        base["job_results"]["validate"] = "failure"
        self.assertEqual(validate_exact_head_ci_receipt(base, SHA).status, "BLOCK")

    def test_uncertain_side_effect_cannot_be_retried_without_reconciliation(self):
        self.assertFalse(side_effect_retry_allowed("UNKNOWN"))
        self.assertFalse(side_effect_retry_allowed("UNKNOWN", "UNKNOWN"))
        self.assertTrue(side_effect_retry_allowed("UNKNOWN", "RECONCILED_NOT_APPLIED"))
        self.assertTrue(side_effect_retry_allowed("UNKNOWN", "IDEMPOTENT_REPLAY_PROVEN_SAFE"))
        self.assertFalse(side_effect_retry_allowed("SUCCEEDED"))
        self.assertTrue(side_effect_retry_allowed("DEFINITELY_NOT_APPLIED"))

    def test_gate_progress_is_ordered_and_sha_bound(self):
        results = {gate: "PASS" for gate in GATE_SEQUENCE}
        decision = validate_gate_progress(GATE_SEQUENCE[-1], SHA, results, SHA)
        self.assertEqual(decision.status, "PASS")
        blocked = validate_gate_progress(GATE_SEQUENCE[-1], SHA, {**results, GATE_SEQUENCE[2]: "BLOCK"}, SHA)
        self.assertEqual(blocked.status, "BLOCK")
        mismatch = validate_gate_progress(GATE_SEQUENCE[0], SHA, results, OTHER_SHA)
        self.assertEqual(mismatch.status, "BLOCK")


if __name__ == "__main__":
    unittest.main()
