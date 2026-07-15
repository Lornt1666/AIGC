from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse
from jsonschema import Draft202012Validator, FormatChecker
ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / 'schemas'
REQUIRED_APIS = {'cloudresourcemanager.googleapis.com', 'iam.googleapis.com', 'iamcredentials.googleapis.com', 'identitytoolkit.googleapis.com', 'secretmanager.googleapis.com', 'serviceusage.googleapis.com', 'storage.googleapis.com', 'sts.googleapis.com'}
DISCOVERY_ACTIONS = {'READ_PROJECT_METADATA', 'READ_ENABLED_APIS', 'READ_EXISTING_IAM', 'READ_SERVICE_ACCOUNT_KEY_COUNTS', 'READ_STATE_BACKEND_METADATA', 'READ_IDENTITY_PLATFORM_CONFIGURATION'}
REQUIRED_PLAN_ACTIONS = {'READ_PROJECT_METADATA', 'VALIDATE_REQUIRED_APIS', 'VALIDATE_EXISTING_RESOURCES', 'GENERATE_TERRAFORM_PLAN', 'CALCULATE_TARGET_DIGEST', 'CALCULATE_PLAN_DIGEST'}
STATUS_ORDER = {'TARGET_SPECIFICATION': 0, 'DISCOVERY_READY_FOR_REVIEW': 1, 'DISCOVERY_EVIDENCE_ACCEPTED': 2, 'STATE_BACKEND_PLAN_READY': 3, 'STATE_BACKEND_BOOTSTRAPPED': 4, 'IDENTITY_BOOTSTRAP_PLAN_READY': 5, 'READY_FOR_OPERATOR_REVIEW': 6, 'SUPERSEDED': 7}
_HEX40 = re.compile('^[a-f0-9]{40}$')
STATUS_TRANSITIONS = {'TARGET_SPECIFICATION': {'DISCOVERY_READY_FOR_REVIEW', 'SUPERSEDED'}, 'DISCOVERY_READY_FOR_REVIEW': {'DISCOVERY_EVIDENCE_ACCEPTED', 'SUPERSEDED'}, 'DISCOVERY_EVIDENCE_ACCEPTED': {'STATE_BACKEND_PLAN_READY', 'SUPERSEDED'}, 'STATE_BACKEND_PLAN_READY': {'STATE_BACKEND_BOOTSTRAPPED', 'SUPERSEDED'}, 'STATE_BACKEND_BOOTSTRAPPED': {'IDENTITY_BOOTSTRAP_PLAN_READY', 'SUPERSEDED'}, 'IDENTITY_BOOTSTRAP_PLAN_READY': {'READY_FOR_OPERATOR_REVIEW', 'SUPERSEDED'}, 'READY_FOR_OPERATOR_REVIEW': {'SUPERSEDED'}, 'SUPERSEDED': set()}

class StagingProcurementContractError(ValueError):
    """Raised when a staging procurement artifact violates its strict contract."""

def canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(payload), sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()

def _load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_DIR / f'{name}.schema.json'
    try:
        schema = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise StagingProcurementContractError(f'Unable to load schema: {path.name}') from exc
    Draft202012Validator.check_schema(schema)
    return schema

def strict_validate(name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    schema = _load_schema(name)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), key=lambda error: list(error.absolute_path))
    if errors:
        messages: list[str] = []
        for error in errors[:10]:
            location = '$' + ''.join((f'[{part}]' if isinstance(part, int) else f'.{part}' for part in error.absolute_path))
            messages.append(f'{location}: {error.message}')
        raise StagingProcurementContractError(f"{name} validation failed: {'; '.join(messages)}")
    return value

def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise StagingProcurementContractError(f'{label} is missing')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise StagingProcurementContractError(f'{label} is invalid') from exc
    return _utc(parsed)

def _time_reason_codes(receipt: Mapping[str, Any], *, now: datetime, max_hours: int, prefix: str) -> list[str]:
    try:
        issued = _parse_time(receipt.get('issued_at'), f'{prefix} issued_at')
        expires = _parse_time(receipt.get('expires_at'), f'{prefix} expires_at')
    except StagingProcurementContractError:
        return [f'{prefix}_TIME_INVALID']
    reasons: list[str] = []
    if expires <= issued:
        reasons.append(f'{prefix}_LIFETIME_INVALID')
    if issued > now:
        reasons.append(f'{prefix}_FUTURE_DATED')
    if now >= expires:
        reasons.append(f'{prefix}_EXPIRED')
    if expires - issued > timedelta(hours=max_hours):
        reasons.append(f'{prefix}_TTL_EXCEEDED')
    return reasons

def _transition_reason_codes(pack: Mapping[str, Any]) -> list[str]:
    transition = dict(pack.get('transition') or {})
    current = str(pack.get('status') or '')
    previous = transition.get('previous_status')
    reason = transition.get('transition_reason')
    evidence_digest = transition.get('transition_evidence_digest')
    if pack.get('artifact_kind') == 'TEMPLATE':
        if previous is not None or reason is not None or evidence_digest is not None:
            return ['TEMPLATE_TRANSITION_MUST_BE_EMPTY']
        return []
    if current == 'TARGET_SPECIFICATION':
        if previous is not None:
            return ['INITIAL_SUBMISSION_PREVIOUS_STATUS_MUST_BE_NULL']
        return []
    reasons: list[str] = []
    if previous not in STATUS_TRANSITIONS:
        reasons.append('TRANSITION_PREVIOUS_STATUS_INVALID')
    elif current not in STATUS_TRANSITIONS[previous]:
        reasons.append('TRANSITION_NOT_ALLOWED')
    if not reason:
        reasons.append('TRANSITION_REASON_MISSING')
    if not evidence_digest:
        reasons.append('TRANSITION_EVIDENCE_DIGEST_MISSING')
    return reasons

def _lifecycle_reason_codes(pack: Mapping[str, Any], *, now: datetime) -> list[str]:
    if pack.get('artifact_kind') != 'SUBMISSION':
        return ['PACK_TEMPLATE_NOT_SUBMISSION']
    lifecycle = dict(pack.get('lifecycle') or {})
    reasons: list[str] = []
    try:
        created = _parse_time(lifecycle.get('created_at'), 'pack created_at')
        expires = _parse_time(lifecycle.get('expires_at'), 'pack expires_at')
    except StagingProcurementContractError:
        return ['PACK_LIFETIME_UNBOUND']
    if expires <= created:
        reasons.append('PACK_LIFETIME_INVALID')
    if created > now:
        reasons.append('PACK_FUTURE_DATED')
    if now >= expires:
        reasons.append('PACK_EXPIRED')
    if expires - created > timedelta(days=7):
        reasons.append('PACK_TTL_EXCEEDED')
    if lifecycle.get('revoked') is True:
        reasons.append('PACK_REVOKED')
    if pack.get('status') == 'SUPERSEDED':
        reasons.append('PACK_SUPERSEDED')
    return reasons

def _target_reason_codes(pack: Mapping[str, Any]) -> list[str]:
    target = dict(pack.get('target_specification') or {})
    reasons: list[str] = []
    required_fields = ('project_reference', 'project_id', 'proposed_wif_pool_id', 'proposed_wif_provider_id', 'proposed_plan_service_account_id', 'proposed_apply_service_account_id', 'proposed_runtime_service_account_id', 'proposed_state_bucket_reference', 'proposed_staging_domain_reference')
    for key in required_fields:
        if not target.get(key):
            reasons.append(f'TARGET_{key.upper()}_UNRESOLVED')
    project_id = str(target.get('project_id') or '')
    project_reference = str(target.get('project_reference') or '')
    if project_id and project_reference != f'gcp_project://{project_id}':
        reasons.append('TARGET_PROJECT_REFERENCE_MISMATCH')
    service_account_ids = [target.get('proposed_plan_service_account_id'), target.get('proposed_apply_service_account_id'), target.get('proposed_runtime_service_account_id')]
    if all(service_account_ids) and len(set(service_account_ids)) != 3:
        reasons.append('TARGET_SERVICE_ACCOUNT_IDENTIFIERS_NOT_DISTINCT')
    if not REQUIRED_APIS.issubset(set(target.get('required_api_service_names') or [])):
        reasons.append('TARGET_REQUIRED_APIS_INCOMPLETE')
    expected_public = {'github_repository_id': 1287333065, 'github_repository_owner_id': 236225491, 'allowed_repository': 'Lornt1666/AIGC', 'allowed_ref': 'refs/heads/main', 'allowed_workflow_reference': 'Lornt1666/AIGC/.github/workflows/aigc-ci.yml@refs/heads/main'}
    for key, expected in expected_public.items():
        if target.get(key) != expected:
            reasons.append(f'TARGET_{key.upper()}_MISMATCH')
    return reasons

def _project_from_reference(value: str, prefix: str) -> str:
    return value.removeprefix(prefix).split('/', 1)[0]

def _final_readiness_reason_codes(pack: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if pack.get('status') != 'READY_FOR_OPERATOR_REVIEW':
        reasons.append('PACK_NOT_READY_FOR_OPERATOR_REVIEW')
    if pack.get('unresolved_requirements') != []:
        reasons.append('UNRESOLVED_REQUIREMENTS_REMAIN')
    target = dict(pack.get('target_specification') or {})
    provider = dict(pack.get('verified_provider_state') or {})
    project = dict(provider.get('project') or {})
    workload = dict(provider.get('workload_identity') or {})
    identity = dict(provider.get('identity_provider') or {})
    session = dict(provider.get('session_security') or {})
    state = dict(provider.get('terraform_state') or {})
    subject = dict(provider.get('test_subject') or {})
    iam = dict(provider.get('iam_separation') or {})
    evidence = dict(pack.get('evidence_bindings') or {})
    project_id = str(target.get('project_id') or '')
    project_number = str(project.get('project_number') or '')
    if not project_number:
        reasons.append('VERIFIED_PROJECT_NUMBER_MISSING')
    for key in ('billing_status', 'identity_platform_status', 'production_data_absent_status'):
        if project.get(key) != 'VERIFIED_TRUE':
            reasons.append(f'VERIFIED_PROJECT_{key.upper()}_NOT_TRUE')
    if not REQUIRED_APIS.issubset(set(project.get('enabled_api_service_names') or [])):
        reasons.append('VERIFIED_REQUIRED_APIS_INCOMPLETE')
    required_workload = ('pool_reference', 'provider_reference', 'plan_service_account_reference', 'apply_service_account_reference', 'runtime_service_account_reference', 'attribute_mapping_fingerprint', 'attribute_condition_fingerprint')
    for key in required_workload:
        if not workload.get(key):
            reasons.append(f'VERIFIED_{key.upper()}_MISSING')
    pool_reference = str(workload.get('pool_reference') or '')
    provider_reference = str(workload.get('provider_reference') or '')
    if project_number and pool_reference and (not pool_reference.startswith(f'gcp_wif_pool://{project_number}/')):
        reasons.append('WIF_POOL_PROJECT_NUMBER_MISMATCH')
    if project_number and provider_reference and (not provider_reference.startswith(f'gcp_wif_provider://{project_number}/')):
        reasons.append('WIF_PROVIDER_PROJECT_NUMBER_MISMATCH')
    service_accounts = [str(workload.get('plan_service_account_reference') or ''), str(workload.get('apply_service_account_reference') or ''), str(workload.get('runtime_service_account_reference') or '')]
    if all(service_accounts):
        if len(set(service_accounts)) != 3:
            reasons.append('VERIFIED_SERVICE_ACCOUNTS_NOT_DISTINCT')
        if project_id and any((_project_from_reference(item, 'gcp_service_account://') != project_id for item in service_accounts)):
            reasons.append('SERVICE_ACCOUNT_PROJECT_MISMATCH')
    if workload.get('key_status') != 'VERIFIED':
        reasons.append('SERVICE_ACCOUNT_KEY_STATUS_UNVERIFIED')
    if workload.get('verified_user_managed_key_count') != 0:
        reasons.append('USER_MANAGED_SERVICE_ACCOUNT_KEYS_PRESENT_OR_UNVERIFIED')
    for key in ('google_oauth_web_client_id', 'oauth_client_secret_reference', 'oauth_consent_configuration_reference', 'authorized_domain_reference', 'authorized_origin', 'authorized_redirect_uri'):
        if not identity.get(key):
            reasons.append(f'VERIFIED_IDENTITY_{key.upper()}_MISSING')
    oauth_secret = str(identity.get('oauth_client_secret_reference') or '')
    session_secret = str(session.get('session_pepper_secret_reference') or '')
    if not session_secret:
        reasons.append('VERIFIED_SESSION_PEPPER_SECRET_REFERENCE_MISSING')
    if oauth_secret and session_secret and (oauth_secret == session_secret):
        reasons.append('OAUTH_AND_SESSION_SECRET_NOT_SEPARATE')
    if project_id and any((item and _project_from_reference(item, 'gcp_secret://') != project_id for item in (oauth_secret, session_secret))):
        reasons.append('SECRET_REFERENCE_PROJECT_MISMATCH')
    domain = str(identity.get('authorized_domain_reference') or '').removeprefix('dns_name://').lower()
    for key in ('authorized_origin', 'authorized_redirect_uri'):
        value = str(identity.get(key) or '')
        host = (urlparse(value).hostname or '').lower()
        if domain and host != domain:
            reasons.append('AUTHORIZED_DOMAIN_ORIGIN_REDIRECT_MISMATCH')
    if state.get('bootstrap_status') != 'BOOTSTRAPPED_VERIFIED':
        reasons.append('STATE_BACKEND_NOT_BOOTSTRAPPED')
    for key in ('bucket_preexists_backend_init_status', 'uniform_bucket_level_access_status', 'public_access_prevention_status', 'object_versioning_status', 'state_locking_status'):
        if state.get(key) != 'VERIFIED_TRUE':
            reasons.append(f'STATE_{key.upper()}_NOT_TRUE')
    for key in ('bucket_reference', 'state_reference', 'retention_policy_days', 'rollback_generation_reference'):
        if state.get(key) in (None, ''):
            reasons.append(f'STATE_{key.upper()}_MISSING')
    if subject.get('operator_controlled_status') != 'VERIFIED_TRUE':
        reasons.append('TEST_SUBJECT_NOT_OPERATOR_CONTROLLED')
    if not subject.get('reference'):
        reasons.append('TEST_SUBJECT_REFERENCE_MISSING')
    if subject.get('production_identity') is not False or subject.get('email_committed') is not False:
        reasons.append('TEST_SUBJECT_BOUNDARY_VIOLATION')
    if not iam.get('bootstrap_administrator_reference'):
        reasons.append('BOOTSTRAP_ADMINISTRATOR_REFERENCE_MISSING')
    if iam.get('bootstrap_administrator_separate') is not True:
        reasons.append('BOOTSTRAP_ADMINISTRATOR_NOT_SEPARATE')
    if iam.get('plan_apply_runtime_identities_distinct') is not True:
        reasons.append('PLAN_APPLY_RUNTIME_IDENTITIES_NOT_DISTINCT')
    if iam.get('owner_role_allowed') is not False or iam.get('editor_role_allowed') is not False:
        reasons.append('BASIC_IAM_ROLE_ALLOWED')
    if iam.get('least_privilege_required') is not True:
        reasons.append('LEAST_PRIVILEGE_NOT_REQUIRED')
    for key in ('discovery_evidence_receipt_id', 'discovery_evidence_digest', 'state_backend_operational_evidence_receipt_id', 'state_backend_operational_evidence_digest', 'identity_operational_evidence_receipt_id', 'identity_operational_evidence_digest'):
        if not evidence.get(key):
            reasons.append(f'EVIDENCE_{key.upper()}_MISSING')
    for key in ('raw_secret_values_present', 'automatic_apply_allowed', 'authorization_receipt_issued', 'provider_action_performed', 'terraform_plan_performed', 'terraform_apply_performed', 'external_action_performed'):
        if pack.get(key) is not False:
            reasons.append(f'{key.upper()}_MUST_BE_FALSE')
    return list(dict.fromkeys(reasons))

def _consumed(pack: Mapping[str, Any], phase_key: str) -> bool:
    phase = dict((pack.get('phase_consumption') or {}).get(phase_key) or {})
    return phase.get('status') == 'CONSUMED'
