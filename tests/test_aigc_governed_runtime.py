import unittest
from datetime import datetime, timezone

from aigc_runtime.governed_runtime import (
    AuditLedger, GovernanceError, PermitBroker, TaskContract, ToolPermit,
    WorkflowState, evaluate_cases, sha256_digest,
)

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
NOW_Z = "2026-10-21T12:00:00Z"


def contract(**overrides):
    values = dict(
        task_id="task-123", project_id="AIGC", agent_id="RX-103",
        agent_version="1.0.0", policy_version="policy-7",
        objective="read one approved record", scope=("record:123",),
        exclusions=("write", "delete"), acceptance_criteria=("record returned",),
        risk_tier="R0", input_refs=("sha256:abc",), allowed_tools=("records.read",),
        permitted_side_effects=(),
    )
    values.update(overrides)
    return TaskContract(**values)


def permit(**overrides):
    values = dict(
        permit_id="permit-1", task_id="task-123", agent_id="RX-103",
        tool_name="records.read", action="read", resource="record:123",
        policy_version="policy-7", issued_at="2026-10-21T11:00:00Z",
        expires_at="2026-10-21T13:00:00Z", max_uses=1,
    )
    values.update(overrides)
    return ToolPermit(**values)


class GovernedRuntimeTests(unittest.TestCase):
    def test_task_contract_rejects_unknown_version(self):
        with self.assertRaisesRegex(GovernanceError, "unsupported_task_contract_version"):
            contract(contract_version="aigc.task/999").validate()

    def test_task_contract_rejects_unknown_agent(self):
        with self.assertRaisesRegex(GovernanceError, "unknown_agent"):
            contract().validate(known_agent_ids={"RX-104"})

    def test_broker_denies_when_agent_disabled(self):
        ledger = AuditLedger()
        broker = PermitBroker(ledger, enabled_agent_ids=())
        result = broker.authorize(contract=contract(), permit=permit(),
            tool_name="records.read", action="read", resource="record:123",
            policy_version="policy-7", now=NOW)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "agent_not_enabled")
        self.assertEqual(len(ledger.snapshot()), 1)

    def test_broker_denies_policy_mismatch(self):
        ledger = AuditLedger()
        broker = PermitBroker(ledger, enabled_agent_ids={"RX-103"}, permit_verifier=lambda p: True)
        result = broker.authorize(contract=contract(), permit=permit(),
            tool_name="records.read", action="read", resource="record:123",
            policy_version="policy-8", now=NOW)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "policy_version_mismatch")


    def test_broker_denies_when_authenticator_is_not_configured(self):
        ledger = AuditLedger()
        broker = PermitBroker(ledger, enabled_agent_ids={"RX-103"})
        result = broker.authorize(contract=contract(), permit=permit(),
            tool_name="records.read", action="read", resource="record:123",
            policy_version="policy-7", now=NOW)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "permit_authenticator_unconfigured")

    def test_broker_authorizes_verified_narrow_permit_once(self):
        ledger = AuditLedger()
        broker = PermitBroker(ledger, enabled_agent_ids={"RX-103"}, permit_verifier=lambda p: p.signature == "verified-test-signature")
        signed = permit(signature="verified-test-signature")
        result = broker.authorize(contract=contract(), permit=signed,
            tool_name="records.read", action="read", resource="record:123",
            policy_version="policy-7", now=NOW)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "authorized")
        replay = broker.authorize(contract=contract(), permit=signed,
            tool_name="records.read", action="read", resource="record:123",
            policy_version="policy-7", now=NOW)
        self.assertFalse(replay["allowed"])
        self.assertEqual(replay["reason"], "permit_use_limit_exceeded")

    def test_broker_rejects_invalid_signature(self):
        broker = PermitBroker(AuditLedger(), enabled_agent_ids={"RX-103"}, permit_verifier=lambda p: False)
        result = broker.authorize(contract=contract(), permit=permit(),
            tool_name="records.read", action="read", resource="record:123",
            policy_version="policy-7", now=NOW)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "permit_signature_invalid")

    def test_broker_denies_tool_outside_contract(self):
        ledger = AuditLedger()
        broker = PermitBroker(ledger, enabled_agent_ids={"RX-103"})
        result = broker.authorize(contract=contract(), permit=permit(tool_name="admin.delete"),
            tool_name="admin.delete", action="delete", resource="record:123",
            policy_version="policy-7", now=NOW)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "tool_not_in_task_contract")

    def test_expired_permit_is_denied(self):
        with self.assertRaisesRegex(GovernanceError, "permit_expired"):
            permit(expires_at="2026-10-21T11:59:59Z").validate(NOW)

    def test_workflow_duplicate_event_is_idempotent(self):
        ledger = AuditLedger()
        wf = WorkflowState("task-123", ledger)
        first = wf.transition("VALIDATED", event_id="evt-1", reason="schema passed", at=NOW_Z)
        duplicate = wf.transition("BLOCKED", event_id="evt-1", reason="replay", at=NOW_Z)
        self.assertFalse(first["duplicate"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(wf.status, "VALIDATED")
        self.assertEqual(len(ledger.snapshot()), 1)

    def test_workflow_rejects_invalid_transition(self):
        wf = WorkflowState("task-123", AuditLedger())
        with self.assertRaisesRegex(GovernanceError, "invalid_transition"):
            wf.transition("SUCCEEDED", event_id="evt-1", reason="skip gates", at=NOW_Z)

    def test_workflow_terminal_failure_cannot_restart(self):
        wf = WorkflowState("task-123", AuditLedger())
        wf.transition("BLOCKED", event_id="evt-1", reason="missing permit", at=NOW_Z)
        with self.assertRaisesRegex(GovernanceError, "invalid_transition"):
            wf.transition("RUNNING", event_id="evt-2", reason="try anyway", at=NOW_Z)

    def test_evaluation_output_is_order_independent_and_digest_stable(self):
        evaluator = lambda case: case["input"] * 2
        cases = [
            {"case_id": "b", "input": 2, "expected": 4},
            {"case_id": "a", "input": 1, "expected": 2},
        ]
        left = evaluate_cases(cases, evaluator)
        right = evaluate_cases(reversed(cases), evaluator)
        self.assertEqual(left["results"], right["results"])
        self.assertEqual(left["evidence_digest"], right["evidence_digest"])
        self.assertEqual(left["failed_count"], 0)

    def test_evaluation_duplicate_ids_block(self):
        with self.assertRaisesRegex(GovernanceError, "evaluation_case_ids_missing_or_duplicate"):
            evaluate_cases([
                {"case_id": "x", "expected": 1},
                {"case_id": "x", "expected": 1},
            ], lambda case: 1)

    def test_digest_is_stable_for_mapping_key_order(self):
        self.assertEqual(sha256_digest({"a": 1, "b": 2}), sha256_digest({"b": 2, "a": 1}))


if __name__ == "__main__":
    unittest.main()
