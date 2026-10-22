import copy
import unittest

from aigc_runtime.agent_operations import plan_agent_operation


SHA = "a" * 40
TASK_DIGEST = "sha256:" + "b" * 64


def fixture_registry():
    return {
        "agents": [
            {"id": "RX-01", "dependencies": [], "authority_tier": "R0", "enabled": False},
            {"id": "RX-02", "dependencies": ["RX-01"], "authority_tier": "R0", "enabled": False},
        ]
    }


def request(**overrides):
    value = {
        "request_id": "dryrun-001",
        "mode": "dry_run",
        "operation": "run_allowlisted_agent",
        "target_agent_id": "RX-02",
        "source_commit_sha": SHA,
        "policy_version": "policy-test-v1",
        "task_contract_digest": TASK_DIGEST,
    }
    value.update(overrides)
    return value


class AgentOperationsTests(unittest.TestCase):
    def test_creates_deterministic_dependency_ordered_dry_run_plan(self):
        registry = fixture_registry()
        first = plan_agent_operation(registry, request())
        second = plan_agent_operation(registry, request())
        self.assertEqual(first["status"], "DRY_RUN_PLAN")
        self.assertEqual(first["dependency_order"], ["RX-01", "RX-02"])
        self.assertEqual(first["plan_digest"], second["plan_digest"])
        self.assertFalse(first["side_effects_performed"])
        self.assertFalse(first["dispatchable_in_production"])
        self.assertFalse(first["production_authorization"])

    def test_production_execution_is_blocked_even_when_requested(self):
        result = plan_agent_operation(fixture_registry(), request(mode="execute"))
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["reason"], "production_execution_not_implemented")
        self.assertFalse(result["side_effects_performed"])

    def test_non_overridable_security_and_release_invariants_block(self):
        for operation in ("override_release_gate", "disable_repository_protection",
                          "skip_required_ci", "self_enable_agent", "elevate_authority",
                          "manufacture_acceptance", "forge_evidence", "merge", "deploy",
                          "authorize_release"):
            with self.subTest(operation=operation):
                result = plan_agent_operation(fixture_registry(), request(operation=operation))
                self.assertEqual(result["status"], "BLOCK")
                self.assertEqual(result["reason"], "non_overridable_security_or_release_invariant")

    def test_retry_requires_side_effect_reconciliation(self):
        blocked = plan_agent_operation(
            fixture_registry(), request(operation="retry_after_side_effect_reconciliation")
        )
        self.assertEqual(blocked["reason"], "side_effect_outcome_must_be_reconciled_before_retry")
        allowed = plan_agent_operation(
            fixture_registry(), request(operation="retry_after_side_effect_reconciliation"),
            side_effect_reconciled=True,
        )
        self.assertEqual(allowed["status"], "DRY_RUN_PLAN")

    def test_kill_switch_preempts_planning(self):
        result = plan_agent_operation(fixture_registry(), request(), kill_switch_engaged=True)
        self.assertEqual(result["reason"], "global_kill_switch_engaged")

    def test_unknown_target_and_invalid_bindings_block(self):
        self.assertEqual(
            plan_agent_operation(fixture_registry(), request(target_agent_id="RX-99"))["reason"],
            "target_agent_not_in_registry",
        )
        self.assertEqual(
            plan_agent_operation(fixture_registry(), request(source_commit_sha="bad"))["reason"],
            "source_commit_sha_invalid",
        )
        self.assertEqual(
            plan_agent_operation(fixture_registry(), request(task_contract_digest="bad"))["reason"],
            "task_contract_digest_invalid",
        )

    def test_dependency_cycles_and_missing_dependencies_block(self):
        registry = fixture_registry()
        registry["agents"][0]["dependencies"] = ["RX-02"]
        self.assertEqual(
            plan_agent_operation(registry, request())["reason"],
            "dependency_cycle:RX-02",
        )
        registry = fixture_registry()
        registry["agents"][0]["dependencies"] = ["RX-404"]
        self.assertEqual(
            plan_agent_operation(registry, request())["reason"],
            "dependency_not_in_registry:RX-404",
        )

    def test_registry_input_is_not_mutated(self):
        registry = fixture_registry()
        before = copy.deepcopy(registry)
        plan_agent_operation(registry, request())
        self.assertEqual(registry, before)


if __name__ == "__main__":
    unittest.main()
