"""Deterministic adversarial tests for AIGC's security assurance agents.

No test in this module claims to perform live GitHub read-back or cryptographic
verification. The verifier is a test double; production wiring must use a real
approved verifier and preserve its raw output.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aigc_security_agents import (
    BLOCK, PASS, UNKNOWN, CybersecurityAgent, GitHubProtectorAgent,
    ReleaseAssuranceAgent, TrustworthinessAssessmentAgent,
)


REPO = "Lornt1666/AIGC"
SHA = "a" * 40
DIGEST = "b" * 64


def good_snapshot():
    return {
        "read_status": "OK",
        "release_tag_pattern": "v*",
        "rulesets": [
            {"enforcement": "active", "target": "branch",
             "conditions": {"ref_name": {"include": ["refs/heads/main"]}},
             "rules": [{"type": "pull_request"}, {"type": "required_status_checks"}],
             "bypass_actors": []},
            {"enforcement": "active", "target": "tag",
             "conditions": {"ref_name": {"include": ["refs/tags/v*"]}},
             "rules": [{"type": "deletion"}, {"type": "update"}],
             "bypass_actors": []},
        ],
        "branch_protection": {
            "read_status": "OK", "required_approving_review_count": 1,
            "required_status_checks": ["canonical-validation"],
            "allow_force_pushes": False, "allow_deletions": False, "enforce_admins": True,
        },
    }


def good_cyber_checks():
    ids = ["workflow_permissions", "action_pinning", "secret_scan", "dependency_scan",
           "static_analysis", "adversarial_tests"]
    return [{"id": x, "commit_sha": SHA, "executed": True, "run_id": "run-123",
             "evidence_sha256": DIGEST, "conclusion": "success"} for x in ids]


def good_evidence():
    return [{"kind": kind, "repository": REPO, "commit_sha": SHA,
             "subject_sha256": DIGEST, "attestation_ref": "immutable-test-fixture"}
            for kind in ("canonical_receipt_bundle", "release_artifact")]


class GitHubProtectorTests(unittest.TestCase):
    def test_complete_snapshot_passes_protection_checks(self):
        report = GitHubProtectorAgent().assess(good_snapshot(), REPO, SHA)
        self.assertEqual(report["decision"], PASS)

    def test_missing_or_unreadable_snapshot_is_unknown_and_blocks(self):
        for snapshot in (None, {}, {"read_status": "FORBIDDEN"}):
            report = GitHubProtectorAgent().assess(snapshot, REPO, SHA)
            self.assertEqual(report["decision"], BLOCK)
            self.assertEqual(report["checks"][0]["status"], UNKNOWN)

    def test_bypass_actor_blocks_main_ruleset(self):
        snapshot = good_snapshot()
        snapshot["rulesets"][0]["bypass_actors"] = [{"actor_id": 7}]
        report = GitHubProtectorAgent().assess(snapshot, REPO, SHA)
        self.assertEqual(report["decision"], BLOCK)


class CybersecurityTests(unittest.TestCase):
    def test_all_actual_revision_bound_checks_pass(self):
        report = CybersecurityAgent().assess(good_cyber_checks(), REPO, SHA)
        self.assertEqual(report["decision"], PASS)

    def test_wrong_revision_and_missing_execution_metadata_block(self):
        checks = good_cyber_checks()
        checks[0]["commit_sha"] = "c" * 40
        checks[1].pop("run_id")
        report = CybersecurityAgent().assess(checks, REPO, SHA)
        self.assertEqual(report["decision"], BLOCK)
        statuses = {c["id"]: c["status"] for c in report["checks"]}
        self.assertEqual(statuses["workflow_permissions"], BLOCK)
        self.assertEqual(statuses["action_pinning"], UNKNOWN)


class TrustworthinessTests(unittest.TestCase):
    def test_no_real_verifier_blocks(self):
        report = TrustworthinessAssessmentAgent().assess(good_evidence(), REPO, SHA)
        self.assertEqual(report["decision"], BLOCK)
        self.assertEqual(report["checks"][0]["status"], UNKNOWN)

    def test_both_subjects_need_verification(self):
        agent = TrustworthinessAssessmentAgent(
            verifier=lambda item: {"verified": item.get("attestation_ref") == "immutable-test-fixture",
                                   "workflow_identity": "test-only", "predicate_type": "test-only"})
        self.assertEqual(agent.assess(good_evidence(), REPO, SHA)["decision"], PASS)
        evidence = good_evidence()
        evidence[1]["commit_sha"] = "c" * 40
        self.assertEqual(agent.assess(evidence, REPO, SHA)["decision"], BLOCK)

    def test_verifier_exception_fails_closed(self):
        def broken(_item):
            raise RuntimeError("verifier unavailable")
        report = TrustworthinessAssessmentAgent(broken).assess(good_evidence(), REPO, SHA)
        self.assertEqual(report["decision"], BLOCK)


class ReleaseAssuranceTests(unittest.TestCase):
    def test_release_blocks_if_any_agent_is_missing_or_mismatched(self):
        protector = GitHubProtectorAgent().assess(good_snapshot(), REPO, SHA)
        cyber = CybersecurityAgent().assess(good_cyber_checks(), REPO, SHA)
        trust = TrustworthinessAssessmentAgent(
            lambda item: {"verified": True}).assess(good_evidence(), REPO, SHA)
        aggregator = ReleaseAssuranceAgent()
        self.assertEqual(aggregator.decide([protector, cyber, trust], REPO, SHA)["decision"], PASS)
        self.assertEqual(aggregator.decide([protector, cyber], REPO, SHA)["decision"], BLOCK)
        self.assertEqual(aggregator.decide([protector, cyber, trust], REPO, "d" * 40)["decision"], BLOCK)

    def test_tampered_report_digest_missing_blocks(self):
        reports = [
            GitHubProtectorAgent().assess(good_snapshot(), REPO, SHA),
            CybersecurityAgent().assess(good_cyber_checks(), REPO, SHA),
            TrustworthinessAssessmentAgent(lambda item: {"verified": True}).assess(good_evidence(), REPO, SHA),
        ]
        reports[0]["evidence_digest"] = ""
        self.assertEqual(ReleaseAssuranceAgent().decide(reports, REPO, SHA)["decision"], BLOCK)


if __name__ == "__main__":
    unittest.main()
