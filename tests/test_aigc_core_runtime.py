import ast
import asyncio
import unittest
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError

from core.contracts import MutationPayload, TaskContract, ToolPermit
from core.arbiter import audit_python_source
from core.orchestrator import (OrchestrationError, SagaCoordinator, SagaStep,
                               dead_letter_disposition_id, validate_hop_count, canonical_json, sha256_text)


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
    def test_hop_count_rejects_negative_boolean_and_over_limit_values(self):
        for value in (-1, True, 11, 1.5, "2", None):
            with self.subTest(value=value), self.assertRaises(OrchestrationError):
                validate_hop_count(value, 10)

    def test_hop_count_accepts_zero_and_configured_limit(self):
        self.assertEqual(validate_hop_count(0, 10), 0)
        self.assertEqual(validate_hop_count(10, 10), 10)

    def test_hop_count_configuration_is_bounded(self):
        for limit in (0, 11, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                validate_hop_count(0, limit)

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

    def test_allowlisted_pure_math_import_can_be_screened(self):
        result = audit_python_source("import math\nx = math.sqrt(4)\n")
        self.assertEqual(result.status, "PASS_STATIC_SCREEN_ONLY")
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
    def test_dead_letter_disposition_key_is_stable_and_stream_scoped(self):
        first = dead_letter_disposition_id("aigc:tasks:v1", "1700000000000-0")
        self.assertEqual(first, dead_letter_disposition_id("aigc:tasks:v1", "1700000000000-0"))
        self.assertNotEqual(first, dead_letter_disposition_id("aigc:tasks:v2", "1700000000000-0"))
        self.assertNotEqual(first, dead_letter_disposition_id("aigc:tasks:v1", "1700000000000-1"))
        for stream, stream_id in (("", "1-0"), ("tasks", ""), (None, "1-0")):
            with self.subTest(stream=stream, stream_id=stream_id), self.assertRaises(ValueError):
                dead_letter_disposition_id(stream, stream_id)

    def test_pending_reclaim_advances_xautoclaim_cursor(self):
        class FakeRedis:
            def __init__(self):
                self.starts = []
            async def xautoclaim(self, *args, **kwargs):
                self.starts.append(kwargs["start_id"])
                return ("123456789-0" if len(self.starts) == 1 else "0-0", [], [])
            async def xreadgroup(self, *args, **kwargs):
                return []
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost")
        fake = FakeRedis()
        coordinator.redis = fake
        async def no_pending_dead_letters(limit=100):
            return 0
        coordinator._publish_pending_dead_letters = no_pending_dead_letters
        async def run():
            await coordinator.consume_once(lambda event, conn: None, block_ms=1)
            await coordinator.consume_once(lambda event, conn: None, block_ms=1)
        asyncio.run(run())
        self.assertEqual(fake.starts, ["0-0", "123456789-0"])

    def test_rejects_non_finite_operation_timeout(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "operation_timeout_seconds"):
                SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
                                operation_timeout_seconds=value)

    def test_rejects_invalid_retry_delay_bounds(self):
        invalid = (
            {"base_retry_seconds": -0.01, "max_retry_seconds": 1},
            {"base_retry_seconds": 2, "max_retry_seconds": 1},
            {"base_retry_seconds": 1, "max_retry_seconds": 60.01},
            {"base_retry_seconds": float("nan"), "max_retry_seconds": 1},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides), self.assertRaisesRegex(ValueError, "retry"):
                SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost", **overrides)

    def test_rejects_unbounded_database_pool_size(self):
        with self.assertRaisesRegex(ValueError, "database pool bounds"):
            SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
                            pool_min_size=1, pool_max_size=257)

    def test_saga_deadline_includes_waiting_for_concurrency_slot(self):
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
                                      dry_run=True, adapters={"read": lambda *a, **k: None})
        item = contract(timeout_seconds=0.02)
        async def run():
            coordinator.semaphore = asyncio.Semaphore(1)
            await coordinator.semaphore.acquire()
            try:
                started = asyncio.get_running_loop().time()
                with self.assertRaisesRegex(OrchestrationError, "saga_deadline_exceeded_waiting_for_concurrency_slot"):
                    await coordinator.run_saga(item, [SagaStep("s1", "read", {})], dry_run=True)
                self.assertLess(asyncio.get_running_loop().time() - started, 0.15)
            finally:
                coordinator.semaphore.release()
        asyncio.run(run())

    def test_saga_deadline_covers_multiple_steps_and_fails_closed_before_late_compensation(self):
        calls = {"adapter": 0}
        async def adapter(payload, *, idempotency_key):
            calls["adapter"] += 1
            await asyncio.sleep(0.05)
            return {"status": "applied"}
        async def permit(permit_ref, claims, key):
            return True
        async def reconcile(operation, payload, key):
            return "NOT_APPLIED"
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
            dry_run=False, adapters={"write": adapter, "undo": adapter},
            permit_verifier=permit, outcome_reconciler=reconcile, operation_timeout_seconds=1)
        async def record_event(*args, **kwargs):
            return None
        coordinator.record_event = record_event
        item = contract(candidate_sha="a" * 40, timeout_seconds=0.08)
        steps = [
            SagaStep(step_id="first", operation="write", input_payload={}, compensation_operation="undo",
                     compensation_payload={}, side_effecting=True, idempotent=True, compensation_idempotent=True),
            SagaStep(step_id="second", operation="write", input_payload={}, compensation_operation="undo",
                     compensation_payload={}, side_effecting=True, idempotent=True, compensation_idempotent=True),
        ]
        async def run():
            started = asyncio.get_running_loop().time()
            with self.assertRaisesRegex(OrchestrationError, "compensation_status:RECONCILIATION_REQUIRED"):
                await coordinator.run_saga(item, steps, dry_run=False, permit_ref="permit-1")
            return asyncio.get_running_loop().time() - started
        elapsed = asyncio.run(run())
        self.assertLess(elapsed, 0.2)
        self.assertEqual(calls["adapter"], 2)

    def test_defaults_to_dry_run(self):
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
                                      adapters={"read": lambda *a, **k: None})
        self.assertTrue(coordinator.dry_run)

    def test_live_mutation_requires_candidate_sha_before_any_adapter_call(self):
        calls = []
        async def adapter(payload, *, idempotency_key):
            calls.append(idempotency_key)
            return {"ok": True}
        async def permit(ref, claims, key):
            return True
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
            dry_run=False, adapters={"write": adapter}, permit_verifier=permit)
        item = contract()
        with self.assertRaisesRegex(Exception, "exact_candidate_sha"):
            asyncio.run(coordinator.run_saga(item, [SagaStep("s1", "write", {}, idempotent=True, side_effecting=False)],
                dry_run=False, permit_ref="signed-permit-ref"))
        self.assertEqual(calls, [])

    def test_all_step_permits_are_preflighted_before_first_side_effect(self):
        calls = []
        async def adapter(payload, *, idempotency_key):
            calls.append(idempotency_key)
            return {"ok": True}
        async def permit(ref, claims, key):
            return claims.get("operation") != "second"
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
            dry_run=False, adapters={"first": adapter, "second": adapter}, permit_verifier=permit)
        item = contract(candidate_sha="a"*40)
        steps = [SagaStep("s1", "first", {}, idempotent=True, side_effecting=False), SagaStep("s2", "second", {}, idempotent=True, side_effecting=False)]
        with self.assertRaisesRegex(Exception, "permit_verification_denied"):
            asyncio.run(coordinator.run_saga(item, steps, dry_run=False, permit_ref="signed-permit-ref"))
        self.assertEqual(calls, [])
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

    def test_retry_budget_is_one_wall_clock_deadline(self):
        calls = {"adapter": 0, "reconcile": 0}
        async def adapter(payload, *, idempotency_key):
            calls["adapter"] += 1
            await asyncio.sleep(0.05)
            raise TimeoutError("simulated slow adapter response")
        async def reconcile(operation, payload, idempotency_key):
            calls["reconcile"] += 1
            return "NOT_APPLIED"
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost",
                                      dry_run=False, adapters={"write": adapter},
                                      outcome_reconciler=reconcile, max_attempts=4,
                                      base_retry_seconds=0, max_retry_seconds=0)
        async def run():
            started = asyncio.get_running_loop().time()
            with self.assertRaisesRegex(OrchestrationError, "operation_deadline_exceeded"):
                await coordinator._invoke_with_retry("write", adapter, {"resource": "x"}, "key-deadline", timeout=0.08)
            return asyncio.get_running_loop().time() - started
        elapsed = asyncio.run(run())
        self.assertLess(elapsed, 0.15)
        self.assertLessEqual(calls["adapter"], 2)

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


    def test_append_only_trigger_check_is_bound_to_events_table(self):
        class FakeCursor:
            def __init__(self):
                self.query = ""
                self.params = ()
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def execute(self, query, params=()):
                self.query, self.params = query, params
            async def fetchone(self):
                if "aigc_schema_migrations" in self.query:
                    return {"version": self.params[0]} if self.params and self.params[0] in {"001_runtime", "002_receipt_claims", "003_dead_letters"} else None
                if "pg_trigger" in self.query:
                    return {"present": True}
                if "to_regclass" in self.query:
                    return {"tasks": "aigc_tasks", "events": "aigc_events",
                            "outbox": "aigc_outbox", "consumed": "aigc_consumed_events",
                            "dead_letters": "aigc_dead_letters"}
                raise AssertionError("unexpected schema verification query")
        class FakeConnection:
            def __init__(self):
                self.cursor_instance = FakeCursor()
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            def cursor(self):
                return self.cursor_instance
        class FakePool:
            def __init__(self):
                self.connection_instance = FakeConnection()
            def connection(self):
                return self.connection_instance
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost")
        pool = FakePool()
        coordinator.pool = pool
        asyncio.run(coordinator._ensure_schema())
        cursor = pool.connection_instance.cursor_instance
        self.assertIn("tgrelid=to_regclass(%s)", cursor.query)
        self.assertEqual(cursor.params, ("aigc_events_no_update", "public.aigc_events"))



    def test_saga_payload_is_snapshotted_before_awaited_permit_verification(self):
        original = {"resource": {"value": "approved"}}
        observed = {"payload": None, "preflight_digest": None}
        async def adapter(payload, *, idempotency_key):
            observed["payload"] = payload
            return {"ok": True}
        async def permit(ref, claims, key):
            observed["preflight_digest"] = claims["input_digest"]
            original["resource"]["value"] = "changed-after-authorization-start"
            return True
        coordinator = SagaCoordinator(
            database_url="postgresql://unused", redis_url="redis://localhost",
            dry_run=False, adapters={"write": adapter}, permit_verifier=permit)
        async def record_event(*args, **kwargs):
            return None
        coordinator.record_event = record_event
        item = contract(candidate_sha="a" * 40)
        step = SagaStep("snapshot", "write", original, idempotent=True, side_effecting=False)
        result = asyncio.run(coordinator.run_saga(item, [step], dry_run=False, permit_ref="permit"))
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(observed["payload"]["resource"]["value"], "approved")
        self.assertEqual(
            observed["preflight_digest"],
            sha256_text(canonical_json({"resource": {"value": "approved"}})),
        )
        self.assertEqual(original["resource"]["value"], "changed-after-authorization-start")

    def test_live_saga_rechecks_permit_immediately_before_effect(self):
        calls = {"permit": 0, "adapter": 0}
        async def adapter(payload, *, idempotency_key):
            calls["adapter"] += 1
            return {"ok": True}
        async def permit(ref, claims, key):
            calls["permit"] += 1
            return calls["permit"] == 1
        coordinator = SagaCoordinator(
            database_url="postgresql://unused", redis_url="redis://localhost",
            dry_run=False, adapters={"write": adapter}, permit_verifier=permit)
        async def record_event(*args, **kwargs):
            return None
        coordinator.record_event = record_event
        item = contract(candidate_sha="a" * 40)
        step = SagaStep("point-of-effect", "write", {}, idempotent=True, side_effecting=False)
        with self.assertRaisesRegex(OrchestrationError, "saga_step_blocked"):
            asyncio.run(coordinator.run_saga(item, [step], dry_run=False, permit_ref="permit"))
        self.assertEqual(calls, {"permit": 2, "adapter": 0})

    def test_saga_reauthorizes_each_retry_attempt(self):
        calls = {"permit": 0, "adapter": 0, "reconcile": 0}
        async def adapter(payload, *, idempotency_key):
            calls["adapter"] += 1
            raise TimeoutError("synthetic transient failure")
        async def permit(ref, claims, key):
            calls["permit"] += 1
            return calls["permit"] < 3
        async def reconcile(operation, payload, key):
            calls["reconcile"] += 1
            return "NOT_APPLIED"
        coordinator = SagaCoordinator(
            database_url="postgresql://unused", redis_url="redis://localhost",
            dry_run=False, adapters={"write": adapter}, permit_verifier=permit,
            outcome_reconciler=reconcile, max_attempts=3,
            base_retry_seconds=0, max_retry_seconds=0)
        async def record_event(*args, **kwargs):
            return None
        coordinator.record_event = record_event
        item = contract(candidate_sha="a" * 40)
        step = SagaStep("retry-auth", "write", {}, idempotent=True, side_effecting=False)
        with self.assertRaisesRegex(OrchestrationError, "saga_step_blocked"):
            asyncio.run(coordinator.run_saga(item, [step], dry_run=False, permit_ref="permit"))
        self.assertEqual(calls["permit"], 3)
        self.assertEqual(calls["adapter"], 1)
        self.assertEqual(calls["reconcile"], 1)

    def test_saga_rejects_oversized_payload_before_permit_or_adapter(self):
        calls = {"permit": 0, "adapter": 0}
        async def adapter(payload, *, idempotency_key):
            calls["adapter"] += 1
            return {"ok": True}
        async def permit(ref, claims, key):
            calls["permit"] += 1
            return True
        coordinator = SagaCoordinator(
            database_url="postgresql://unused", redis_url="redis://localhost",
            dry_run=False, adapters={"write": adapter}, permit_verifier=permit)
        item = contract(candidate_sha="a" * 40)
        step = SagaStep("oversize", "write", {"data": "x" * 1_000_001},
                        idempotent=True, side_effecting=False)
        with self.assertRaisesRegex(OrchestrationError, "saga_payload_size_limit_exceeded"):
            asyncio.run(coordinator.run_saga(item, [step], dry_run=False, permit_ref="permit"))
        self.assertEqual(calls, {"permit": 0, "adapter": 0})


    def test_compensation_permit_binds_original_and_compensation_payload_digests(self):
        observed = {"claims": None, "payload": None}
        async def adapter(payload, *, idempotency_key):
            observed["payload"] = payload
            return {"restored": True}
        async def permit(ref, claims, key):
            observed["claims"] = claims
            return True
        async def reconcile(operation, payload, key):
            return "NOT_APPLIED"
        coordinator = SagaCoordinator(
            database_url="postgresql://unused", redis_url="redis://localhost",
            dry_run=False, adapters={"undo": adapter}, permit_verifier=permit,
            outcome_reconciler=reconcile)
        item = contract(candidate_sha="a" * 40)
        completed_step = SagaStep(
            "completed", "write", {"resource": "original"},
            compensation_operation="undo", compensation_payload={"restore": "previous"},
            side_effecting=True, idempotent=True, compensation_idempotent=True)
        failed_step = SagaStep("failed", "write", {"resource": "failed"}, idempotent=True, side_effecting=False)
        async def run():
            return await coordinator._compensate(
                item, [completed_step], failed_step=failed_step, failed_key="failed-key",
                permit_ref="permit", deadline=time.monotonic() + 2)
        result = asyncio.run(run())
        self.assertEqual(result["status"], "COMPENSATION_REQUESTS_SUCCEEDED")
        self.assertEqual(observed["payload"], {"restore": "previous"})
        self.assertEqual(observed["claims"]["input_digest"],
                         sha256_text(canonical_json({"restore": "previous"})))
        self.assertEqual(observed["claims"]["original_input_digest"],
                         sha256_text(canonical_json({"resource": "original"})))

    def test_saga_payload_with_unpaired_surrogate_fails_closed(self):
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost")
        item = contract()
        step = SagaStep("surrogate", "read", {"value": "\ud800"})
        with self.assertRaisesRegex(OrchestrationError, "saga_payload_not_canonical_json"):
            asyncio.run(coordinator.run_saga(item, [step], dry_run=True))


if __name__ == "__main__":
    unittest.main()
