from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ControlPlaneMetadataTests(unittest.TestCase):
    def test_global_control_plane_is_explicit_and_contains_no_customer_content(self) -> None:
        manifest = json.loads(
            (
                ROOT / "config/quebec_resource_manifest.example.json"
            ).read_text(encoding="utf-8")
        )
        control_plane = manifest["control_plane_resources"]
        self.assertGreater(len(control_plane), 0)
        for item in control_plane:
            self.assertEqual(item["location"], "global")
            self.assertEqual(
                item["classification"],
                "CONTROL_PLANE_METADATA",
            )
            self.assertIs(item["customer_content"], False)
            self.assertEqual(
                item["residency_status"],
                "VERIFIED_WITH_LIMITATION",
            )
        self.assertIs(
            manifest["strict_quebec_data_residency_verified"],
            False,
        )

    def test_customer_content_resources_are_montreal_only(self) -> None:
        manifest = json.loads(
            (
                ROOT / "config/quebec_resource_manifest.example.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(
            all(
                item["location"]
                in {
                    "northamerica-northeast1",
                    "NORTHAMERICA-NORTHEAST1",
                }
                for item in manifest["resources"]
            )
        )

    def test_billing_and_resource_manager_apis_are_default_deny_gated(self) -> None:
        text = (
            ROOT / "infra/gcp/quebec/platform_apis.tf"
        ).read_text(encoding="utf-8")
        self.assertIn("billingbudgets.googleapis.com", text)
        self.assertIn("cloudresourcemanager.googleapis.com", text)
        self.assertIn("local.create_resources", text)
        self.assertIn("disable_on_destroy = false", text)

    def test_resource_manifest_schema_preserves_truth_boundary(self) -> None:
        schema = json.loads(
            (
                ROOT / "schemas/quebec_resource_manifest.schema.json"
            ).read_text(encoding="utf-8")
        )
        properties = schema["properties"]
        control = properties["control_plane_resources"]["items"][
            "properties"
        ]
        self.assertEqual(control["location"]["const"], "global")
        self.assertEqual(
            control["classification"]["const"],
            "CONTROL_PLANE_METADATA",
        )
        self.assertIs(control["customer_content"]["const"], False)
        self.assertIs(
            properties["strict_quebec_data_residency_verified"]["const"],
            False,
        )

    def test_documentation_discloses_global_metadata_limitation(self) -> None:
        text = (
            ROOT / "docs/cloud/QUEBEC_CLOUD_FOUNDATION.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Control-plane metadata", text)
        self.assertIn("Strict Québec residency", text)


if __name__ == "__main__":
    unittest.main()
