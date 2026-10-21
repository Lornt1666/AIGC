"""Offline tests for AER and Red/Blue/Green report producers; no live attacks or writes."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aigc_team_agents import (
    AERAgent, AuthenticatedTeamReportAdapter, BLOCK, BlueTeamAgent, GreenTeamAgent,
    PASS, POLICY_ID, RedTeamAgent, SCHEMA_VERSION, canonical_json, sha256_hex,
)

REPO, SHA, TREE = "Lornt1666/AIGC", "a" * 40, "c" * 40
POLICY_DIGEST, DIGEST = "d" * 64, "e" * 64


def envelope():
    return {"schema_version": SCHEMA_VERSION, "policy_id": POLICY_ID, "policy_digest": POLICY_DIGEST,
            "repository": REPO, "commit_sha": SHA, "tree_sha": TREE, "invocation_id": "test-run-1",
            "producer_identity": "test-fixture-only", "issued_at_utc": "2026-10-20T12:00:00Z",
            "expires_at_utc": "2026-10-20T13:00:00Z", "evidence_refs": []}


def aer_inputs():
    return {"architecture_baseline_ref": "adr-set-v1", "interface_contracts": "contracts-v1",
            "failure_mode_review": "fmea-v1", "observability_baseline": "otel-v1",
            "rollback_plan_ref": "rollback-v1",
            "slos": [{"service": "api", "objective": "99.9%", "measurement_window": "30d"}],
            "unresolved_critical_risks": []}


class AERTests(unittest.TestCase):
    def test_complete_readiness_evidence_passes(self):
        self.assertEqual(AERAgent().assess(envelope(), aer_inputs())["decision"], PASS)

    def test_missing_slo_or_risk_inventory_blocks(self):
        inputs = aer_inputs()
        inputs.pop("slos")
        inputs.pop("unresolved_critical_risks")
        self.assertEqual(AERAgent().assess(envelope(), inputs)["decision"], BLOCK)


class RedTeamTests(unittest.TestCase):
    def test_missing_authorization_blocks_and_active_execution_is_not_performed(self):
        report = RedTeamAgent().assess(envelope(), None, [], ["test-target"])
        self.assertEqual(report["decision"], BLOCK)
        self.assertEqual(next(c for c in report["checks"] if c["id"] == "active_execution")["status"], "UNKNOWN")

    def test_out_of_scope_target_blocks(self):
        auth = {"authorization_id": "auth-1", "repository": REPO, "environment": "disposable",
                "allowed_targets": ["synthetic://fixture-a"], "allowed_test_types": ["static"],
                "start_at_utc": "2026-10-20T12:00:00Z", "end_at_utc": "2026-10-20T13:00:00Z",
                "approver_identity": "reviewer", "authenticated": True}
        report = RedTeamAgent().assess(envelope(), auth, [], ["https://unrelated.example"])
        self.assertEqual(report["decision"], BLOCK)


class BlueTeamTests(unittest.TestCase):
    def test_detection_requires_timestamped_alert_evidence(self):
        telemetry = [{"source_id": "ci-audit", "observed_at_utc": "2026-10-20T12:00:00Z", "evidence_sha256": DIGEST}]
        report = BlueTeamAgent().assess(envelope(), telemetry, [{"scenario_id": "workflow-tamper", "expected_detection": True}])
        self.assertEqual(report["decision"], BLOCK)

    def test_recorded_alert_evidence_passes(self):
        telemetry = [{"source_id": "ci-audit", "observed_at_utc": "2026-10-20T12:00:00Z", "evidence_sha256": DIGEST}]
        scenarios = [{"scenario_id": "workflow-tamper", "expected_detection": True,
                      "alert": {"alert_id": "alert-1", "detected_at_utc": "2026-10-20T12:00:01Z", "evidence_sha256": DIGEST}}]
        self.assertEqual(BlueTeamAgent().assess(envelope(), telemetry, scenarios)["decision"], PASS)


class GreenTeamTests(unittest.TestCase):
    def test_self_approval_and_auto_merge_block(self):
        remediation = {"finding_ids": ["F-1"], "patch_ref": "commit-ref", "regression_tests": ["test-1"],
                       "rollback_plan_ref": "rollback-v1", "before_metrics": {"latency": 10},
                       "after_metrics": {"latency": 9}, "author_identity": "agent-a",
                       "independent_reviewer": "agent-a", "auto_merge": True}
        self.assertEqual(GreenTeamAgent().assess(envelope(), remediation)["decision"], BLOCK)

    def test_incomplete_proposal_blocks(self):
        self.assertEqual(GreenTeamAgent().assess(envelope(), {})["decision"], BLOCK)


class AdapterTests(unittest.TestCase):
    def _reports(self):
        reports = []
        for agent_id in ("aer", "red-team", "blue-team", "green-team"):
            report = {"agent_id": agent_id, "repository": REPO, "commit_sha": SHA, "tree_sha": TREE,
                      "policy_digest": POLICY_DIGEST, "decision": PASS,
                      "authentication": {"status": "AUTHENTICATED"}}
            report["report_sha256"] = sha256_hex(canonical_json(report))
            reports.append(report)
        return reports

    def test_missing_verifier_blocks_and_never_decides_release(self):
        result = AuthenticatedTeamReportAdapter().validate(self._reports(), REPO, SHA, TREE, POLICY_DIGEST)
        self.assertEqual(result["status"], BLOCK)
        self.assertEqual(result["release_decision"], "NOT_MADE")

    def test_adapter_requires_signature_and_exact_binding(self):
        adapter = AuthenticatedTeamReportAdapter(lambda report: {"verified": True, "signer_identity": "trusted-test"})
        reports = self._reports()
        self.assertEqual(adapter.validate(reports, REPO, SHA, TREE, POLICY_DIGEST)["status"], PASS)
        reports[0]["tree_sha"] = "f" * 40
        self.assertEqual(adapter.validate(reports, REPO, SHA, TREE, POLICY_DIGEST)["status"], BLOCK)


if __name__ == "__main__":
    unittest.main()
