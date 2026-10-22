import copy
import json
from pathlib import Path
import unittest

from scripts.validate_regenexcalibur_agent_registry import RegistryError, validate_registry


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "regenexcalibur_aigc_agent_registry.json"


class RegenExcaliburAgentRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_registry_is_valid_and_fail_closed(self):
        result = validate_registry(self.registry)
        self.assertEqual(result["status"], "VALID")
        self.assertEqual(result["agent_count"], 136)
        self.assertEqual(len(self.registry["operational_gate_contracts"]), 7)
        self.assertEqual(self.registry["final_decision_contract"]["canonical_decision_authority"], "RX-19")
        self.assertEqual(result["dependency_graph"], "ACYCLIC")
        self.assertEqual(result["default_disposition"], "BLOCK")
        self.assertEqual(result["production_authorization"], "NOT_GRANTED")

    def test_duplicate_agent_ids_block(self):
        data = copy.deepcopy(self.registry)
        data["agents"][1]["id"] = data["agents"][0]["id"]
        with self.assertRaisesRegex(RegistryError, "duplicate_agent_id"):
            validate_registry(data)

    def test_unknown_dependency_blocks(self):
        data = copy.deepcopy(self.registry)
        data["agents"][0]["dependencies"] = ["RX-DOES-NOT-EXIST"]
        with self.assertRaisesRegex(RegistryError, "unknown_dependency"):
            validate_registry(data)

    def test_dependency_cycle_blocks(self):
        data = copy.deepcopy(self.registry)
        data["agents"][0]["dependencies"] = ["RX-01"]
        with self.assertRaisesRegex(RegistryError, "dependency_cycle_detected"):
            validate_registry(data)

    def test_release_gate_agents_are_present_and_human_gates_are_reserved(self):
        result = validate_registry(self.registry)
        self.assertEqual(result["release_authority"], "RX-19")
        by_id = {agent["id"]: agent for agent in self.registry["agents"]}
        for agent_id in ("RX-21", "RX-22", "RX-23", "RX-24", "RX-25", "RX-26", "RX-27", "RX-28"):
            self.assertIn(agent_id, by_id)
            self.assertFalse(by_id[agent_id]["enabled"])
        self.assertEqual(by_id["RX-24"]["authority_tier"], "R4")
        self.assertEqual(by_id["RX-25"]["authority_tier"], "R4")
        self.assertEqual(by_id["RX-73"]["authority_tier"], "R0")
        self.assertEqual(by_id["RX-28"]["authority_tier"], "R0")
        self.assertIn("RX-19", by_id["RX-28"]["dependencies"])
        self.assertIn("BLOCK", by_id["RX-28"]["authority_boundary"])
        self.assertFalse(by_id["RX-28"]["enabled"])

    def test_operational_gate_contracts_fail_closed_and_bind_to_agents(self):
        data = copy.deepcopy(self.registry)
        self.assertEqual(len(data["operational_gate_contracts"]), 7)
        agent_ids = {agent["id"] for agent in data["agents"]}
        for gate in data["operational_gate_contracts"]:
            self.assertEqual(gate["failure_disposition"], "BLOCK")
            self.assertIn(gate["agent_id"], agent_ids)
        data["operational_gate_contracts"][2]["failure_disposition"] = "WARN"
        with self.assertRaisesRegex(RegistryError, "operational_gate_contract_weak_or_unbound"):
            validate_registry(data)

    def test_final_decision_cannot_be_reassigned_from_rx19(self):
        data = copy.deepcopy(self.registry)
        data["final_decision_contract"]["canonical_decision_authority"] = "RX-28"
        with self.assertRaisesRegex(RegistryError, "final_decision_authority_mismatch"):
            validate_registry(data)

    def test_new_assurance_agents_have_contracts_and_remain_disabled(self):
        by_id = {agent["id"]: agent for agent in self.registry["agents"]}
        contracts = {item["agent_id"]: item for item in self.registry["new_agent_contracts"]}
        for agent_id in ("RX-29", "RX-30", "RX-31", "RX-40", "RX-41", "RX-42", "RX-43", "RX-44", "RX-45", "RX-46", "RX-47", "RX-48", "RX-49", "RX-50", "RX-51", "RX-52", "RX-53", "RX-54", "RX-55", "RX-56", "RX-57", "RX-58", "RX-59", "RX-60", "RX-61", "RX-62", "RX-63", "RX-64", "RX-65", "RX-66", "RX-67", "RX-68", "RX-69", "RX-70", "RX-71", "RX-72", "RX-73", "RX-74", "RX-75", "RX-76", "RX-77", "RX-78", "RX-79", "RX-80", "RX-81", "RX-82", "RX-83", "RX-84", "RX-85", "RX-86", "RX-87", "RX-88", "RX-89", "RX-90", "RX-91", "RX-92", "RX-93", "RX-94", "RX-95", "RX-96", "RX-97", "RX-98", "RX-99", "RX-100", "RX-101", "RX-102", "RX-103", "RX-104", "RX-105", "RX-106", "RX-107", "RX-108", "RX-109", "RX-110", "RX-111", "RX-112", "RX-113", "RX-114", "RX-115", "RX-116", "RX-117", "RX-118", "RX-119", "RX-120", "RX-121", "RX-122", "RX-123", "RX-124", "RX-125", "RX-126", "RX-127", "RX-128", "RX-129", "RX-130", "RX-131", "RX-132", "RX-133", "RX-134", "RX-135", "RX-136", "RX-137", "RX-138"):
            self.assertIn(agent_id, by_id)
            self.assertIn(agent_id, contracts)
            self.assertFalse(by_id[agent_id]["enabled"])
            self.assertEqual(by_id[agent_id]["implementation_status"], "SPECIFIED_NOT_PRODUCTION_INTEGRATED")
            self.assertTrue(contracts[agent_id]["self_approval_prohibited"])
            self.assertTrue(contracts[agent_id]["human_approved_activation_required"])
            self.assertTrue(contracts[agent_id]["rollback_plan_required"])
            self.assertEqual(contracts[agent_id]["failure_disposition"], "BLOCK")


    def test_runtime_maturity_gates_are_ordered_and_fail_closed(self):
        runtime = self.registry["runtime_maturity_contract"]
        self.assertEqual(runtime["canonical_release_authority"], "RX-19")
        self.assertEqual([step["sequence"] for step in runtime["sequence"]], [1, 2, 3, 4, 5])
        self.assertEqual([step["gate_id"] for step in runtime["sequence"]], [
            "cryptographic_trust", "durability_and_concurrency",
            "tool_adapter_enforcement", "observability_and_evaluation",
            "independent_assurance",
        ])
        self.assertTrue(all(step["failure_disposition"] == "BLOCK" for step in runtime["sequence"]))
        self.assertFalse(runtime["production_authorization"])
        by_id = {agent["id"]: agent for agent in self.registry["agents"]}
        for agent_id in ("RX-121", "RX-122", "RX-123", "RX-124", "RX-125", "RX-126"):
            self.assertFalse(by_id[agent_id]["enabled"])
            self.assertEqual(by_id[agent_id]["authority_tier"], "R0")

    def test_runtime_gate_sequence_tampering_blocks(self):
        data = copy.deepcopy(self.registry)
        data["runtime_maturity_contract"]["sequence"][0]["sequence"] = 2
        with self.assertRaisesRegex(RegistryError, "runtime_maturity_sequence_invalid"):
            validate_registry(data)

    def test_runtime_agents_cannot_be_enabled_by_registry_edit(self):
        data = copy.deepcopy(self.registry)
        data["agents"][-1]["enabled"] = True
        with self.assertRaisesRegex(RegistryError, "new_registry_agents_must_default_disabled"):
            validate_registry(data)

    def test_handoff_coordinator_preserves_required_order_and_fail_closed_rules(self):
        contract = self.registry["handoff_coordination_contract"]
        self.assertEqual(contract["default_disposition"], "BLOCK")
        self.assertEqual(contract["canonical_release_authority"], "RX-19")
        self.assertEqual([step["sequence"] for step in contract["sequence"]], list(range(1, 9)))
        self.assertEqual([step["agent_id"] for step in contract["sequence"]], [
            "RX-53", "RX-54", "RX-55", "RX-50", "RX-56", "RX-49", "RX-51", "RX-52"
        ])
        self.assertTrue(contract["no_agent_self_approval"])
        self.assertTrue(contract["no_agent_may_assign_human_identity"])
        self.assertTrue(contract["no_agent_may_bypass_protection"])
        self.assertTrue(contract["no_agent_may_merge_or_authorize_release"])
        by_id = {agent["id"]: agent for agent in self.registry["agents"]}
        for agent_id in ("RX-53", "RX-54", "RX-55", "RX-56", "RX-57"):
            self.assertFalse(by_id[agent_id]["enabled"])
            self.assertEqual(by_id[agent_id]["implementation_status"], "SPECIFIED_NOT_PRODUCTION_INTEGRATED")

    def test_research_quality_contract_fails_closed(self):
        data = copy.deepcopy(self.registry)
        data["research_intelligence_contract"]["no_unsupported_compliance_claims"] = False
        with self.assertRaisesRegex(RegistryError, "research_intelligence_authority_boundary_weak"):
            validate_registry(data)
        data = copy.deepcopy(self.registry)
        data["research_intelligence_contract"]["research_quality_rules"] = []
        with self.assertRaisesRegex(RegistryError, "research_quality_rules_missing"):
            validate_registry(data)

    def test_lifecycle_statuses_are_distinct_and_production_is_not_authorized(self):
        lifecycle = self.registry["implementation_lifecycle"]
        self.assertEqual(lifecycle["operational_statuses"], [
            "SPECIFIED", "IMPLEMENTED", "TESTED", "INDEPENDENTLY_VERIFIED", "PRODUCTION_AUTHORIZED"
        ])
        self.assertEqual(lifecycle["default_operational_status"], "SPECIFIED")
        self.assertFalse(lifecycle["production_authorization_granted"])

    def test_incomplete_new_agent_contract_blocks(self):
        data = copy.deepcopy(self.registry)
        data["new_agent_contracts"][0]["tool_allowlist"] = []
        with self.assertRaisesRegex(RegistryError, "new_agent_contract_incomplete_or_unsafe"):
            validate_registry(data)

    def test_agents_must_remain_disabled_by_default(self):
        data = copy.deepcopy(self.registry)
        data["agents"][0]["enabled"] = True
        with self.assertRaisesRegex(RegistryError, "new_registry_agents_must_default_disabled"):
            validate_registry(data)

    def test_hash_only_or_self_approval_policy_blocks(self):
        data = copy.deepcopy(self.registry)
        data["acceptance_policy"]["no_hash_only_provenance_fallback"] = False
        with self.assertRaisesRegex(RegistryError, "acceptance_policy_weak_or_incomplete"):
            validate_registry(data)

    def test_second_release_authority_blocks(self):
        data = copy.deepcopy(self.registry)
        data["agents"][3]["authority_tier"] = "R4"
        data["agents"][3]["responsibility"] = "release approval"
        with self.assertRaisesRegex(RegistryError, "multiple_release_authorities"):
            validate_registry(data)

    def test_release_operations_agents_are_disabled_and_fail_closed(self):
        contract = self.registry["release_operations_assurance_contract"]
        self.assertEqual(contract["default_disposition"], "BLOCK")
        self.assertEqual(contract["canonical_release_authority"], "RX-19")
        self.assertFalse(contract["production_authorization"])
        by_id = {agent["id"]: agent for agent in self.registry["agents"]}
        contracts = {item["agent_id"]: item for item in self.registry["new_agent_contracts"]}
        for agent_id in ("RX-95", "RX-96", "RX-97", "RX-98", "RX-99", "RX-100", "RX-101", "RX-102"):
            self.assertIn(agent_id, by_id)
            self.assertIn(agent_id, contracts)
            self.assertEqual(by_id[agent_id]["authority_tier"], "R0")
            self.assertFalse(by_id[agent_id]["enabled"])
            self.assertEqual(by_id[agent_id]["implementation_status"], "SPECIFIED_NOT_PRODUCTION_INTEGRATED")
            self.assertTrue(contracts[agent_id]["self_approval_prohibited"])
            self.assertEqual(contracts[agent_id]["failure_disposition"], "BLOCK")


    def test_release_readiness_trigger_agents_are_disabled_and_fail_closed(self):
        contract = self.registry["release_readiness_trigger_contract"]
        self.assertEqual(contract["default_disposition"], "BLOCK")
        self.assertEqual(contract["canonical_release_authority"], "RX-19")
        self.assertEqual([step["sequence"] for step in contract["trigger_sequence"]], [1, 2, 3, 4])
        by_id = {agent["id"]: agent for agent in self.registry["agents"]}
        contracts = {item["agent_id"]: item for item in self.registry["new_agent_contracts"]}
        for agent_id in ("RX-135", "RX-136", "RX-137", "RX-138"):
            self.assertIn(agent_id, by_id)
            self.assertIn(agent_id, contracts)
            self.assertFalse(by_id[agent_id]["enabled"])
            self.assertEqual(by_id[agent_id]["authority_tier"], "R0")
            self.assertEqual(by_id[agent_id]["implementation_status"], "SPECIFIED_NOT_PRODUCTION_INTEGRATED")
            self.assertTrue(contracts[agent_id]["self_approval_prohibited"])
            self.assertTrue(contracts[agent_id]["human_approved_activation_required"])
            self.assertEqual(contracts[agent_id]["failure_disposition"], "BLOCK")

    def test_release_readiness_trigger_contract_tampering_blocks(self):
        data = copy.deepcopy(self.registry)
        data["release_readiness_trigger_contract"]["trigger_sequence"][0]["failure_disposition"] = "WARN"
        with self.assertRaisesRegex(RegistryError, "release_readiness_trigger_gate_weak_or_unbound"):
            validate_registry(data)
        data = copy.deepcopy(self.registry)
        data["release_readiness_trigger_contract"]["canonical_release_authority"] = "RX-138"
        with self.assertRaisesRegex(RegistryError, "release_readiness_trigger_contract_must_fail_closed"):
            validate_registry(data)

    def test_release_operations_authority_cannot_be_reassigned(self):
        data = copy.deepcopy(self.registry)
        data["release_operations_assurance_contract"]["canonical_release_authority"] = "RX-102"
        with self.assertRaisesRegex(RegistryError, "release_operations_contract_must_fail_closed"):
            validate_registry(data)


    def test_systems_excellence_agents_are_disabled_and_fail_closed(self):
        contract = self.registry["aigc_systems_excellence_contract"]
        self.assertEqual(contract["default_disposition"], "BLOCK")
        self.assertEqual(contract["canonical_release_authority"], "RX-19")
        self.assertFalse(contract["production_authorization"])
        by_id = {agent["id"]: agent for agent in self.registry["agents"]}
        contracts = {item["agent_id"]: item for item in self.registry["new_agent_contracts"]}
        for agent_id in ("RX-103", "RX-104", "RX-105", "RX-106", "RX-107", "RX-108", "RX-109", "RX-110", "RX-111", "RX-112", "RX-113", "RX-114", "RX-115", "RX-116", "RX-117", "RX-118", "RX-119", "RX-120"):
            self.assertIn(agent_id, by_id)
            self.assertIn(agent_id, contracts)
            self.assertEqual(by_id[agent_id]["authority_tier"], "R0")
            self.assertFalse(by_id[agent_id]["enabled"])
            self.assertEqual(by_id[agent_id]["implementation_status"], "SPECIFIED_NOT_PRODUCTION_INTEGRATED")
            self.assertTrue(contracts[agent_id]["self_approval_prohibited"])
            self.assertEqual(contracts[agent_id]["failure_disposition"], "BLOCK")

    def test_systems_excellence_cannot_reassign_release_authority(self):
        data = copy.deepcopy(self.registry)
        data["aigc_systems_excellence_contract"]["canonical_release_authority"] = "RX-103"
        with self.assertRaisesRegex(RegistryError, "systems_excellence_contract_must_fail_closed"):
            validate_registry(data)

    def test_systems_excellence_blocks_missing_control_evidence(self):
        data = copy.deepcopy(self.registry)
        data["aigc_systems_excellence_contract"]["required_test_classes"] = []
        with self.assertRaisesRegex(RegistryError, "systems_excellence_contract_incomplete"):
            validate_registry(data)

    def test_runtime_mishap_recovery_agents_are_disabled_and_sequence_is_ordered(self):
        result = validate_registry(self.registry)
        recovery = self.registry["runtime_mishap_recovery_contract"]
        self.assertEqual(result["agent_count"], 136)
        self.assertEqual(recovery["canonical_release_authority"], "RX-19")
        self.assertFalse(recovery["production_authorization"])
        self.assertEqual([step["sequence"] for step in recovery["operating_sequence"]], list(range(1, 9)))
        by_id = {agent["id"]: agent for agent in self.registry["agents"]}
        for agent_id in ("RX-127", "RX-128", "RX-129", "RX-130", "RX-131", "RX-132", "RX-133", "RX-134"):
            self.assertIn(agent_id, by_id)
            self.assertFalse(by_id[agent_id]["enabled"])
            self.assertEqual(by_id[agent_id]["authority_tier"], "R0")
            self.assertEqual(by_id[agent_id]["implementation_status"], "SPECIFIED_NOT_PRODUCTION_INTEGRATED")

    def test_override_agents_are_disabled_and_contract_is_fail_closed(self):
        result = validate_registry(self.registry)
        self.assertEqual(result["agent_count"], 136)
        contract = self.registry["agent_operations_override_contract"]
        self.assertEqual(contract["canonical_release_authority"], "RX-19")
        self.assertFalse(contract["production_authorization"])
        self.assertEqual(contract["execution_modes"], ["dry_run"])
        by_id = {agent["id"]: agent for agent in self.registry["agents"]}
        contracts = {item["agent_id"]: item for item in self.registry["new_agent_contracts"]}
        for agent_id in ("RX-139", "RX-140", "RX-141", "RX-142", "RX-143"):
            self.assertIn(agent_id, by_id)
            self.assertIn(agent_id, contracts)
            self.assertFalse(by_id[agent_id]["enabled"])
            self.assertEqual(by_id[agent_id]["authority_tier"], "R0")
            self.assertEqual(by_id[agent_id]["implementation_status"], "SPECIFIED_NOT_PRODUCTION_INTEGRATED")
            self.assertTrue(contracts[agent_id]["self_approval_prohibited"])
            self.assertEqual(contracts[agent_id]["failure_disposition"], "BLOCK")

    def test_override_cannot_be_promoted_or_weakened(self):
        data = copy.deepcopy(self.registry)
        data["agent_operations_override_contract"]["production_authorization"] = True
        with self.assertRaisesRegex(RegistryError, "agent_operations_override_must_remain_dry_run_only"):
            validate_registry(data)
        data = copy.deepcopy(self.registry)
        data["agent_operations_override_contract"]["prohibited_override_kinds"].remove("authorize_release")
        with self.assertRaisesRegex(RegistryError, "agent_operations_override_prohibited_operations_missing"):
            validate_registry(data)

    def test_runtime_mishap_recovery_tampering_blocks(self):
        data = copy.deepcopy(self.registry)
        data["runtime_mishap_recovery_contract"]["operating_sequence"][0]["failure_disposition"] = "WARN"
        with self.assertRaisesRegex(RegistryError, "runtime_mishap_recovery_gate_weak_or_unbound"):
            validate_registry(data)
        data = copy.deepcopy(self.registry)
        data["runtime_mishap_recovery_contract"]["canonical_release_authority"] = "RX-134"
        with self.assertRaisesRegex(RegistryError, "runtime_mishap_recovery_contract_must_fail_closed"):
            validate_registry(data)
        data = copy.deepcopy(self.registry)
        data["runtime_mishap_recovery_contract"]["production_authorization"] = True
        with self.assertRaisesRegex(RegistryError, "runtime_mishap_recovery_contract_incomplete"):
            validate_registry(data)



if __name__ == "__main__":
    unittest.main()
