import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aigc_control_plane_agents import (
    AdversarialControlTestAgent, AllowlistedExtensionRegistry, AuthenticatedPolicyInputAgent,
    ControlError, CosignEvidenceVerifier, ExecutionControllerEnforcementAgent,
    ExtensionSpec, IndependentReviewAcceptanceAgent, MVPPolicyCreatorAgent,
)

SHA = "a" * 40
DIGEST = "b" * 64


class FakeIdentity:
    def verify(self, token, *, issuer, audience, subject):
        return {"iss": issuer, "aud": audience, "sub": subject, "authenticated": True}


class FakeAudit:
    def __init__(self, fail=False):
        self.records, self.fail = [], fail
    def append(self, record):
        if self.fail:
            return ""
        self.records.append(dict(record))
        return f"audit://receipt/{len(self.records)}"


class FakeBackend:
    def __init__(self, status="SUCCEEDED"):
        self.calls, self.status = [], status
    def execute(self, action_id, payload, idempotency_key):
        self.calls.append((action_id, dict(payload), idempotency_key))
        return {"status": self.status}


class ControlPlaneAgentTests(unittest.TestCase):
    def test_extension_registry_requires_enabled_explicit_action(self):
        reg = AllowlistedExtensionRegistry([ExtensionSpec("docs", "1.0", "pkg:docs.run",
            ("docs.generate",), "docs.input.v1", "docs.output.v1", "low", enabled=True)])
        self.assertEqual(reg.resolve("docs", "1.0", "docs.generate").extension_id, "docs")
        with self.assertRaises(ControlError):
            reg.resolve("docs", "2.0", "docs.generate")
        with self.assertRaises(ControlError):
            reg.resolve("docs", "1.0", "network.*")

    def test_policy_creator_emits_draft_not_approval(self):
        draft = MVPPolicyCreatorAgent().create_draft(policy_id="policy.core", policy_version="1.0",
            owner="governance-owner", rules=[{"rule_id":"deny-unknown", "condition":"authorization_unknown",
            "effect":"BLOCK", "rationale":"unknown authority fails closed", "source_refs":["spec://aigc/governance"]}])
        self.assertEqual(draft.status, "DRAFT")
        self.assertEqual(draft.rules[0].effect, "BLOCK")
        with self.assertRaises(ControlError):
            MVPPolicyCreatorAgent().create_draft(policy_id="x", policy_version="1", owner="o",
                rules=[{"rule_id":"bad", "condition":"x", "effect":"ALLOW", "rationale":"x", "source_refs":["ref"]}])

    def test_authenticated_policy_inputs_rejects_wrong_allowlist(self):
        agent = AuthenticatedPolicyInputAgent(FakeIdentity(), {"https://issuer"}, {"aigc"}, {"policy-service"})
        result = agent.authenticate("token", issuer="https://issuer", audience="aigc", subject="policy-service")
        self.assertEqual(result["subject"], "policy-service")
        with self.assertRaises(ControlError):
            agent.authenticate("token", issuer="https://attacker", audience="aigc", subject="policy-service")

    def test_cosign_verifier_checks_process_and_exact_bindings(self):
        statement = {"subject_sha256": DIGEST, "source_sha": SHA, "workflow_identity":"https://github.com/org/repo/.github/workflows/trusted.yml"}
        runner = lambda *a, **kw: SimpleNamespace(returncode=0, stdout=__import__("json").dumps(statement), stderr="")
        verifier = CosignEvidenceVerifier("/opt/cosign", statement["workflow_identity"], "https://token.actions.githubusercontent.com", runner=runner)
        verified = verifier.verify_bundle(bundle_path="bundle.json", artifact_sha256=DIGEST, source_sha=SHA, workflow_identity=statement["workflow_identity"])
        self.assertTrue(verified["verified"])
        with self.assertRaises(ControlError):
            verifier.verify_bundle(bundle_path="bundle.json", artifact_sha256="c"*64, source_sha=SHA, workflow_identity=statement["workflow_identity"])
        bad_runner = lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="invalid signature")
        with self.assertRaises(ControlError):
            CosignEvidenceVerifier("/opt/cosign", statement["workflow_identity"], "issuer", runner=bad_runner).verify_bundle(
                bundle_path="bundle.json", artifact_sha256=DIGEST, source_sha=SHA, workflow_identity=statement["workflow_identity"])

    def test_controller_fails_closed_and_audits_success(self):
        audit, backend = FakeAudit(), FakeBackend()
        controller = ExecutionControllerEnforcementAgent(audit_sink=audit, backend=backend,
            decision_verifier=lambda d: d.get("signature_valid") is True, allowlisted_actions={"artifact.publish"})
        decision = {"decision":"ALLOW_SCOPED", "action_id":"artifact.publish",
            "expires_at":(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(), "signature_valid":True}
        result = controller.execute(action_id="artifact.publish", payload={"digest":DIGEST}, decision=decision, idempotency_key="job-1")
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(len(audit.records), 2)
        self.assertEqual(len(backend.calls), 1)
        with self.assertRaises(ControlError):
            controller.execute(action_id="shell.exec", payload={}, decision=decision, idempotency_key="job-2")

    def test_controller_blocks_if_audit_unavailable_or_decision_expired(self):
        backend = FakeBackend()
        controller = ExecutionControllerEnforcementAgent(audit_sink=FakeAudit(fail=True), backend=backend,
            decision_verifier=lambda d: True, allowlisted_actions={"artifact.publish"})
        decision = {"decision":"ALLOW_SCOPED", "action_id":"artifact.publish",
            "expires_at":(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()}
        with self.assertRaises(ControlError):
            controller.execute(action_id="artifact.publish", payload={}, decision=decision, idempotency_key="job-1")
        self.assertEqual(backend.calls, [])
        decision["expires_at"] = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
        with self.assertRaises(ControlError):
            ExecutionControllerEnforcementAgent(audit_sink=FakeAudit(), backend=backend,
                decision_verifier=lambda d: True, allowlisted_actions={"artifact.publish"}).execute(
                    action_id="artifact.publish", payload={}, decision=decision, idempotency_key="job-2")
        self.assertEqual(backend.calls, [])

    def test_adversarial_agent_detects_denial(self):
        controller = ExecutionControllerEnforcementAgent(audit_sink=FakeAudit(), backend=FakeBackend(),
            decision_verifier=lambda d: True, allowlisted_actions={"artifact.publish"})
        base = {"action_id":"artifact.publish", "payload":{}, "decision":{"decision":"BLOCK"},
                "idempotency_key":"job-1"}
        result = AdversarialControlTestAgent().run_cases(controller, base, [
            {"case_id":"block-decision", "expected":"BLOCKED"}])
        self.assertTrue(result["passed"])

    def test_independent_review_requires_real_references_and_human_acceptance(self):
        agent = IndependentReviewAcceptanceAgent()
        blocked = agent.evaluate(subject_sha=SHA, reviewer_id="reviewer", reviewer_independent=True,
            findings=[], signed_review_ref=None, human_acceptance_ref=None)
        self.assertEqual(blocked["decision"], "BLOCK")
        pending = agent.evaluate(subject_sha=SHA, reviewer_id="reviewer", reviewer_independent=True,
            findings=[], signed_review_ref="review://signed/1", human_acceptance_ref=None)
        self.assertEqual(pending["decision"], "REVIEW_REQUIRED")
        complete = agent.evaluate(subject_sha=SHA, reviewer_id="reviewer", reviewer_independent=True,
            findings=[{"finding_id":"F-1", "status":"RESOLVED"}], signed_review_ref="review://signed/1",
            human_acceptance_ref="approval://human/1")
        self.assertEqual(complete["decision"], "REVIEW_EVIDENCE_COMPLETE")


if __name__ == "__main__":
    unittest.main()
