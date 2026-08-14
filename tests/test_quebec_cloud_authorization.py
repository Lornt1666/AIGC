from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from scripts.validate_quebec_cloud_authorization import (
    AuthorizationError,
    canonical_sha256,
    validate,
)
from scripts.verify_quebec_resource_locations import (
    RegionVerificationError,
    verify,
)

ROOT = Path(__file__).resolve().parents[1]
TEST_NOW = datetime(2026, 8, 6, 19, tzinfo=timezone.utc)


def template() -> dict:
    return json.loads(
        (
            ROOT / "config/quebec_staging_authorization.example.json"
        ).read_text(encoding="utf-8")
    )


def manifest() -> dict:
    return json.loads(
        (
            ROOT / "config/quebec_resource_manifest.example.json"
        ).read_text(encoding="utf-8")
    )


def _approval_phrase(payload: dict) -> str:
    return (
        "AUTHORIZE AIGC QUEBEC STAGING "
        f"PROJECT {payload['project_id']} "
        "REGION northamerica-northeast1 "
        f"RELEASE {payload['release_sha']} "
        f"RESOURCE-DIGEST {payload['resource_manifest_sha256']} "
        "MONTHLY-CEILING-CAD 200 NO-PUBLIC-TRAFFIC "
        "NO-LIVE-MODEL-CALL EXPIRES 2026-08-07T18:00:00Z"
    )


def authorized() -> dict:
    payload = template()
    project = "aigc-qc-stage-12345"
    payload.update(
        {
            "project_id": project,
            "project_number": "123456789012",
            "billing_account_id": "ABCDEF-123456-ABCDEF",
            "release_sha": "a" * 40,
            "release_tree_sha": "b" * 40,
            "resource_manifest_sha256": canonical_sha256(manifest()),
            "task_type": "canadian_staging_execution",
        }
    )
    payload["costs"].update(
        {
            "estimated_one_time": 0,
            "estimated_monthly": 175,
        }
    )
    payload["service_accounts"] = {
        name: (
            f"aigc-qc-{name.replace('_', '-')}@"
            f"{project}.iam.gserviceaccount.com"
        )
        for name in (
            "deployer",
            "cloud_build",
            "operator",
            "judge",
            "security_review",
        )
    }
    payload["exact_secret_version_refs"] = {
        name: (
            f"projects/{project}/locations/northamerica-northeast1/"
            f"secrets/{name}/versions/1"
        )
        for name in (
            "runtime_control_dsn",
            "operator_token",
            "operator_binding_key",
            "runtime_admin_token",
            "runtime_admin_binding_key",
            "judge_token",
            "judge_binding_key",
        )
    }
    for name in payload["reviews"]:
        payload["reviews"][name] = True
    payload["authority"].update(
        {
            "configuration_reviewed": True,
            "resource_creation_authorized": True,
            "staging_deployment_authorized": True,
            "authorized_by": "Justice Gray Maciocha",
            "authorized_at": "2026-08-06T18:00:00Z",
            "expires_at": "2026-08-07T18:00:00Z",
        }
    )
    payload["authority"]["approval_phrase"] = _approval_phrase(payload)
    return payload


def rebind_manifest(payload: dict, resource_manifest: dict) -> None:
    payload["resource_manifest_sha256"] = canonical_sha256(resource_manifest)
    payload["authority"]["approval_phrase"] = _approval_phrase(payload)


class AuthorizationTests(unittest.TestCase):
    def test_default_template_passes_plan_only(self) -> None:
        result = validate(template(), gate="plan")
        self.assertTrue(result["valid"])
        self.assertFalse(result["deployment_performed"])
        self.assertFalse(result["strict_quebec_data_residency_verified"])

    def test_plan_rejects_resource_authority(self) -> None:
        payload = template()
        payload["authority"]["resource_creation_authorized"] = True
        with self.assertRaises(AuthorizationError):
            validate(payload, gate="plan")

    def test_staging_authorization_passes_exact_packet(self) -> None:
        result = validate(
            authorized(),
            gate="staging",
            manifest=manifest(),
            now=TEST_NOW,
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["region"], "northamerica-northeast1")
        self.assertFalse(result["live_model_call_performed"])
        self.assertFalse(result["strict_quebec_data_residency_verified"])

    def test_staging_requires_exact_manifest(self) -> None:
        with self.assertRaises(AuthorizationError):
            validate(authorized(), gate="staging", now=TEST_NOW)

    def test_manifest_digest_mismatch_fails(self) -> None:
        changed = manifest()
        changed["resources"][0]["name"] = "changed-artifact-repository"
        with self.assertRaises(AuthorizationError):
            validate(
                authorized(),
                gate="staging",
                manifest=changed,
                now=TEST_NOW,
            )

    def test_non_quebec_region_fails(self) -> None:
        payload = authorized()
        payload["region"] = "northamerica-northeast2"
        with self.assertRaises(AuthorizationError):
            validate(payload, gate="staging", manifest=manifest(), now=TEST_NOW)

    def test_public_or_production_authority_fails(self) -> None:
        for field in (
            "public_access_authorized",
            "production_activation_authorized",
        ):
            payload = authorized()
            payload["authority"][field] = True
            with self.assertRaises(AuthorizationError):
                validate(
                    payload,
                    gate="staging",
                    manifest=manifest(),
                    now=TEST_NOW,
                )

    def test_latest_secret_alias_fails(self) -> None:
        payload = authorized()
        payload["exact_secret_version_refs"]["operator_token"] = (
            "projects/aigc-qc-stage-12345/"
            "locations/northamerica-northeast1/"
            "secrets/operator_token/versions/latest"
        )
        with self.assertRaises(AuthorizationError):
            validate(
                payload,
                gate="staging",
                manifest=manifest(),
                now=TEST_NOW,
            )

    def test_cost_over_ceiling_fails(self) -> None:
        payload = authorized()
        payload["costs"]["estimated_monthly"] = 201
        with self.assertRaises(AuthorizationError):
            validate(
                payload,
                gate="staging",
                manifest=manifest(),
                now=TEST_NOW,
            )

    def test_missing_residency_review_fails(self) -> None:
        for review in (
            "gemini_ml_processing_commitment_reviewed",
            "global_control_plane_metadata_reviewed",
        ):
            payload = authorized()
            payload["reviews"][review] = False
            with self.assertRaises(AuthorizationError):
                validate(
                    payload,
                    gate="staging",
                    manifest=manifest(),
                    now=TEST_NOW,
                )

    def test_wrong_approval_phrase_fails(self) -> None:
        payload = authorized()
        payload["authority"]["approval_phrase"] += " "
        with self.assertRaises(AuthorizationError):
            validate(
                payload,
                gate="staging",
                manifest=manifest(),
                now=TEST_NOW,
            )

    def test_resource_manifest_rejects_non_quebec_customer_content(self) -> None:
        payload = manifest()
        payload["resources"][0]["location"] = "us-central1"
        with self.assertRaises(RegionVerificationError):
            verify(payload)

    def test_control_plane_customer_content_is_rejected(self) -> None:
        payload = manifest()
        payload["control_plane_resources"][0]["customer_content"] = True
        with self.assertRaises(RegionVerificationError):
            verify(payload)

    def test_authorization_invokes_manifest_classification_gate(self) -> None:
        changed = manifest()
        changed["control_plane_resources"][0]["customer_content"] = True
        auth = authorized()
        rebind_manifest(auth, changed)
        with self.assertRaises(AuthorizationError):
            validate(
                auth,
                gate="staging",
                manifest=changed,
                now=TEST_NOW,
            )

    def test_resource_manifest_accepts_quebec_content_and_global_metadata(self) -> None:
        result = verify(manifest())
        self.assertEqual(
            result["non_quebec_customer_content_resources"],
            [],
        )
        self.assertTrue(result["customer_content_quebec_region_verified"])
        self.assertFalse(result["strict_quebec_data_residency_verified"])
        self.assertGreater(result["global_control_plane_resource_count"], 0)
        self.assertFalse(result["silent_failover_outside_canada"])


if __name__ == "__main__":
    unittest.main()
