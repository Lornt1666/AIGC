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
        self.assertEqual(result["agent_count"], 28)
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
        for agent_id in ("RX-21", "RX-22", "RX-23", "RX-24", "RX-25", "RX-26", "RX-27"):
            self.assertIn(agent_id, by_id)
            self.assertFalse(by_id[agent_id]["enabled"])
        self.assertEqual(by_id["RX-24"]["authority_tier"], "R4")
        self.assertEqual(by_id["RX-25"]["authority_tier"], "R4")

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


if __name__ == "__main__":
    unittest.main()
