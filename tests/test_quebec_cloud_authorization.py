from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from scripts.validate_quebec_cloud_authorization import (
    AuthorizationError,
    authorization_inventory,
    canonical_sha256,
    validate,
)
from scripts.verify_quebec_resource_locations import (
    RegionVerificationError,
    verify,
)

ROOT = Path(__file__).resolve().parents[1]
TEST_NOW = datetime(2026, 8, 6, 19, tzinfo=timezone.utc)
PREFIX = "aigc-qc"


def exact_supply_chain() -> dict[str, str]:
    return {
        "docker_builder_image": "gcr.io/cloud-builders/docker@sha256:" + "c" * 64,
        "python_base_image": "python:3.12.13-slim-bookworm@sha256:" + "d" * 64,
        "sbom_generator_image": "anchore/syft@sha256:" + "e" * 64,
    }


def exact_resources(project: str) -> dict[str, str]:
    return {
        "artifact_registry_repository": f"{PREFIX}-runtime",
        "operator_service": f"{PREFIX}-operator",
        "judge_service": f"{PREFIX}-judge",
        "cloud_sql_instance": f"{PREFIX}-control",
        "database_name": "aigc_control",
        "evidence_bucket": f"{project}-{PREFIX}-evidence",
        "judge_bucket": f"{project}-{PREFIX}-judge",
        "receipt_bucket": f"{project}-{PREFIX}-receipts",
        "build_source_bucket": f"{project}-{PREFIX}-build-source",
        "log_bucket": f"{PREFIX}-logs",
        "kms_key_ring": f"{PREFIX}-keys",
    }


def exact_accounts(project: str) -> dict[str, str]:
    return {
        role: f"{PREFIX}-{suffix}@{project}.iam.gserviceaccount.com"
        for role, suffix in {
            "deployer": "deployer",
            "cloud_build": "build",
            "operator": "operator",
            "canary_gemini": "can-gem",
            "canary_openai": "can-oai",
            "canary_provisioner": "can-prov",
            "canary_binder": "can-bind",
            "canary_executor": "can-exec",
            "canary_publisher": "can-pub",
            "judge": "judge",
            "security_review": "security",
            "authority_signer": "signer",
        }.items()
    }


def exact_refs(project: str) -> dict[str, str]:
    suffixes = {
        "runtime_control_dsn": "runtime-control-dsn",
        "operator_token": "operator-token",
        "operator_binding_key": "operator-binding-key",
        "runtime_admin_token": "runtime-admin-token",
        "runtime_admin_binding_key": "runtime-admin-binding-key",
        "judge_token": "judge-token",
        "judge_binding_key": "judge-binding-key",
    }
    return {
        purpose: (
            f"projects/{project}/locations/northamerica-northeast1/"
            f"secrets/{PREFIX}-{suffix}/versions/1"
        )
        for purpose, suffix in suffixes.items()
    }


def template() -> dict:
    return json.loads(
        (
            ROOT / "config/quebec_staging_authorization.example.json"
        ).read_text(encoding="utf-8")
    )


def manifest() -> dict:
    value = json.loads(
        (
            ROOT / "config/quebec_resource_manifest.example.json"
        ).read_text(encoding="utf-8")
    )
    project = "aigc-qc-stage-12345"
    value["project_id"] = project
    value["project_number"] = "123456789012"
    value["resource_prefix"] = PREFIX
    replacements = {
        "placeholder_artifact_repository": f"{PREFIX}-runtime",
        "placeholder_sql_instance": f"{PREFIX}-control",
        "placeholder_operator_service": f"{PREFIX}-operator",
        "placeholder_judge_service": f"{PREFIX}-judge",
        "placeholder_evidence_bucket": f"{project}-{PREFIX}-evidence",
        "placeholder_judge_bucket": f"{project}-{PREFIX}-judge",
        "placeholder_receipt_bucket": f"{project}-{PREFIX}-receipts",
        "placeholder_build_source_bucket": f"{project}-{PREFIX}-build-source",
        "placeholder_secret_set": f"{PREFIX}-secret-set",
        "placeholder_kms_key_ring": f"{PREFIX}-keys",
        "placeholder_log_bucket": f"{PREFIX}-logs",
    }
    for item in value["resources"]:
        item["name"] = replacements.get(item["name"], item["name"])
    control_replacements = {
        "placeholder_project_id": project,
        "placeholder_identity_control_plane": f"{PREFIX}-gha",
        "placeholder_billing_control_plane": "ABCDEF-123456-ABCDEF",
        "placeholder_vpc_network": f"{PREFIX}-vpc",
        "placeholder_private_service_peering": f"{PREFIX}-private-services",
    }
    for item in value["control_plane_resources"]:
        item["name"] = control_replacements.get(item["name"], item["name"])
    return value


def _approval_phrase(payload: dict) -> str:
    return (
        "AUTHORIZE AIGC QUEBEC STAGING "
        f"PROJECT {payload['project_id']} "
        "REGION northamerica-northeast1 "
        f"RELEASE {payload['release_sha']} "
        f"RESOURCE-DIGEST {payload['resource_manifest_sha256']} "
        f"INVENTORY-DIGEST {payload['authorization_inventory_sha256']} "
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
            "resource_prefix": PREFIX,
            "billing_account_id": "ABCDEF-123456-ABCDEF",
            "release_sha": "a" * 40,
            "release_tree_sha": "b" * 40,
            "resource_manifest_sha256": canonical_sha256(manifest()),
            "ci_admission_sha256": "7" * 64,
            "task_type": "canadian_staging_execution",
        }
    )
    payload["costs"].update(
        {
            "estimated_one_time": 0,
            "estimated_monthly": 175,
        }
    )
    payload["resources"] = exact_resources(project)
    payload["service_accounts"] = exact_accounts(project)
    payload["exact_secret_version_refs"] = exact_refs(project)
    payload["supply_chain"] = exact_supply_chain()
    bound_manifest = manifest()
    bound_manifest["authorization_bindings"] = {
        "resources": deepcopy(payload["resources"]),
        "service_accounts": deepcopy(payload["service_accounts"]),
        "exact_secret_version_refs": deepcopy(payload["exact_secret_version_refs"]),
    }
    payload["resource_manifest_sha256"] = canonical_sha256(bound_manifest)
    payload["authorization_inventory_sha256"] = canonical_sha256(
        authorization_inventory(payload)
    )
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
    resource_manifest["authorization_bindings"] = {
        "resources": deepcopy(payload["resources"]),
        "service_accounts": deepcopy(payload["service_accounts"]),
        "exact_secret_version_refs": deepcopy(payload["exact_secret_version_refs"]),
    }
    payload["resource_manifest_sha256"] = canonical_sha256(resource_manifest)
    payload["authorization_inventory_sha256"] = canonical_sha256(
        authorization_inventory(payload)
    )
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
        payload = authorized()
        resource_manifest = manifest()
        rebind_manifest(payload, resource_manifest)
        result = validate(
            payload,
            gate="staging",
            manifest=resource_manifest,
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

    def test_project_resource_identity_and_secret_scope_substitution_fails(self) -> None:
        for field, changed in (
            ("resources", {"operator_service": "attacker-service"}),
            ("service_accounts", {"operator": "attacker-operator@aigc-qc-stage-12345.iam.gserviceaccount.com"}),
            ("exact_secret_version_refs", {"operator_token": "projects/aigc-qc-stage-12345/locations/northamerica-northeast1/secrets/attacker/versions/9"}),
        ):
            payload = authorized()
            resource_manifest = manifest()
            rebind_manifest(payload, resource_manifest)
            payload[field].update(changed)
            payload["authorization_inventory_sha256"] = canonical_sha256(
                authorization_inventory(payload)
            )
            payload["authority"]["approval_phrase"] = _approval_phrase(payload)
            with self.assertRaisesRegex(
                AuthorizationError, "deterministic|authorization_bindings|numeric Montréal"
            ):
                validate(payload, gate="staging", manifest=resource_manifest, now=TEST_NOW)

    def test_manifest_project_substitution_fails_even_with_rebound_digest(self) -> None:
        payload = authorized()
        resource_manifest = manifest()
        rebind_manifest(payload, resource_manifest)
        resource_manifest["project_id"] = "different-project-12345"
        payload["resource_manifest_sha256"] = canonical_sha256(resource_manifest)
        payload["authority"]["approval_phrase"] = _approval_phrase(payload)
        with self.assertRaisesRegex(AuthorizationError, "project_id"):
            validate(payload, gate="staging", manifest=resource_manifest, now=TEST_NOW)

    def test_rebinding_both_packet_and_manifest_cannot_change_inventory(self) -> None:
        for field, key, value in (
            ("resources", "operator_service", "attacker-service"),
            (
                "service_accounts",
                "operator",
                "attacker-operator@aigc-qc-stage-12345.iam.gserviceaccount.com",
            ),
            (
                "exact_secret_version_refs",
                "operator_token",
                "projects/aigc-qc-stage-12345/locations/"
                "northamerica-northeast1/secrets/attacker/versions/9",
            ),
        ):
            payload = authorized()
            payload[field][key] = value
            resource_manifest = manifest()
            rebind_manifest(payload, resource_manifest)
            with self.assertRaisesRegex(
                AuthorizationError, "deterministic|numeric Montréal"
            ):
                validate(
                    payload,
                    gate="staging",
                    manifest=resource_manifest,
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
