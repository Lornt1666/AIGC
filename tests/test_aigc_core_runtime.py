import ast
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError

from core.contracts import MutationPayload, TaskContract, ToolPermit
from core.arbiter import audit_python_source
from core.orchestrator import OrchestrationError, SagaCoordinator, SagaStep


def contract(**overrides):
    data = {
        "idempotency_key": "idempotency-key-000001",
        "project_id": "REGENEXCALIBUR",
        "objective": "Create a read-only evidence summary",
        "scope": ["repo evidence"],
        "acceptance_criteria": ["evidence references are present"],
        "risk_tier": "R0",
        "policy_version": "policy-v1",
        "allowed_agent_ids": ["RX-155"],
    }
    data.update(overrides)
    return TaskContract(**data)


class ContractTests(unittest.TestCase):
    def test_contract_is_strict_and_versioned(self):
        item = contract()
        self.assertEqual(item.contract_version, "1.0.0")
        with self.assertRaises(ValidationError):
            TaskContract(**{**item.model_dump(), "unknown_field": True})

    def test_task_hop_bound(self):
        with self.assertRaises(ValidationError):
            contract(max_hops=11)

    def test_irreversible_mutation_needs_human_receipt(self):
        with self.assertRaises(ValidationError):
            MutationPayload(operation="delete", resource="prod/db", idempotency_key="long-idempotency-key",
                precondition_digest="a"*64, irreversible=True)

    def test_tool_permit_expiry_bound(self):
        now = datetime.now(timezone.utc)
        with self.assertRaises(ValidationError):
            ToolPermit(permit_id=uuid4(), issuer="policy", subject_agent_id="RX-156", operation="write",
                resource="test", candidate_sha="a"*64, policy_version="v1", issued_at=now,
                expires_at=now+timedelta(minutes=30), idempotency_key="long-idempotency-key",
                signature_envelope_ref="secretless-ref")


class ArbiterTests(unittest.TestCase):
    def test_benign_source_is_screened_without_execution(self):
        result = audit_python_source("x = 1\nprint(x)\n")
        self.assertEqual(result.status, "BLOCK")  # print is not in the restricted AST allowlist policy
        self.assertFalse(result.execution_performed)

    def test_exec_eval_and_import_os_block(self):
        for source in ("exec('print(1)')", "eval('1+1')", "import os\nos.system('id')", "from subprocess import run"):
            with self.subTest(source=source):
                self.assertEqual(audit_python_source(source).status, "BLOCK")

    def test_deep_or_large_input_fails_closed(self):
        self.assertEqual(audit_python_source("x=1", max_bytes=1).status, "BLOCK")

    def test_arbitrary_calls_are_blocked(self):
        for source in ("print('x')", "object().danger()", "open('/etc/passwd')", "__import__('os')"):
            with self.subTest(source=source):
                self.assertEqual(audit_python_source(source).status, "BLOCK")


class OrchestratorSafetyTests(unittest.TestCase):
    def test_defaults_to_dry_run(self):
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
                                      adapters={"read": lambda *a, **k: None})
        self.assertTrue(coordinator.dry_run)

    def test_no_permit_means_no_live_side_effect(self):
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
                                      dry_run=False, adapters={"write": lambda *a, **k: None})
        self.assertIsNone(coordinator.permit_verifier)

    def test_ambiguous_adapter_failure_is_not_retried_without_reconciliation(self):
        calls = {"adapter": 0}
        async def adapter(payload, *, idempotency_key):
            calls["adapter"] += 1
            raise TimeoutError("response lost after possible remote commit")
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
                                      dry_run=False, adapters={"write": adapter}, max_attempts=3)
        async def run():
            with self.assertRaisesRegex(OrchestrationError, "retry_prohibited_without_trusted_outcome_reconciliation"):
                await coordinator._invoke_with_retry("write", adapter, {"resource": "x"}, "key-1", timeout=1)
        asyncio.run(run())
        self.assertEqual(calls["adapter"], 1)

    def test_unknown_outcome_is_not_retried(self):
        calls = {"adapter": 0, "reconcile": 0}
        async def adapter(payload, *, idempotency_key):
            calls["adapter"] += 1
            raise TimeoutError("response lost")
        async def reconcile(operation, payload, idempotency_key):
            calls["reconcile"] += 1
            return "UNKNOWN"
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
                                      dry_run=False, adapters={"write": adapter},
                                      outcome_reconciler=reconcile, max_attempts=3)
        async def run():
            with self.assertRaisesRegex(OrchestrationError, "retry_prohibited_side_effect_outcome:UNKNOWN"):
                await coordinator._invoke_with_retry("write", adapter, {"resource": "x"}, "key-2", timeout=1)
        asyncio.run(run())
        self.assertEqual(calls, {"adapter": 1, "reconcile": 1})

    def test_retry_requires_reconciler_to_prove_not_applied(self):
        calls = {"adapter": 0, "reconcile": 0}
        async def adapter(payload, *, idempotency_key):
            calls["adapter"] += 1
            if calls["adapter"] == 1:
                raise TimeoutError("first attempt not applied")
            return {"status": "ok"}
        async def reconcile(operation, payload, idempotency_key):
            calls["reconcile"] += 1
            return "NOT_APPLIED"
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
                                      dry_run=False, adapters={"write": adapter},
                                      outcome_reconciler=reconcile, max_attempts=2,
                                      base_retry_seconds=0, max_retry_seconds=0)
        async def run():
            return await coordinator._invoke_with_retry("write", adapter, {"resource": "x"}, "key-3", timeout=1)
        self.assertEqual(asyncio.run(run()), {"status": "ok"})
        self.assertEqual(calls, {"adapter": 2, "reconcile": 1})


if __name__ == "__main__":
    unittest.main()
