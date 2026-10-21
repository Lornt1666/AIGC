import asyncio
import unittest

from next_steps_coordinator import (
    AUTO_ACTIONS, Coordinator, GateEvidence, PROHIBITED_ACTIONS,
)


SHA = "8f2dd00ff28fdca422396826f53e4b6c27bc6919"


class NextStepsCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def test_unknown_gates_fail_closed_and_generate_plan(self):
        evidence = GateEvidence(exact_commit=SHA, ci="PASS", artifact_binding="PASS",
                                specification="PASS")
        coordinator = Coordinator()
        report = coordinator.readiness(evidence)
        self.assertEqual(report["decision"], "BLOCK")
        self.assertFalse(report["release_eligible"])
        actions = {item["action"] for item in report["planned_actions"]}
        self.assertIn("analyze_gate_evidence", actions)
        self.assertIn("prepare_independent_review_packet", actions)

    def test_all_gates_pass_only_means_eligible_for_canonical_review(self):
        evidence = GateEvidence(exact_commit=SHA, ci="PASS", artifact_binding="PASS",
                                specification="PASS", security_review="PASS",
                                isolated_deployment="PASS", operational_acceptance="PASS",
                                human_acceptance="PASS", release_assurance="PASS")
        report = Coordinator().readiness(evidence)
        self.assertTrue(report["release_eligible"])
        self.assertEqual(report["decision"], "ELIGIBLE_FOR_CANONICAL_REVIEW")

    def test_invalid_sha_rejected(self):
        with self.assertRaises(ValueError):
            Coordinator().readiness(GateEvidence(exact_commit="main"))

    async def test_allowlisted_action_strips_authority_fields_and_audits(self):
        async def inspect(payload):
            return {"commit": payload["commit"], "approved": True,
                    "release_decision": "PASS", "deployment_authority": True}
        coordinator = Coordinator(handlers={"inspect_exact_head_ci": inspect})
        result = await coordinator.execute("inspect_exact_head_ci", {"commit": SHA})
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["result"], {"commit": SHA})
        self.assertEqual([e["event"] for e in coordinator.event_log],
                         ["ACTION_STARTED", "ACTION_COMPLETED"])
        self.assertEqual(coordinator.event_log[1]["previous_hash"],
                         coordinator.event_log[0]["event_hash"])

    async def test_unknown_and_privileged_actions_blocked(self):
        async def handler(payload): return {"ok": True}
        coordinator = Coordinator(handlers={name: handler for name in AUTO_ACTIONS})
        for action in ("merge", "deploy", "release", "self_approve",
                       "change_release_authority", "unknown_action"):
            with self.subTest(action=action):
                with self.assertRaises(PermissionError):
                    await coordinator.execute(action, {})
        self.assertEqual(len(coordinator.event_log), 6)
        self.assertTrue(all(e["event"] == "ACTION_BLOCKED" for e in coordinator.event_log))

    async def test_missing_handler_blocks(self):
        with self.assertRaises(PermissionError):
            await Coordinator().execute("inspect_exact_head_ci", {})

    async def test_handler_failure_is_audited_without_leaking_message(self):
        async def fail(payload): raise RuntimeError("sensitive payload should not be logged")
        coordinator = Coordinator(handlers={"run_reference_tests": fail})
        with self.assertRaises(RuntimeError):
            await coordinator.execute("run_reference_tests", {})
        event = coordinator.event_log[-1]
        self.assertEqual(event["event"], "ACTION_FAILED")
        self.assertNotIn("sensitive", str(event))

    async def test_handler_timeout_is_audited(self):
        async def slow(payload): await asyncio.sleep(0.1); return {"ok": True}
        coordinator = Coordinator(handlers={"run_reference_tests": slow})
        # The production default is 30s; replace wait_for for this test by an injected
        # slow action is not practical, so exercise timeout with a patched wait_for.
        original = asyncio.wait_for
        async def quick_timeout(awaitable, timeout):
            return await original(awaitable, timeout=0.001)
        asyncio.wait_for = quick_timeout
        try:
            with self.assertRaises(asyncio.TimeoutError):
                await coordinator.execute("run_reference_tests", {})
        finally:
            asyncio.wait_for = original
        self.assertEqual(coordinator.event_log[-1]["event"], "ACTION_TIMEOUT")


if __name__ == "__main__":
    unittest.main()
