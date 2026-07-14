from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.core.staging_identity_procurement import canonical_digest,evaluate_staging_identity_procurement,load_procurement_pack

REVISION="a"*40
NOW=datetime(2026,7,14,18,30,tzinfo=timezone.utc)
APIS=["cloudresourcemanager.googleapis.com","iam.googleapis.com","iamcredentials.googleapis.com","identitytoolkit.googleapis.com","secretmanager.googleapis.com","serviceusage.googleapis.com","storage.googleapis.com","sts.googleapis.com"]

def validator(name):
    schema=json.loads((ROOT/"schemas"/f"{name}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema,format_checker=FormatChecker())

def resolved_pack(phase="STATE_BACKEND_BOOTSTRAP"):
    state={"bucket_reference":"gcs_bucket://aigc-stage-123/aigc-stage-tf-state","state_reference":"gcs_state://aigc-stage-123/aigc-stage-tf-state/aigc/staging/default.tfstate","bootstrap_status":"READY_FOR_BOOTSTRAP_PLAN","bucket_preexists_backend_init_attestation":"VERIFIED_FALSE","uniform_bucket_level_access_attestation":"UNVERIFIED","public_access_prevention_attestation":"UNVERIFIED","object_versioning_attestation":"UNVERIFIED","retention_policy_days":30,"state_locking_attestation":"UNVERIFIED","rollback_generation_reference":None}
    if phase=="STAGING_IDENTITY_CONFIGURATION": state.update({"bootstrap_status":"BOOTSTRAPPED_VERIFIED","bucket_preexists_backend_init_attestation":"VERIFIED_TRUE","uniform_bucket_level_access_attestation":"VERIFIED_TRUE","public_access_prevention_attestation":"VERIFIED_TRUE","object_versioning_attestation":"VERIFIED_TRUE","state_locking_attestation":"VERIFIED_TRUE","rollback_generation_reference":"gcs_generation://aigc-stage-123/aigc-stage-tf-state/aigc/staging/default.tfstate/101"})
    return {
      "contract_id":"AIGC-STAGING-IDENTITY-PROCUREMENT-READINESS-PACK-001","contract_version":"1.0.0","artifact_kind":"SUBMISSION","template_id":"SIPT-STAGING-IDENTITY-PROCUREMENT-V1","pack_id":"SIP-"+"A"*24,"status":"READY_FOR_PLAN_REVIEW","requested_plan_phase":phase,
      "lifecycle":{"created_at":"2026-07-14T18:00:00+00:00","expires_at":"2026-07-18T18:00:00+00:00","supersedes_pack_id":None,"revoked":False,"revoked_at":None,"revocation_reason":None},
      "project":{"project_reference":"gcp_project://aigc-stage-123","project_id":"aigc-stage-123","project_number":"123456789012","billing_enabled_attestation":"VERIFIED_ENABLED","identity_platform_enabled_attestation":"VERIFIED_ENABLED","required_api_service_names":list(APIS),"enabled_api_service_names":list(APIS),"production_data_absent_attestation":"VERIFIED_ABSENT"},
      "workload_identity":{"pool_resource_name":"gcp_wif_pool://projects/123456789012/locations/global/workloadIdentityPools/aigc-stage","provider_resource_name":"gcp_wif_provider://projects/123456789012/locations/global/workloadIdentityPools/aigc-stage/providers/github-aigc","github_repository_id":"1287333065","github_repository_owner_id":"236225491","allowed_repository":"Lornt1666/AIGC","allowed_ref":"refs/heads/main","allowed_workflow_reference":".github/workflows/aigc-ci.yml@refs/heads/main","attribute_mapping_fingerprint":"b"*64,"attribute_condition_fingerprint":"c"*64,"plan_service_account_reference":"gcp_service_account://aigc-stage-123/aigc-plan@aigc-stage-123.iam.gserviceaccount.com","apply_service_account_reference":"gcp_service_account://aigc-stage-123/aigc-apply@aigc-stage-123.iam.gserviceaccount.com","application_runtime_service_account_reference":"gcp_service_account://aigc-stage-123/aigc-runtime@aigc-stage-123.iam.gserviceaccount.com","verified_user_managed_key_count":0,"long_lived_key_allowed":False,"service_account_key_export_allowed":False},
      "identity_platform_google_provider":{"google_oauth_web_client_id":"123456789012-abcXYZ_123.apps.googleusercontent.com","google_oauth_web_client_secret_reference":"gcp_secret://aigc-stage-123/aigc-google-oauth-client-secret/3","oauth_consent_configuration_reference":"gcp_oauth_consent://aigc-stage-123/external","authorized_domain":"dns_name://stage.aigc.example","authorized_origin":"https://stage.aigc.example","authorized_redirect_uri":"https://stage.aigc.example/auth/callback","localhost_allowed":False},
      "session_security":{"session_pepper_secret_reference":"gcp_secret://aigc-stage-123/aigc-session-pepper/7","immutable_numeric_version_required":True,"separate_from_oauth_client_secret":True,"raw_value_repository_allowed":False,"raw_value_receipt_allowed":False},
      "terraform_state":state,"test_subject":{"subject_reference":"staging_subject://operator-test-001","operator_controlled_attestation":"VERIFIED_TRUE","production_user_allowed":False,"public_registration_allowed":False,"email_in_repository_allowed":False},
      "iam_separation":{"bootstrap_administrator_reference":"gcp_principal://user:operator@example.invalid","bootstrap_administrator_separate":True,"plan_apply_runtime_identities_distinct":True,"owner_role_allowed":False,"editor_role_allowed":False,"least_privilege_required":True},"unresolved_requirements":[],"raw_secret_values_present":False,"authorization_receipt_issued":False,"provider_action_performed":False,"terraform_plan_performed":False,"terraform_apply_performed":False,"operator_review_required":True,"automatic_apply_allowed":False,"external_action_performed":False}

def plan_auth(pack):
    return {"contract_id":"AIGC-STAGING-IDENTITY-PLAN-AUTHORIZATION-RECEIPT-001","contract_version":"1.0.0","receipt_id":"SIPLAN-APPROVAL-0001","exact_revision":REVISION,"procurement_pack_digest":canonical_digest(pack),"decision":"APPROVED","reason_codes":[],"approved_by_role":"ACCOUNTABLE_OPERATOR","approved_by_name":"Justice Gray Maciocha","issued_at":"2026-07-14T18:05:00+00:00","expires_at":"2026-07-14T22:00:00+00:00","phase":pack["requested_plan_phase"],"target_project_reference":pack["project"]["project_reference"],"allowed_actions":{"read_project_metadata":True,"validate_required_apis":True,"validate_existing_resources":True,"generate_terraform_plan":True,"calculate_target_digest":True,"calculate_plan_digest":True},"mutation_actions":{"enable_api":False,"create_update_delete_resource":False,"iam_policy_mutation":False,"secret_access":False,"secret_create_update":False,"terraform_apply":False,"dns_mutation":False,"identity_provider_configuration":False,"test_subject_onboarding":False,"staging_sign_in":False},"single_use":True,"operator_review_required":True,"automatic_apply_allowed":False,"provider_action_performed":False,"terraform_plan_performed":False,"terraform_apply_performed":False,"external_action_performed":False}

def plan_evidence(pack,auth):
    provider=pack["identity_platform_google_provider"]
    return {"contract_id":"AIGC-STAGING-IDENTITY-PLAN-EVIDENCE-RECEIPT-001","contract_version":"1.0.0","receipt_id":"SIPLANEV-EVIDENCE-0001","exact_revision":REVISION,"procurement_pack_digest":canonical_digest(pack),"plan_authorization_receipt_id":auth["receipt_id"],"phase":pack["requested_plan_phase"],"target_project_reference":pack["project"]["project_reference"],"plan_result":"SUCCESS","review_status":"ACCEPTED","plan_artifact_digest":"sha256:"+"d"*64,"target_inventory_digest":"e"*64,"iam_delta_digest":"f"*64,"planned_resources":[pack["terraform_state"]["bucket_reference"]],"planned_iam_delta":[],"authorized_origins":[provider["authorized_origin"]],"authorized_redirect_uris":[provider["authorized_redirect_uri"]],"secret_references":sorted([provider["google_oauth_web_client_secret_reference"],pack["session_security"]["session_pepper_secret_reference"]]),"generated_at":"2026-07-14T18:10:00+00:00","reviewed_at":"2026-07-14T18:20:00+00:00","provider_read_performed":True,"provider_mutation_performed":False,"terraform_plan_performed":True,"terraform_apply_performed":False,"raw_secret_values_present":False,"external_action_performed":True}

def apply_auth(pack,evidence):
    phase=pack["requested_plan_phase"]
    scope={"state_backend_bootstrap_authorized":phase=="STATE_BACKEND_BOOTSTRAP","identity_platform_configuration_authorized":phase=="STAGING_IDENTITY_CONFIGURATION","workload_identity_configuration_authorized":False,"oauth_provider_configuration_authorized":False,"secret_container_creation_authorized":False,"secret_version_creation_authorized":False,"secret_value_access_authorized":False,"test_subject_onboarding_authorized":False,"staging_sign_in_authorized":False,"production_identity_activation_authorized":False,"production_deployment_authorized":False}
    return {"contract_id":"AIGC-STAGING-IDENTITY-APPLY-AUTHORIZATION-RECEIPT-001","contract_version":"1.0.0","receipt_id":"SIAPPLY-APPROVAL-0001","exact_revision":REVISION,"procurement_pack_digest":canonical_digest(pack),"plan_evidence_receipt_id":evidence["receipt_id"],"plan_evidence_digest":canonical_digest(evidence),"plan_artifact_digest":evidence["plan_artifact_digest"],"decision":"APPROVED","reason_codes":[],"approved_by_role":"ACCOUNTABLE_OPERATOR","approved_by_name":"Justice Gray Maciocha","issued_at":"2026-07-14T18:25:00+00:00","expires_at":"2026-07-14T19:20:00+00:00","phase":phase,"target_project_reference":pack["project"]["project_reference"],"planned_resources":deepcopy(evidence["planned_resources"]),"planned_iam_delta":deepcopy(evidence["planned_iam_delta"]),"authorized_origins":deepcopy(evidence["authorized_origins"]),"authorized_redirect_uris":deepcopy(evidence["authorized_redirect_uris"]),"secret_references":deepcopy(evidence["secret_references"]),"scope":scope,"rollback_instructions":"Revert only exact planned resources and restore the recorded prior state generation.","single_use":True,"operator_review_required":True,"automatic_apply_allowed":False,"provider_action_performed":False,"terraform_apply_performed":False,"external_action_performed":False}

def evaluate(pack,plan=None,evidence=None,apply=None):
    return evaluate_staging_identity_procurement(procurement_pack=pack,exact_revision=REVISION,plan_authorization_receipt=plan,plan_evidence_receipt=evidence,apply_authorization_receipt=apply,now=NOW).receipt

def test_canonical_template_validates_and_is_inert():
    result=evaluate(load_procurement_pack()); assert not result["pack_ready_for_plan_review"]; assert not result["plan_authorization_effective"]; assert not result["apply_authorization_effective"]; assert not result["external_action_performed"]

def test_resolved_bootstrap_and_identity_packs_validate():
    for phase in ("STATE_BACKEND_BOOTSTRAP","STAGING_IDENTITY_CONFIGURATION"):
        pack=resolved_pack(phase); assert not list(validator("staging_identity_procurement_readiness_pack").iter_errors(pack)); assert evaluate(pack)["pack_ready_for_plan_review"]

def test_ready_pack_rejects_missing_required_api():
    pack=resolved_pack(); pack["project"]["enabled_api_service_names"].remove("sts.googleapis.com"); assert list(validator("staging_identity_procurement_readiness_pack").iter_errors(pack))

def test_evaluator_rejects_cross_project_and_duplicate_identities():
    pack=resolved_pack(); pack["workload_identity"]["apply_service_account_reference"]=pack["workload_identity"]["plan_service_account_reference"]; assert "IAM_IDENTITIES_NOT_DISTINCT" in evaluate(pack)["pack_reason_codes"]
    pack=resolved_pack(); pack["session_security"]["session_pepper_secret_reference"]="gcp_secret://wrong-stage-123/aigc-session-pepper/7"; assert "SECRET_REFERENCE_PROJECT_MISMATCH" in evaluate(pack)["pack_reason_codes"]

def test_plan_authorization_is_read_only_and_exact_bound():
    pack=resolved_pack(); plan=plan_auth(pack); assert evaluate(pack,plan)["plan_authorization_effective"]
    plan["mutation_actions"]["terraform_apply"]=True; result=evaluate(pack,plan); assert not result["plan_authorization_effective"]; assert "PLAN_AUTHORIZATION_RECEIPT_INVALID" in result["plan_authorization_reason_codes"]

def test_plan_authorization_expiry_and_digest_mismatch_fail_closed():
    pack=resolved_pack(); plan=plan_auth(pack); plan["expires_at"]="2026-07-14T18:15:00+00:00"; assert "PLAN_AUTHORIZATION_RECEIPT_EXPIRED" in evaluate(pack,plan)["plan_authorization_reason_codes"]
    plan=plan_auth(pack); plan["procurement_pack_digest"]="0"*64; assert "PLAN_AUTHORIZATION_PACK_DIGEST_MISMATCH" in evaluate(pack,plan)["plan_authorization_reason_codes"]

def test_plan_evidence_requires_effective_authorization_and_review():
    pack=resolved_pack(); plan=plan_auth(pack); evidence=plan_evidence(pack,plan); assert evaluate(pack,plan,evidence)["plan_evidence_accepted"]
    evidence["review_status"]="PENDING_OPERATOR_REVIEW"; evidence["reviewed_at"]=None; result=evaluate(pack,plan,evidence); assert not result["plan_evidence_accepted"]; assert "PLAN_EVIDENCE_NOT_ACCEPTED" in result["plan_evidence_reason_codes"]

def test_apply_authorization_requires_accepted_exact_plan():
    pack=resolved_pack(); plan=plan_auth(pack); evidence=plan_evidence(pack,plan); apply=apply_auth(pack,evidence); assert evaluate(pack,plan,evidence,apply)["apply_authorization_effective"]
    apply["planned_resources"]=["gcs_bucket://aigc-stage-123/unreviewed-bucket"]; result=evaluate(pack,plan,evidence,apply); assert not result["apply_authorization_effective"]; assert "APPLY_AUTHORIZATION_RESOURCE_LIST_MISMATCH" in result["apply_authorization_reason_codes"]

def test_apply_authorization_cannot_include_production_scope():
    pack=resolved_pack("STAGING_IDENTITY_CONFIGURATION"); plan=plan_auth(pack); evidence=plan_evidence(pack,plan); apply=apply_auth(pack,evidence); apply["scope"]["production_deployment_authorized"]=True; result=evaluate(pack,plan,evidence,apply); assert not result["apply_authorization_effective"]; assert "APPLY_AUTHORIZATION_RECEIPT_INVALID" in result["apply_authorization_reason_codes"]

def test_evaluator_does_not_mutate_inputs():
    pack=resolved_pack(); plan=plan_auth(pack); evidence=plan_evidence(pack,plan); apply=apply_auth(pack,evidence); before=deepcopy((pack,plan,evidence,apply)); evaluate(pack,plan,evidence,apply); assert (pack,plan,evidence,apply)==before
