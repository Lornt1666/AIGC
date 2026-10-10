from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import unittest

from src.gemini_workflow.control_store import (
    EmergencyStopActive,
    IdempotencyConflict,
    InMemoryRuntimeControlStore,
    PostgresRuntimeControlStore,
    RunStateError,
    RuntimeControlUnavailable,
    RuntimeLimitExceeded,
    StopEpochChanged,
    TokenBudgetExceeded,
    UnavailableRuntimeControlStore,
)
from src.gemini_workflow.runtime_limits import (
    RuntimeLimitConfigurationError,
    RuntimeLimits,
)


class ManualClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs: int) -> None:
        self.value += timedelta(**kwargs)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def key(index: int) -> str:
    return f"request-key-{index:04d}"


def limits(**overrides: int) -> RuntimeLimits:
    values = {
        "principal_runs_per_minute": 3,
        "principal_runs_per_day": 10,
        "principal_reserved_tokens_per_day": 1_000,
        "global_runs_per_minute": 6,
        "global_runs_per_day": 20,
        "global_reserved_tokens_per_day": 2_000,
        "max_tokens_per_run": 1_000,
    }
    values.update(overrides)
    return RuntimeLimits(**values)


class GeminiRuntimeControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = ManualClock()
        self.store = InMemoryRuntimeControlStore(clock=self.clock)
        self.principal = "shared-credential-prod"

    def reserve(
        self,
        index: int = 1,
        *,
        principal: str | None = None,
        request: str | None = None,
        tokens: int = 100,
        policy: RuntimeLimits | None = None,
    ):
        return self.store.reserve_run(
            principal_id=principal or self.principal,
            idempotency_key=key(index),
            request_sha256=digest(request or f"request-{index}"),
            reserved_tokens=tokens,
            limits=policy or limits(),
        )

    def complete(self, index: int = 1):
        run = self.reserve(index)
        self.store.mark_executing(
            run_id=run.run_id,
            expected_epoch=run.stop_epoch,
        )
        return self.store.complete_run(
            run_id=run.run_id,
            expected_epoch=run.stop_epoch,
            actual_tokens=80,
            execution_event_id=(
                f"AIGC-GEMINI-EVENT-execution-{index:04d}"
            ),
            evidence_object_uri=(
                f"gs://evidence/{run.run_id}/execution.json"
            ),
            evidence_generation=index,
        )

    def test_stop_epoch_is_durable_transition_boundary(self) -> None:
        first = self.reserve()
        self.assertEqual(first.stop_epoch, 0)
        self.assertEqual(self.store.get_run(first.run_id), first)

        stopped = self.store.activate_emergency_stop(
            actor_principal_id=self.principal,
            reason="Operator activated the durable emergency stop.",
        )
        self.assertTrue(stopped.active)
        self.assertEqual(stopped.stop_epoch, 1)
        with self.assertRaises(EmergencyStopActive):
            self.store.assert_epoch_current(
                run_id=first.run_id,
                expected_epoch=first.stop_epoch,
            )

        self.store.fail_run(
            run_id=first.run_id,
            state="stopped",
            reason="Run invalidated by the durable emergency stop.",
        )
        cleared = self.store.clear_emergency_stop(
            actor_principal_id=self.principal,
            reason="Operator cleared the stop after controlled review.",
            expected_epoch=stopped.stop_epoch,
            exact_phrase=f"CLEAR GEMINI STOP EPOCH {stopped.stop_epoch}",
        )
        self.assertFalse(cleared.active)
        self.assertEqual(cleared.stop_epoch, 2)
        with self.assertRaises(StopEpochChanged):
            self.store.assert_epoch_current(
                run_id=first.run_id,
                expected_epoch=first.stop_epoch,
            )

        second = self.reserve(2)
        self.assertEqual(second.stop_epoch, 2)
        self.store.assert_epoch_current(
            run_id=second.run_id,
            expected_epoch=second.stop_epoch,
        )

    def test_stale_clear_is_rejected(self) -> None:
        state = self.store.activate_emergency_stop(
            actor_principal_id=self.principal,
            reason="Operator activated emergency control for review.",
        )
        with self.assertRaises(StopEpochChanged):
            self.store.clear_emergency_stop(
                actor_principal_id=self.principal,
                reason="Stale emergency clear must not be accepted.",
                expected_epoch=state.stop_epoch - 1,
                exact_phrase=(
                    f"CLEAR GEMINI STOP EPOCH {state.stop_epoch - 1}"
                ),
            )
        self.assertTrue(self.store.get_emergency_state().active)

    def test_active_stop_blocks_without_consuming_rate_limit(self) -> None:
        policy = limits(
            principal_runs_per_minute=1,
            global_runs_per_minute=1,
        )
        stopped = self.store.activate_emergency_stop(
            actor_principal_id=self.principal,
            reason="Stop before any provider reservation is created.",
        )
        with self.assertRaises(EmergencyStopActive):
            self.reserve(policy=policy)
        self.store.clear_emergency_stop(
            actor_principal_id=self.principal,
            reason="Controlled test clear after blocked reservation.",
            expected_epoch=stopped.stop_epoch,
            exact_phrase=f"CLEAR GEMINI STOP EPOCH {stopped.stop_epoch}",
        )
        created = self.reserve(policy=policy)
        self.assertFalse(created.replayed)

    def test_idempotent_replay_returns_same_run(self) -> None:
        created = self.reserve()
        replay = self.reserve()
        self.assertEqual(replay.run_id, created.run_id)
        self.assertTrue(replay.replayed)
        self.assertEqual(self.store.get_run(created.run_id).run_id, created.run_id)

    def test_idempotency_key_conflict_fails_closed(self) -> None:
        self.reserve(request="first normalized request")
        with self.assertRaises(IdempotencyConflict):
            self.reserve(request="different normalized request")

    def test_idempotency_is_bound_to_model_and_source_revision(self) -> None:
        common = {
            "run_id": "AIGC-GEMINI-RUN-model-binding",
            "principal_id": self.principal,
            "idempotency_key": key(1),
            "request_sha256": digest("request-1"),
            "model": "gemini-2.5-pro",
            "source_revision": "a" * 40,
            "reserved_tokens": 100,
            "limits": limits(),
        }
        created = self.store.reserve_run(**common)
        replay = self.store.reserve_run(**common)
        self.assertEqual(created.run_id, replay.run_id)
        self.assertEqual(created.model, "gemini-2.5-pro")
        self.assertEqual(created.source_revision, "a" * 40)
        self.assertNotEqual(created.idempotency_key_sha256, key(1))
        with self.assertRaises(IdempotencyConflict):
            self.store.reserve_run(
                **{
                    **common,
                    "run_id": "AIGC-GEMINI-RUN-other-model",
                    "model": "gemini-2.5-flash",
                }
            )

    def test_clear_requires_exact_epoch_bound_phrase(self) -> None:
        stopped = self.store.activate_emergency_stop(
            actor_principal_id=self.principal,
            reason="Operator activated emergency control for phrase test.",
        )
        with self.assertRaises(ValueError):
            self.store.clear_emergency_stop(
                actor_principal_id=self.principal,
                reason="Clear request with the wrong confirmation phrase.",
                expected_epoch=stopped.stop_epoch,
                exact_phrase="CLEAR GEMINI STOP EPOCH 999",
            )
        self.assertTrue(self.store.get_emergency_state().active)

    def test_concurrent_idempotent_requests_have_one_winner(self) -> None:
        def reserve_once(_index: int):
            return self.reserve()

        with ThreadPoolExecutor(max_workers=12) as pool:
            reservations = list(pool.map(reserve_once, range(24)))

        self.assertEqual(len({item.run_id for item in reservations}), 1)
        self.assertEqual(
            sum(not item.replayed for item in reservations),
            1,
        )
        self.assertEqual(
            sum(item.replayed for item in reservations),
            23,
        )

    def test_self_attested_label_cannot_reset_stable_principal_limit(self) -> None:
        policy = limits(
            principal_runs_per_minute=2,
            global_runs_per_minute=10,
        )
        # Labels are deliberately absent from the control-store contract. Both
        # requests are bound to the stable shared-credential principal.
        self.reserve(1, principal=self.principal, policy=policy)
        self.reserve(2, principal=self.principal, policy=policy)
        with self.assertRaises(RuntimeLimitExceeded) as caught:
            self.reserve(3, principal=self.principal, policy=policy)
        self.assertEqual(caught.exception.scope, "principal")
        self.assertGreater(caught.exception.retry_after_seconds, 0)

    def test_global_rate_limit_applies_across_principals(self) -> None:
        policy = limits(
            principal_runs_per_minute=2,
            global_runs_per_minute=2,
        )
        self.reserve(1, principal="credential-principal-one", policy=policy)
        self.reserve(2, principal="credential-principal-two", policy=policy)
        with self.assertRaises(RuntimeLimitExceeded) as caught:
            self.reserve(3, principal="credential-principal-three", policy=policy)
        self.assertEqual(caught.exception.scope, "global")

    def test_minute_limit_resets_only_after_new_window(self) -> None:
        policy = limits(
            principal_runs_per_minute=1,
            global_runs_per_minute=1,
        )
        self.reserve(1, policy=policy)
        with self.assertRaises(RuntimeLimitExceeded):
            self.reserve(2, policy=policy)
        self.clock.advance(minutes=1)
        second = self.reserve(2, policy=policy)
        self.assertFalse(second.replayed)

    def test_principal_token_reservation_fails_before_provider(self) -> None:
        policy = limits(
            principal_reserved_tokens_per_day=500,
            global_reserved_tokens_per_day=1_000,
            max_tokens_per_run=500,
        )
        self.reserve(1, tokens=400, policy=policy)
        with self.assertRaises(TokenBudgetExceeded) as caught:
            self.reserve(2, tokens=200, policy=policy)
        self.assertEqual(caught.exception.scope, "principal")

    def test_global_token_reservation_applies_across_principals(self) -> None:
        policy = limits(
            principal_reserved_tokens_per_day=700,
            global_reserved_tokens_per_day=1_000,
            max_tokens_per_run=700,
        )
        self.reserve(
            1,
            principal="credential-principal-one",
            tokens=600,
            policy=policy,
        )
        with self.assertRaises(TokenBudgetExceeded) as caught:
            self.reserve(
                2,
                principal="credential-principal-two",
                tokens=500,
                policy=policy,
            )
        self.assertEqual(caught.exception.scope, "global")

    def test_completion_never_refunds_original_reservation(self) -> None:
        policy = limits(
            principal_reserved_tokens_per_day=1_000,
            global_reserved_tokens_per_day=2_000,
            max_tokens_per_run=1_000,
        )
        run = self.reserve(1, tokens=600, policy=policy)
        self.store.mark_executing(
            run_id=run.run_id,
            expected_epoch=run.stop_epoch,
        )
        completed = self.store.complete_run(
            run_id=run.run_id,
            expected_epoch=run.stop_epoch,
            actual_tokens=100,
            evidence_object_uri="gs://evidence/run/execution.json",
            evidence_generation=7,
        )
        self.assertEqual(completed.state, "completed")
        self.assertEqual(completed.actual_tokens, 100)
        with self.assertRaises(TokenBudgetExceeded):
            self.reserve(2, tokens=500, policy=policy)

    def test_missing_usage_charges_full_reservation_and_completion_is_idempotent(
        self,
    ) -> None:
        run = self.reserve(tokens=600)
        self.store.mark_executing(
            run_id=run.run_id,
            expected_epoch=run.stop_epoch,
        )
        first = self.store.complete_run(
            run_id=run.run_id,
            expected_epoch=run.stop_epoch,
            actual_tokens=None,
            evidence_object_uri="gs://evidence/run/execution.json",
            evidence_generation=8,
        )
        second = self.store.complete_run(
            run_id=run.run_id,
            expected_epoch=run.stop_epoch,
            actual_tokens=None,
            evidence_object_uri="gs://evidence/run/execution.json",
            evidence_generation=8,
        )
        self.assertFalse(first.replayed)
        self.assertTrue(second.replayed)
        principal_day = self.store._usage[
            (
                "principal",
                self.principal,
                "day",
                run.day_window_start,
            )
        ]
        self.assertEqual(principal_day["reserved_tokens"], 600)
        self.assertEqual(principal_day["actual_tokens"], 600)

    def test_stop_epoch_change_blocks_late_completion(self) -> None:
        run = self.reserve()
        self.store.mark_executing(
            run_id=run.run_id,
            expected_epoch=run.stop_epoch,
        )
        self.store.activate_emergency_stop(
            actor_principal_id=self.principal,
            reason="Stop activated while the provider request was in flight.",
        )
        with self.assertRaises(EmergencyStopActive):
            self.store.complete_run(
                run_id=run.run_id,
                expected_epoch=run.stop_epoch,
                actual_tokens=50,
                evidence_object_uri="gs://evidence/run/execution.json",
                evidence_generation=9,
            )
        self.assertEqual(self.store.get_run(run.run_id).state, "executing")

    def test_decision_marker_requires_completed_run(self) -> None:
        run = self.reserve()
        with self.assertRaises(RunStateError):
            self.store.complete_decision(
                run_id=run.run_id,
                expected_epoch=run.stop_epoch,
                decision_event_id="AIGC-GEMINI-EVENT-decision-0001",
                decision_object_uri=(
                    f"gs://evidence/{run.run_id}/operator-decision.json"
                ),
                decision_generation=2,
            )
        self.assertIsNone(self.store.get_run(run.run_id).decision_event_id)

    def test_decision_marker_is_exactly_idempotent(self) -> None:
        run = self.complete()
        values = {
            "run_id": run.run_id,
            "expected_epoch": run.stop_epoch,
            "decision_event_id": "AIGC-GEMINI-EVENT-decision-0001",
            "decision_object_uri": (
                f"gs://evidence/{run.run_id}/operator-decision.json"
            ),
            "decision_generation": 2,
        }
        first = self.store.complete_decision(**values)
        second = self.store.complete_decision(**values)
        self.assertFalse(first.replayed)
        self.assertTrue(second.replayed)
        self.assertEqual(
            second.decision_event_id,
            "AIGC-GEMINI-EVENT-decision-0001",
        )
        self.assertEqual(second.decision_generation, 2)

    def test_decision_marker_conflict_cannot_replace_receipt(self) -> None:
        run = self.complete()
        first = self.store.complete_decision(
            run_id=run.run_id,
            decision_event_id="AIGC-GEMINI-EVENT-decision-0001",
            decision_object_uri=(
                f"gs://evidence/{run.run_id}/operator-decision.json"
            ),
            decision_generation=2,
        )
        with self.assertRaises(RunStateError):
            self.store.complete_decision(
                run_id=run.run_id,
                decision_event_id="AIGC-GEMINI-EVENT-decision-0002",
                decision_object_uri=first.decision_object_uri,
                decision_generation=first.decision_generation,
            )
        current = self.store.get_run(run.run_id)
        self.assertEqual(current.decision_event_id, first.decision_event_id)

    def test_concurrent_decision_markers_have_one_winner(self) -> None:
        run = self.complete()

        def mark_once(_index: int):
            return self.store.complete_decision(
                run_id=run.run_id,
                decision_event_id="AIGC-GEMINI-EVENT-decision-0001",
                decision_object_uri=(
                    f"gs://evidence/{run.run_id}/operator-decision.json"
                ),
                decision_generation=2,
            )

        with ThreadPoolExecutor(max_workers=12) as pool:
            markers = list(pool.map(mark_once, range(24)))
        self.assertEqual(sum(not item.replayed for item in markers), 1)
        self.assertEqual(sum(item.replayed for item in markers), 23)

    def test_stop_epoch_blocks_late_decision_marker(self) -> None:
        run = self.complete()
        self.store.activate_emergency_stop(
            actor_principal_id=self.principal,
            reason="Stop activated before decision receipt completion.",
        )
        with self.assertRaises(EmergencyStopActive):
            self.store.complete_decision(
                run_id=run.run_id,
                expected_epoch=run.stop_epoch,
                decision_event_id="AIGC-GEMINI-EVENT-decision-0001",
                decision_object_uri=(
                    f"gs://evidence/{run.run_id}/operator-decision.json"
                ),
                decision_generation=2,
            )
        self.assertIsNone(self.store.get_run(run.run_id).decision_event_id)

    def test_in_memory_decision_marker_accepts_receiptless_jsonl(self) -> None:
        run = self.complete()
        marked = self.store.complete_decision(
            run_id=run.run_id,
            decision_event_id="AIGC-GEMINI-EVENT-decision-local",
            decision_object_uri=None,
            decision_generation=None,
        )
        self.assertEqual(
            marked.decision_event_id,
            "AIGC-GEMINI-EVENT-decision-local",
        )
        self.assertIsNone(marked.decision_object_uri)
        self.assertIsNone(marked.decision_generation)

    def test_postgres_decision_marker_requires_durable_receipt(self) -> None:
        store = PostgresRuntimeControlStore(pool=None)
        with self.assertRaises(ValueError):
            store.complete_decision(
                run_id="AIGC-GEMINI-RUN-durable-receipt",
                decision_event_id="AIGC-GEMINI-EVENT-decision",
                decision_object_uri=None,
                decision_generation=None,
            )

    def test_terminal_failure_replays_without_new_reservation(self) -> None:
        run = self.reserve()
        failed = self.store.fail_run(
            run_id=run.run_id,
            state="failed",
            reason="Provider failed and the run remains non-retriable.",
        )
        replay = self.reserve()
        self.assertEqual(failed.state, "failed")
        self.assertEqual(replay.run_id, run.run_id)
        self.assertEqual(replay.state, "failed")
        self.assertTrue(replay.replayed)

    def test_unknown_run_get_fails_closed(self) -> None:
        with self.assertRaises(RunStateError):
            self.store.get_run("AIGC-GEMINI-RUN-unknown")

    def test_unavailable_control_store_blocks_every_transition(self) -> None:
        unavailable = UnavailableRuntimeControlStore("synthetic outage")
        with self.assertRaises(RuntimeControlUnavailable):
            unavailable.get_emergency_state()
        with self.assertRaises(RuntimeControlUnavailable):
            unavailable.get_run("AIGC-GEMINI-RUN-unknown")
        with self.assertRaises(RuntimeControlUnavailable):
            unavailable.reserve_run(
                principal_id=self.principal,
                idempotency_key=key(1),
                request_sha256=digest("request"),
                reserved_tokens=100,
                limits=limits(),
            )
        with self.assertRaises(RuntimeControlUnavailable):
            unavailable.complete_decision(
                run_id="AIGC-GEMINI-RUN-unknown",
                decision_event_id="AIGC-GEMINI-EVENT-decision",
                decision_object_uri=None,
                decision_generation=None,
            )

    def test_in_memory_health_cannot_be_claimed_as_durable(self) -> None:
        health = self.store.healthcheck()
        self.assertTrue(health.ok)
        self.assertFalse(health.durable)
        self.assertEqual(health.backend, "memory_test_only")

    def test_runtime_limits_reject_unbounded_or_inverted_configuration(self) -> None:
        with self.assertRaises(RuntimeLimitConfigurationError):
            RuntimeLimits(principal_runs_per_minute=0)
        with self.assertRaises(RuntimeLimitConfigurationError):
            RuntimeLimits(
                principal_runs_per_minute=5,
                global_runs_per_minute=4,
            )

    def test_postgres_migration_contains_required_constraints(self) -> None:
        migration = Path(
            "migrations/002_gemini_runtime_controls.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("gemini_runtime_control", migration)
        self.assertIn("gemini_run_reservations", migration)
        self.assertIn("gemini_usage_windows", migration)
        self.assertIn(
            "UNIQUE (principal_id, idempotency_key_sha256)",
            migration,
        )
        self.assertNotIn("idempotency_key VARCHAR", migration)
        self.assertIn("stop_epoch", migration)
        self.assertIn("evidence_missing", migration)
        self.assertIn("execution_event_id", migration)
        self.assertIn("decision_event_id", migration)
        self.assertIn("decision_object_uri", migration)
        self.assertIn("decision_generation", migration)
        self.assertIn("gemini_decision_receipt_complete", migration)
        self.assertIn("reserved_tokens", migration)
        self.assertIn("actual_tokens", migration)


if __name__ == "__main__":
    unittest.main()
