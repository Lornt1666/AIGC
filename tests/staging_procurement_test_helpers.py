from __future__ import annotations

import copy
import json
from pathlib import Path

from src.core.staging_identity_procurement_readiness import (
    DISCOVERY_ACTIONS,
    REQUIRED_APIS,
    REQUIRED_PLAN_ACTIONS,
    canonical_digest,
)

ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def submission(status: str):
    pack = copy.deepcopy(load("config/staging_identity_procurement_readiness_pack.json"))
    pack["artifact_kind"] = "SUBMISSION"
    pack["pack_id"] = "SIP-ABCDEFGHIJKLMNOPQRSTUVWX"
    pack["status"] = status
    previous_by_status = {
        "TARGET_SPECIFICATION": None,
        "DISCOVERY_READY_FOR_REVIEW": "TARGET_SPECIFICATION",
        "DISCOVERY_EVIDENCE_ACCEPTED": "DISCOVERY_READY_FOR_REVIEW",
        "STATE_BACKEND_PLAN_READY": "DISCOVERY_EVIDENCE_ACCEPTED",
        "STATE_BACKEND_BOOTSTRAPPED": "STATE_BACKEND_PLAN_READY",
        "IDENTITY_BOOTSTRAP_PLAN_READY": "STATE_BACKEND_BOOTSTRAPPED",
        "READY_FOR_OPERATOR_REVIEW": "IDENTITY_BOOTSTRAP_PLAN_READY",
        "SUPERSEDED": "TARGET_SPECIFICATION",
    }
    previous = previous_by_status[status]
    pack["transition"] = {
        "previous_status": previous,
        "transition_reason": None if previous is None else f"Advance to {status}.",
        "transition_evidence_digest": None if previous is None else "a" * 64,
    }
    pack["lifecycle"] = {
        "created_at": "2026-07-14T18:00:00+00:00",
        "expires_at": "2026-07-20T18:00:00+00:00",
        "supersedes_pack_id": None,
        "revoked": False,
        "revoked_at": None,
        "revocation_reason": None,
    }
    for phase in pack["phase_consumption"].values():
        phase["status"] = "UNUSED"
    target = pack["target_specification"]
    target.update(
        {
            "project_reference": "gcp_project://aigc-staging-001",
            "project_id": "aigc-staging-001",
            "proposed_wif_pool_id": "aigc-pool",
            "proposed_wif_provider_id": "aigc-provider",
            "proposed_plan_service_account_id": "aigc-plan-sa",
            "proposed_apply_service_account_id": "aigc-apply-sa",
            "proposed_runtime_service_account_id": "aigc-runtime-sa",
            "proposed_state_bucket_reference": "gcs_bucket://aigc-staging-001/aigc-staging-state",
            "proposed_staging_domain_reference": "dns_name://staging.aigc.example",
        }
    )
    return pack


def final_submission():
    pack = submission("READY_FOR_OPERATOR_REVIEW")
    provider = pack["verified_provider_state"]
    provider["project"].update(
        {
            "project_number": "123456789012",
            "billing_status": "VERIFIED_TRUE",
            "identity_platform_status": "VERIFIED_TRUE",
            "production_data_absent_status": "VERIFIED_TRUE",
            "enabled_api_service_names": sorted(REQUIRED_APIS),
        }
    )
    provider["workload_identity"].update(
        {
            "pool_reference": "gcp_wif_pool://123456789012/aigc-pool",
            "provider_reference": "gcp_wif_provider://123456789012/aigc-pool/aigc-provider",
            "plan_service_account_reference": "gcp_service_account://aigc-staging-001/aigc-plan-sa@aigc-staging-001.iam.gserviceaccount.com",
            "apply_service_account_reference": "gcp_service_account://aigc-staging-001/aigc-apply-sa@aigc-staging-001.iam.gserviceaccount.com",
            "runtime_service_account_reference": "gcp_service_account://aigc-staging-001/aigc-runtime-sa@aigc-staging-001.iam.gserviceaccount.com",
            "attribute_mapping_fingerprint": "1" * 64,
            "attribute_condition_fingerprint": "2" * 64,
            "key_status": "VERIFIED",
            "verified_user_managed_key_count": 0,
        }
    )
    provider["identity_provider"].update(
        {
            "google_oauth_web_client_id": "client-1234567890.apps.googleusercontent.com",
            "oauth_client_secret_reference": "gcp_secret://aigc-staging-001/aigc-google-oauth-client-secret/1",
            "oauth_consent_configuration_reference": "oauth_consent://aigc-staging-001/staging",
            "authorized_domain_reference": "dns_name://staging.aigc.example",
            "authorized_origin": "https://staging.aigc.example",
            "authorized_redirect_uri": "https://staging.aigc.example/auth/callback",
        }
    )
    provider["session_security"]["session_pepper_secret_reference"] = (
        "gcp_secret://aigc-staging-001/aigc-session-pepper/1"
    )
    provider["terraform_state"].update(
        {
            "bucket_reference": "gcs_bucket://aigc-staging-001/aigc-staging-state",
            "state_reference": "gcs_state://aigc-staging-001/aigc-staging-state/aigc/staging/default.tfstate",
            "bootstrap_status": "BOOTSTRAPPED_VERIFIED",
            "bucket_preexists_backend_init_status": "VERIFIED_TRUE",
            "uniform_bucket_level_access_status": "VERIFIED_TRUE",
            "public_access_prevention_status": "VERIFIED_TRUE",
            "object_versioning_status": "VERIFIED_TRUE",
            "retention_policy_days": 30,
            "state_locking_status": "VERIFIED_TRUE",
            "rollback_generation_reference": "gcs_generation://aigc-staging-state/123456",
        }
    )
    provider["test_subject"].update(
        {
            "reference": "staging_subject://operator-controlled-001",
            "operator_controlled_status": "VERIFIED_TRUE",
        }
    )
    provider["iam_separation"].update(
        {
            "bootstrap_administrator_reference": "principal://bootstrap-admin",
            "bootstrap_administrator_separate": True,
            "plan_apply_runtime_identities_distinct": True,
        }
    )
    pack["evidence_bindings"] = {
        "discovery_evidence_receipt_id": "SDE-FINAL-0001",
        "discovery_evidence_digest": "3" * 64,
        "state_backend_operational_evidence_receipt_id": "SOE-STATE-0001",
        "state_backend_operational_evidence_digest": "4" * 64,
        "identity_operational_evidence_receipt_id": "SOE-IDENTITY-0001",
        "identity_operational_evidence_digest": "5" * 64,
    }
    pack["unresolved_requirements"] = []
    return pack


def discovery_authorization(pack):
    return {
        "contract_id": "AIGC-PROVIDER-DISCOVERY-AUTHORIZATION-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "SDA-EXAMPLE-0001",
        "decision": "APPROVED",
        "reason_codes": [],
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "approved_by_name": "Justice Gray Maciocha",
        "exact_revision": REVISION,
        "procurement_pack_digest": canonical_digest(pack),
        "phase": "PROVIDER_DISCOVERY",
        "target_project_reference": pack["target_specification"]["project_reference"],
        "allowed_actions": sorted(DISCOVERY_ACTIONS),
        "issued_at": "2026-07-14T19:00:00+00:00",
        "expires_at": "2026-07-14T23:00:00+00:00",
        "single_use": True,
        "mutation_authorized": False,
        "secret_value_access_authorized": False,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "provider_action_performed": False,
        "external_action_performed": False,
    }


def discovery_evidence(pack, auth):
    return {
        "contract_id": "AIGC-PROVIDER-DISCOVERY-EVIDENCE-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "SDE-EXAMPLE-0001",
        "exact_revision": REVISION,
        "procurement_pack_digest": canonical_digest(pack),
        "discovery_authorization_receipt_id": auth["receipt_id"],
        "target_project_reference": pack["target_specification"]["project_reference"],
        "collected_at": "2026-07-14T19:30:00+00:00",
        "result": "SUCCESS",
        "review_status": "ACCEPTED",
        "observed_resources": [
            {
                "resource_type": "PROJECT",
                "target_reference": pack["target_specification"]["project_reference"],
                "existence_status": "EXISTS",
                "evidence_digest": "6" * 64,
            }
        ],
        "enabled_api_service_names": [],
        "service_account_key_counts": [],
        "identity_platform_configuration_status": "UNCONFIGURED",
        "state_backend_status": "MISSING",
        "unresolved_requirements": ["state_backend", "identity_bootstrap"],
        "raw_secret_values_present": False,
        "mutation_performed": False,
        "secret_value_access_performed": False,
        "provider_read_performed": True,
        "external_action_performed": True,
    }


def plan_authorization(pack, discovery, phase):
    discovery_id = discovery["receipt_id"] if discovery else "SDE-MISSING-0001"
    discovery_digest = canonical_digest(discovery) if discovery else "7" * 64
    return {
        "contract_id": "AIGC-STAGING-PLAN-AUTHORIZATION-RECEIPT-001",
        "contract_version": "1.1.0",
        "receipt_id": "SPA-EXAMPLE-0001",
        "decision": "APPROVED",
        "reason_codes": [],
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "approved_by_name": "Justice Gray Maciocha",
        "exact_revision": REVISION,
        "procurement_pack_digest": canonical_digest(pack),
        "phase": phase,
        "target_project_reference": pack["target_specification"]["project_reference"],
        "discovery_evidence_receipt_id": discovery_id,
        "discovery_evidence_digest": discovery_digest,
        "issued_at": "2026-07-14T19:35:00+00:00",
        "expires_at": "2026-07-14T23:35:00+00:00",
        "allowed_actions": sorted(REQUIRED_PLAN_ACTIONS),
        "single_use": True,
        "mutation_authorized": False,
        "terraform_apply_authorized": False,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "provider_action_performed": False,
        "terraform_plan_performed": False,
        "external_action_performed": False,
    }


def plan_evidence(pack, discovery, plan_auth, phase):
    state_bucket = pack["target_specification"]["proposed_state_bucket_reference"]
    return {
        "contract_id": "AIGC-STAGING-PLAN-EVIDENCE-RECEIPT-001",
        "contract_version": "1.0.0",
        "receipt_id": "SPE-EXAMPLE-0001",
        "exact_revision": REVISION,
        "procurement_pack_digest": canonical_digest(pack),
        "phase": phase,
        "target_project_reference": pack["target_specification"]["project_reference"],
        "discovery_evidence_receipt_id": discovery["receipt_id"],
        "discovery_evidence_digest": canonical_digest(discovery),
        "plan_authorization_receipt_id": plan_auth["receipt_id"],
        "generated_at": "2026-07-14T19:45:00+00:00",
        "plan_result": "SUCCESS",
        "review_status": "ACCEPTED",
        "plan_artifact_digest": "sha256:" + "8" * 64,
        "planned_resources": [state_bucket],
        "planned_iam_delta": [],
        "authorized_origins": [],
        "authorized_redirect_uris": [],
        "secret_references": [],
        "raw_secret_values_present": False,
        "provider_mutation_performed": False,
        "terraform_plan_performed": True,
        "terraform_apply_performed": False,
        "external_action_performed": True,
    }


def apply_authorization(pack, discovery, plan_auth, plan):
    return {
        "contract_id": "AIGC-STAGING-APPLY-AUTHORIZATION-RECEIPT-001",
        "contract_version": "1.1.0",
        "receipt_id": "SAA-EXAMPLE-0001",
        "decision": "APPROVED",
        "reason_codes": [],
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "approved_by_name": "Justice Gray Maciocha",
        "exact_revision": REVISION,
        "procurement_pack_digest": canonical_digest(pack),
        "phase": plan["phase"],
        "target_project_reference": pack["target_specification"]["project_reference"],
        "discovery_evidence_receipt_id": discovery["receipt_id"],
        "discovery_evidence_digest": canonical_digest(discovery),
        "plan_authorization_receipt_id": plan_auth["receipt_id"],
        "plan_evidence_receipt_id": plan["receipt_id"],
        "plan_evidence_digest": canonical_digest(plan),
        "plan_artifact_digest": plan["plan_artifact_digest"],
        "issued_at": "2026-07-14T19:50:00+00:00",
        "expires_at": "2026-07-14T20:50:00+00:00",
        "planned_resources": plan["planned_resources"],
        "planned_iam_delta": plan["planned_iam_delta"],
        "authorized_origins": plan["authorized_origins"],
        "authorized_redirect_uris": plan["authorized_redirect_uris"],
        "secret_references": plan["secret_references"],
        "rollback_instructions_digest": "9" * 64,
        "single_use": True,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "provider_mutation_authorized": True,
        "terraform_apply_authorized": True,
        "production_identity_activation_authorized": False,
        "production_deployment_authorized": False,
        "provider_action_performed": False,
        "terraform_apply_performed": False,
        "external_action_performed": False,
    }
