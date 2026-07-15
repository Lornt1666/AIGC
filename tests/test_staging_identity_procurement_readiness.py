from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from src.core.staging_identity_procurement_readiness import (
    DISCOVERY_ACTIONS,
    REQUIRED_APIS,
    REQUIRED_PLAN_ACTIONS,
    StagingProcurementContractError,
    canonical_digest,
    evaluate_apply_authorization,
    evaluate_procurement_pack,
    evaluate_staging_procurement,
    strict_validate,
)

from tests.staging_procurement_test_helpers import (
    apply_authorization,
    discovery_authorization,
    discovery_evidence,
    final_submission,
    plan_authorization,
    plan_evidence,
    submission,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc)
REVISION = "a" * 40


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_template_validates_and_is_explicitly_non_live():
    pack = load("config/staging_identity_procurement_readiness_pack.json")
    strict_validate("staging_identity_procurement_readiness_pack", pack)
    result = evaluate_procurement_pack(pack)
    assert result["ready_for_operator_review"] is False
    assert "PACK_TEMPLATE_NOT_SUBMISSION" in result["reason_codes"]
    assert pack["status"] == "TARGET_SPECIFICATION"
    assert pack["verified_provider_state"]["workload_identity"]["key_status"] == "UNVERIFIED"
    assert pack["verified_provider_state"]["workload_identity"]["verified_user_managed_key_count"] is None
    assert pack["external_action_performed"] is False


def test_schema_accepts_phased_submission_and_fixes_template_submission_deadlock():
    pack = submission("DISCOVERY_READY_FOR_REVIEW")
    strict_validate("staging_identity_procurement_readiness_pack", pack)
    assert pack["artifact_kind"] == "SUBMISSION"
    assert pack["pack_id"] is not None
    assert pack["unresolved_requirements"]


def test_required_api_set_includes_service_usage_and_storage():
    assert "serviceusage.googleapis.com" in REQUIRED_APIS
    assert "storage.googleapis.com" in REQUIRED_APIS
    assert len(REQUIRED_APIS) == 8


def test_discovery_authorization_precedes_complete_provider_state():
    pack = submission("DISCOVERY_READY_FOR_REVIEW")
    auth = discovery_authorization(pack)
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        discovery_authorization_receipt=auth,
        evaluated_at=NOW,
    )
    assert result["target_specification_complete"] is True
    assert result["discovery_authorization_effective"] is True
    assert result["discovery_evidence_accepted"] is False
    assert result["ready_for_operator_review"] is False


def test_discovery_authorization_rejects_project_mismatch_and_mutation_scope():
    pack = submission("DISCOVERY_READY_FOR_REVIEW")
    auth = discovery_authorization(pack)
    auth["target_project_reference"] = "gcp_project://other-staging-001"
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        discovery_authorization_receipt=auth,
        evaluated_at=NOW,
    )
    assert result["discovery_authorization_effective"] is False
    assert "DISCOVERY_PROJECT_MISMATCH" in result["discovery_authorization_reason_codes"]

    bad = discovery_authorization(pack)
    bad["mutation_authorized"] = True
    with pytest.raises(StagingProcurementContractError):
        strict_validate("provider_discovery_authorization_receipt", bad)


def test_discovery_evidence_is_separate_external_read_evidence():
    pack = submission("DISCOVERY_EVIDENCE_ACCEPTED")
    auth = discovery_authorization(pack)
    evidence = discovery_evidence(pack, auth)
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        discovery_authorization_receipt=auth,
        discovery_evidence_receipt=evidence,
        evaluated_at=NOW,
    )
    assert result["discovery_authorization_effective"] is True
    assert result["discovery_evidence_accepted"] is True
    assert evidence["provider_read_performed"] is True
    assert evidence["mutation_performed"] is False
    assert evidence["secret_value_access_performed"] is False
    assert evidence["external_action_performed"] is True
    assert result["external_action_performed"] is False


def test_state_backend_plan_requires_accepted_discovery_evidence():
    pack = submission("STATE_BACKEND_PLAN_READY")
    auth = discovery_authorization(pack)
    plan = plan_authorization(pack, discovery=None, phase="STATE_BACKEND_BOOTSTRAP")
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        discovery_authorization_receipt=auth,
        plan_authorization_receipt=plan,
        evaluated_at=NOW,
    )
    assert result["plan_authorization_effective"] is False
    assert "DISCOVERY_EVIDENCE_NOT_ACCEPTED" in result["plan_authorization_reason_codes"]


def test_state_backend_plan_and_evidence_can_be_accepted_without_secret_versions():
    pack = submission("STATE_BACKEND_PLAN_READY")
    auth = discovery_authorization(pack)
    discovery = discovery_evidence(pack, auth)
    plan_auth = plan_authorization(pack, discovery, phase="STATE_BACKEND_BOOTSTRAP")
    plan = plan_evidence(pack, discovery, plan_auth, phase="STATE_BACKEND_BOOTSTRAP")
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        discovery_authorization_receipt=auth,
        discovery_evidence_receipt=discovery,
        plan_authorization_receipt=plan_auth,
        plan_evidence_receipt=plan,
        evaluated_at=NOW,
    )
    assert result["plan_authorization_effective"] is True
    assert result["plan_evidence_accepted"] is True
    assert plan["secret_references"] == []


def test_identity_plan_requires_verified_state_backend():
    pack = submission("IDENTITY_BOOTSTRAP_PLAN_READY")
    auth = discovery_authorization(pack)
    discovery = discovery_evidence(pack, auth)
    plan_auth = plan_authorization(pack, discovery, phase="IDENTITY_BOOTSTRAP")
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        discovery_authorization_receipt=auth,
        discovery_evidence_receipt=discovery,
        plan_authorization_receipt=plan_auth,
        evaluated_at=NOW,
    )
    assert result["plan_authorization_effective"] is False
    assert "STATE_BACKEND_NOT_BOOTSTRAPPED" in result["plan_authorization_reason_codes"]


def test_apply_authorization_is_exactly_bound_to_accepted_plan_evidence():
    pack = submission("STATE_BACKEND_PLAN_READY")
    auth = discovery_authorization(pack)
    discovery = discovery_evidence(pack, auth)
    plan_auth = plan_authorization(pack, discovery, phase="STATE_BACKEND_BOOTSTRAP")
    plan = plan_evidence(pack, discovery, plan_auth, phase="STATE_BACKEND_BOOTSTRAP")
    apply = apply_authorization(pack, discovery, plan_auth, plan)
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        discovery_authorization_receipt=auth,
        discovery_evidence_receipt=discovery,
        plan_authorization_receipt=plan_auth,
        plan_evidence_receipt=plan,
        apply_authorization_receipt=apply,
        evaluated_at=NOW,
    )
    assert result["apply_authorization_effective"] is True

    tampered = copy.deepcopy(apply)
    tampered["planned_resources"] = ["gcs_bucket://aigc-staging-001/wrong"]
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        discovery_authorization_receipt=auth,
        discovery_evidence_receipt=discovery,
        plan_authorization_receipt=plan_auth,
        plan_evidence_receipt=plan,
        apply_authorization_receipt=tampered,
        evaluated_at=NOW,
    )
    assert result["apply_authorization_effective"] is False
    assert "APPLY_RESOURCE_LIST_MISMATCH" in result["apply_authorization_reason_codes"]


def test_apply_compatibility_wrapper_never_bypasses_integrated_plan_evidence():
    pack = submission("STATE_BACKEND_PLAN_READY")
    discovery = discovery_evidence(pack, discovery_authorization(pack))
    plan_auth = plan_authorization(pack, discovery, phase="STATE_BACKEND_BOOTSTRAP")
    plan = plan_evidence(pack, discovery, plan_auth, phase="STATE_BACKEND_BOOTSTRAP")
    apply = apply_authorization(pack, discovery, plan_auth, plan)
    result = evaluate_apply_authorization(
        apply,
        exact_revision=REVISION,
        procurement_pack_digest=canonical_digest(pack),
        plan_artifact_digest=plan["plan_artifact_digest"],
        evaluated_at=NOW,
    )
    assert result["effective"] is False
    assert "INTEGRATED_PLAN_EVIDENCE_REQUIRED" in result["reason_codes"]


def test_consumed_phase_cannot_be_reused():
    pack = submission("STATE_BACKEND_PLAN_READY")
    pack["phase_consumption"]["state_backend_plan"] = {
        "status": "CONSUMED",
        "consumed_at": "2026-07-14T19:30:00+00:00",
        "consumed_by_receipt_id": "SPA-CONSUMED-0001",
    }
    auth = discovery_authorization(pack)
    discovery = discovery_evidence(pack, auth)
    plan_auth = plan_authorization(pack, discovery, phase="STATE_BACKEND_BOOTSTRAP")
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        discovery_authorization_receipt=auth,
        discovery_evidence_receipt=discovery,
        plan_authorization_receipt=plan_auth,
        evaluated_at=NOW,
    )
    assert result["plan_authorization_effective"] is False
    assert "PLAN_PHASE_ALREADY_CONSUMED" in result["plan_authorization_reason_codes"]


def test_final_verified_submission_can_reach_operator_review_without_issuing_receipt():
    pack = final_submission()
    strict_validate("staging_identity_procurement_readiness_pack", pack)
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        evaluated_at=NOW,
    )
    assert result["ready_for_operator_review"] is True
    assert result["final_readiness_reason_codes"] == []
    assert pack["authorization_receipt_issued"] is False
    assert pack["provider_action_performed"] is False
    assert pack["external_action_performed"] is False


def test_final_submission_rejects_unverified_or_nonzero_service_account_keys():
    pack = final_submission()
    pack["verified_provider_state"]["workload_identity"]["verified_user_managed_key_count"] = 1
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        evaluated_at=NOW,
    )
    assert result["ready_for_operator_review"] is False
    assert "USER_MANAGED_SERVICE_ACCOUNT_KEYS_PRESENT_OR_UNVERIFIED" in result["final_readiness_reason_codes"]


def test_final_submission_rejects_duplicate_oauth_and_session_secrets():
    pack = final_submission()
    pack["verified_provider_state"]["session_security"]["session_pepper_secret_reference"] = (
        pack["verified_provider_state"]["identity_provider"]["oauth_client_secret_reference"]
    )
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        evaluated_at=NOW,
    )
    assert result["ready_for_operator_review"] is False
    assert "OAUTH_AND_SESSION_SECRET_NOT_SEPARATE" in result["final_readiness_reason_codes"]


def test_final_submission_rejects_domain_origin_redirect_mismatch():
    pack = final_submission()
    pack["verified_provider_state"]["identity_provider"]["authorized_redirect_uri"] = (
        "https://other.example/callback"
    )
    result = evaluate_staging_procurement(
        procurement_pack=pack,
        exact_revision=REVISION,
        evaluated_at=NOW,
    )
    assert result["ready_for_operator_review"] is False
    assert "AUTHORIZED_DOMAIN_ORIGIN_REDIRECT_MISMATCH" in result["final_readiness_reason_codes"]


def test_all_new_contract_schemas_are_valid_draft_2020_12():
    for name in (
        "staging_identity_procurement_readiness_pack",
        "provider_discovery_authorization_receipt",
        "provider_discovery_evidence_receipt",
        "staging_plan_authorization_receipt",
        "staging_plan_evidence_receipt",
        "staging_apply_authorization_receipt",
        "staging_post_apply_operational_evidence",
        "staging_procurement_state_evaluation",
    ):
        schema = load(f"schemas/{name}.schema.json")
        jsonschema.Draft202012Validator.check_schema(schema)
