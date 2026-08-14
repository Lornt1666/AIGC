from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.core.nexus.universal_integration import (
    RegistryValidationError,
    canonical_sha256,
    evaluate_registry,
    load_and_validate_registry,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "aigc_universal_integration_registry.v1.json"
SCHEMA = ROOT / "schemas" / "aigc_universal_integration_registry.schema.json"


def load_registry() -> dict:
    return load_and_validate_registry(REGISTRY, SCHEMA)


class UniversalIntegrationTests(unittest.TestCase):
    def test_registry_is_structurally_valid_and_truthfully_blocked(self) -> None:
        result = evaluate_registry(load_registry())
        self.assertFalse(result.production_ready)
        self.assertFalse(result.authority_granted)
        self.assertFalse(result.external_action_performed)
        self.assertIn("registry remains template_only", result.blockers)
        self.assertIn(
            "required surface chatgpt_mcp is implemented with 3/5 receipt-bound checks",
            result.blockers,
        )

    def test_hash_is_deterministic_and_order_independent(self) -> None:
        registry = load_registry()
        reordered = json.loads(json.dumps(registry, sort_keys=True))
        self.assertEqual(canonical_sha256(registry), canonical_sha256(reordered))

    def test_ninety_five_percent_threshold_cannot_hide_a_known_blocker(self) -> None:
        registry = load_registry()
        registry["completion_policy"]["minimum_verified_applicable_ratio"] = 0.0
        result = evaluate_registry(registry)
        self.assertFalse(result.production_ready)
        self.assertTrue(result.blockers)

    def test_receipt_count_without_verified_status_cannot_pass_surface(self) -> None:
        registry = load_registry()
        surface = next(item for item in registry["surfaces"] if item["id"] == "chatgpt_mcp")
        surface["evidence_receipts"] = {
            item: f"receipt-{index}"
            for index, item in enumerate(surface["required_evidence"])
        }
        result = evaluate_registry(registry)
        self.assertFalse(result.production_ready)
        self.assertIn(
            "required surface chatgpt_mcp is implemented with 5/5 receipt-bound checks",
            result.blockers,
        )

    def test_verified_status_without_complete_receipts_cannot_pass_surface(self) -> None:
        registry = load_registry()
        surface = next(item for item in registry["surfaces"] if item["id"] == "chatgpt_mcp")
        surface["status"] = "verified"
        surface["evidence_receipts"] = {
            surface["required_evidence"][0]: "one-receipt-is-not-the-five-required"
        }
        result = evaluate_registry(registry)
        self.assertFalse(result.production_ready)
        self.assertIn(
            "required surface chatgpt_mcp is verified with 1/5 receipt-bound checks",
            result.blockers,
        )

    def test_connector_requires_every_certification_dimension(self) -> None:
        registry = load_registry()
        connector = next(item for item in registry["connectors"] if item["id"] == "openai_responses")
        connector["status"] = "verified"
        connector["certification"].update(
            terms_reviewed=True,
            identity_bound=True,
            scope_bound=True,
            recovery_tested=True,
            live_receipt_ids=[],
        )
        result = evaluate_registry(registry)
        self.assertIn("required connector openai_responses is not fully certified", result.blockers)

    def test_authority_is_required_but_never_granted_by_evaluation(self) -> None:
        registry = load_registry()
        for key in registry["completion_policy"]["required_authorities"]:
            registry["authority"][key] = True
        result = evaluate_registry(registry)
        self.assertFalse(result.authority_granted)
        self.assertFalse(result.external_action_performed)

    def test_schema_rejects_subsystem_self_authority(self) -> None:
        registry = copy.deepcopy(load_registry())
        registry["subsystems"][0]["authority_granted"] = True
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid_registry.json"
            invalid.write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaises(RegistryValidationError):
                load_and_validate_registry(invalid, SCHEMA)


if __name__ == "__main__":
    unittest.main()
