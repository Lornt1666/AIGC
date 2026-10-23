import copy
import unittest

from aigc_runtime.closure_workflow import evaluate_closure


SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64


def valid_snapshot():
    return {
        "repository": "Lornt1666/AIGC",
        "pr_number": 330,
        "pr_state": "open",
        "pr_merged": False,
        "candidate_sha": SHA,
        "observed_head_sha": SHA,
        "live_observation_authenticated": True,
        "observed_at": "2026-10-22T22:00:00Z",
        "evaluation_time": "2026-10-22T22:00:00Z",
        "head_changed_during_acquisition": False,
        "observation_source": "github_api",
        "base_branch": "feat/runtime-governance-harness-v1",
        "base_sha": "c" * 40,
        "required_ci_jobs": ["validate", "locked-release-1", "locked-release-2"],
        "ci_runs": [{
            "run_id": 1001, "run_attempt": 1, "head_sha": SHA, "status": "completed", "conclusion": "success",
            "jobs": [
                {"name": "validate", "conclusion": "success", "head_sha": SHA},
                {"name": "locked-release-1", "conclusion": "success", "head_sha": SHA},
                {"name": "locked-release-2", "conclusion": "success", "head_sha": SHA},
            ],
        }],
        "artifact": {
            "head_sha": SHA, "sha256": DIGEST, "run_id": 1001, "run_attempt": 1, "bytes_verified": True, "manifest_verified": True,
            "files": [{"path": "receipt.json", "sha256": DIGEST, "size": 10}],
        },
        "protection": {
            "authenticated": True, "status": "VERIFIED",
            "base_branch": "feat/runtime-governance-harness-v1",
            "release_branch": "main", "readback_digest": DIGEST,
        },
        "review": {
            "authenticated": True, "qualified_independent": True,
            "reviewed_sha": SHA, "findings_closed_with_retest": True, "review_threads_verified": True, "review_id": "PRREV-1",
        },
        "provenance": {
            "verified": True, "authenticated": True, "repository": "Lornt1666/AIGC",
            "source_sha": SHA, "subject_digest": DIGEST,
            "workflow_identity": "trusted-workflow", "issuer": "trusted-issuer",
        },
        "evidence_digest": DIGEST,
        "policy_version": "rx148-policy-v1",
        "acceptance": {
            "authenticated": True, "approver_role": "authorized_human_approver",
            "candidate_sha": SHA, "evidence_digest": DIGEST, "policy_version": "rx148-policy-v1", "receipt_id": "ACCEPT-1",
        },
        "rx19_handoff": {
            "authenticated": True, "recipient": "RX-19", "candidate_sha": SHA,
            "evidence_digest": DIGEST, "receipt_id": "HANDOFF-1",
        },
        "rx19_decision": {
            "authenticated": True, "authority": "RX-19", "decision": "APPROVE",
            "candidate_sha": SHA, "evidence_digest": DIGEST, "receipt_id": "DECISION-1",
        },
    }


class ClosureWorkflowTests(unittest.TestCase):
    def test_all_valid_evidence_is_deterministic_and_never_executes(self):
        snapshot = valid_snapshot()
        first = evaluate_closure(snapshot)
        second = evaluate_closure(snapshot)
        self.assertEqual(first["disposition"], "RX19_APPROVED_EVIDENCE_ONLY_NO_ACTION")
        self.assertEqual(first["manifest_digest"], second["manifest_digest"])
        self.assertFalse(first["merge_authorization"])
        self.assertFalse(first["deployment_authorization"])
        self.assertFalse(first["release_authorization"])

    def test_live_head_mismatch_marks_stale_and_blocks(self):
        snapshot = valid_snapshot()
        snapshot["observed_head_sha"] = "d" * 40
        result = evaluate_closure(snapshot)
        gates = {g["gate_id"]: g for g in result["gate_results"]}
        self.assertEqual(gates["G0_LIVE_RECONCILIATION"]["status"], "STALE")
        self.assertEqual(gates["G1_EXACT_HEAD_CI"]["status"], "STALE")
        self.assertEqual(result["disposition"], "BLOCK")

    def test_closed_or_merged_candidate_pr_blocks(self):
        snapshot = valid_snapshot()
        snapshot["pr_merged"] = True
        gate = next(g for g in evaluate_closure(snapshot)["gate_results"] if g["gate_id"] == "G0_LIVE_RECONCILIATION")
        self.assertEqual(gate["status"], "STALE")
    def test_old_live_observation_is_stale(self):
        snapshot = valid_snapshot()
        snapshot["evaluation_time"] = "2026-10-22T22:05:00Z"
        result = evaluate_closure(snapshot)
        gate = next(g for g in result["gate_results"] if g["gate_id"] == "G0_LIVE_RECONCILIATION")
        self.assertEqual(gate["status"], "STALE")
        self.assertEqual(result["disposition"], "BLOCK")

    def test_missing_evaluation_time_is_unverifiable(self):
        snapshot = valid_snapshot()
        snapshot.pop("evaluation_time")
        gate = next(g for g in evaluate_closure(snapshot)["gate_results"] if g["gate_id"] == "G0_LIVE_RECONCILIATION")
        self.assertEqual(gate["status"], "UNVERIFIABLE")
    def test_missing_ci_job_blocks(self):
        snapshot = valid_snapshot()
        snapshot["ci_runs"][0]["jobs"] = snapshot["ci_runs"][0]["jobs"][:1]
        result = evaluate_closure(snapshot)
        gate = next(g for g in result["gate_results"] if g["gate_id"] == "G1_EXACT_HEAD_CI")
        self.assertEqual(gate["status"], "BLOCK")
        self.assertIn("locked-release-1:missing", gate["reason"])

    def test_skipped_or_failed_required_job_blocks(self):
        snapshot = valid_snapshot()
        snapshot["ci_runs"][0]["jobs"][1]["conclusion"] = "skipped"
        self.assertEqual(
            next(g for g in evaluate_closure(snapshot)["gate_results"] if g["gate_id"] == "G1_EXACT_HEAD_CI")["status"],
            "BLOCK",
        )

    def test_missing_or_unauthenticated_evidence_never_passes(self):
        for key in ("protection", "review", "provenance", "acceptance", "rx19_handoff", "rx19_decision", "artifact"):
            with self.subTest(key=key):
                snapshot = valid_snapshot()
                snapshot.pop(key)
                result = evaluate_closure(snapshot)
                self.assertEqual(result["disposition"], "BLOCK")
                self.assertTrue(any(g["status"] != "PASS" for g in result["gate_results"]))

        snapshot = valid_snapshot()
        snapshot["acceptance"]["authenticated"] = False
        self.assertEqual(evaluate_closure(snapshot)["disposition"], "BLOCK")

    def test_contradictory_cross_bindings_block(self):
        snapshot = valid_snapshot()
        snapshot["review"]["reviewed_sha"] = "e" * 40
        snapshot["provenance"]["source_sha"] = "e" * 40
        snapshot["rx19_decision"]["evidence_digest"] = "sha256:" + "f" * 64
        result = evaluate_closure(snapshot)
        self.assertEqual(result["disposition"], "BLOCK")
        self.assertTrue(any(g["status"] == "BLOCK" for g in result["gate_results"]))

    def test_empty_or_inconclusive_protection_is_not_pass(self):
        snapshot = valid_snapshot()
        snapshot["protection"] = {"authenticated": False, "status": "UNKNOWN"}
        gate = next(g for g in evaluate_closure(snapshot)["gate_results"] if g["gate_id"] == "G3_EFFECTIVE_PROTECTION")
        self.assertEqual(gate["status"], "UNVERIFIABLE")

    def test_duplicate_artifact_paths_block(self):
        snapshot = valid_snapshot()
        snapshot["artifact"]["files"].append(copy.deepcopy(snapshot["artifact"]["files"][0]))
        gate = next(g for g in evaluate_closure(snapshot)["gate_results"] if g["gate_id"] == "G2_ARTIFACT_INTEGRITY")
        self.assertEqual(gate["status"], "BLOCK")

    def test_rx144_cannot_substitute_for_rx19(self):
        snapshot = valid_snapshot()
        snapshot["rx19_decision"]["authority"] = "RX-144"
        self.assertEqual(evaluate_closure(snapshot)["disposition"], "BLOCK")

    def test_missing_live_head_is_unverifiable_not_cached_pass(self):
        snapshot = valid_snapshot()
        snapshot["observed_head_sha"] = None
        result = evaluate_closure(snapshot)
        gate = next(g for g in result["gate_results"] if g["gate_id"] == "G0_LIVE_RECONCILIATION")
        self.assertEqual(gate["status"], "UNVERIFIABLE")
        self.assertEqual(result["disposition"], "BLOCK")


    def test_artifact_must_bind_to_successful_ci_run_attempt(self):
        snapshot = valid_snapshot()
        snapshot["artifact"]["run_attempt"] = 2
        gate = next(g for g in evaluate_closure(snapshot)["gate_results"] if g["gate_id"] == "G2_ARTIFACT_INTEGRITY")
        self.assertEqual(gate["status"], "BLOCK")
        self.assertIn("run_attempt", gate["reason"])

    def test_required_jobs_cannot_be_combined_across_runs(self):
        snapshot = valid_snapshot()
        original = snapshot["ci_runs"][0]
        snapshot["ci_runs"] = [
            {**original, "jobs": original["jobs"][:1]},
            {**original, "run_id": 1002, "jobs": original["jobs"][1:]},
        ]
        gate = next(g for g in evaluate_closure(snapshot)["gate_results"] if g["gate_id"] == "G1_EXACT_HEAD_CI")
        self.assertEqual(gate["status"], "BLOCK")

    def test_newer_failed_attempt_invalidates_older_success(self):
        snapshot = valid_snapshot()
        first = copy.deepcopy(snapshot["ci_runs"][0])
        newer = copy.deepcopy(first)
        newer["run_attempt"] = 2
        newer["conclusion"] = "failure"
        newer["jobs"][0]["conclusion"] = "failure"
        snapshot["ci_runs"] = [first, newer]
        result = evaluate_closure(snapshot)
        gates = {g["gate_id"]: g for g in result["gate_results"]}
        self.assertEqual(gates["G1_EXACT_HEAD_CI"]["status"], "BLOCK")
        self.assertIn("no_completed_successful_run_attempt", gates["G1_EXACT_HEAD_CI"]["reason"])
        self.assertEqual(gates["G2_ARTIFACT_INTEGRITY"]["status"], "BLOCK")
        self.assertEqual(result["disposition"], "BLOCK")

    def test_newer_in_progress_attempt_invalidates_older_success(self):
        snapshot = valid_snapshot()
        first = copy.deepcopy(snapshot["ci_runs"][0])
        newer = copy.deepcopy(first)
        newer["run_attempt"] = 2
        newer["status"] = "in_progress"
        newer["conclusion"] = None
        snapshot["ci_runs"] = [first, newer]
        gate = next(g for g in evaluate_closure(snapshot)["gate_results"] if g["gate_id"] == "G1_EXACT_HEAD_CI")
        self.assertEqual(gate["status"], "BLOCK")

    def test_conflicting_records_for_same_attempt_fail_closed(self):
        snapshot = valid_snapshot()
        conflicting = copy.deepcopy(snapshot["ci_runs"][0])
        conflicting["conclusion"] = "failure"
        snapshot["ci_runs"].append(conflicting)
        gate = next(g for g in evaluate_closure(snapshot)["gate_results"] if g["gate_id"] == "G1_EXACT_HEAD_CI")
        self.assertEqual(gate["status"], "BLOCK")

    def test_invalid_snapshot_identity_rejected(self):
        snapshot = valid_snapshot()
        snapshot["candidate_sha"] = "not-a-sha"
        with self.assertRaisesRegex(ValueError, "candidate_sha_invalid"):
            evaluate_closure(snapshot)


if __name__ == "__main__":
    unittest.main()
