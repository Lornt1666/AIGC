from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping
from src.core.staging_procurement_contracts import DISCOVERY_ACTIONS, REQUIRED_PLAN_ACTIONS, STATUS_ORDER, _HEX40, StagingProcurementContractError, _consumed, _final_readiness_reason_codes, _lifecycle_reason_codes, _target_reason_codes, _time_reason_codes, _transition_reason_codes, _utc, canonical_digest, strict_validate

def evaluate_staging_procurement(*, procurement_pack: Mapping[str, Any], exact_revision: str | None, discovery_authorization_receipt: Mapping[str, Any] | None=None, discovery_evidence_receipt: Mapping[str, Any] | None=None, plan_authorization_receipt: Mapping[str, Any] | None=None, plan_evidence_receipt: Mapping[str, Any] | None=None, apply_authorization_receipt: Mapping[str, Any] | None=None, post_apply_evidence_receipt: Mapping[str, Any] | None=None, evaluated_at: datetime | None=None) -> dict[str, Any]:
    pack = strict_validate('staging_identity_procurement_readiness_pack', procurement_pack)
    now = _utc(evaluated_at or datetime.now(timezone.utc))
    revision = str(exact_revision) if exact_revision and _HEX40.fullmatch(str(exact_revision)) else 'unbound'
    pack_digest = canonical_digest(pack)
    lifecycle_reasons = _lifecycle_reason_codes(pack, now=now)
    if revision == 'unbound':
        lifecycle_reasons.append('REVISION_UNBOUND')
    transition_reasons = _transition_reason_codes(pack)
    target_reasons = _target_reason_codes(pack)
    lifecycle_effective = not lifecycle_reasons and (not transition_reasons)
    target_complete = not target_reasons
    discovery_auth_reasons: list[str] = []
    discovery_auth: dict[str, Any] | None = None
    if discovery_authorization_receipt is None:
        discovery_auth_reasons.append('DISCOVERY_AUTHORIZATION_RECEIPT_MISSING')
    else:
        try:
            discovery_auth = strict_validate('provider_discovery_authorization_receipt', discovery_authorization_receipt)
        except StagingProcurementContractError:
            discovery_auth_reasons.append('DISCOVERY_AUTHORIZATION_RECEIPT_INVALID')
        else:
            if not lifecycle_effective:
                discovery_auth_reasons.append('PACK_LIFECYCLE_NOT_EFFECTIVE')
            if not target_complete:
                discovery_auth_reasons.append('TARGET_SPECIFICATION_INCOMPLETE')
            if STATUS_ORDER.get(pack['status'], -1) < STATUS_ORDER['DISCOVERY_READY_FOR_REVIEW']:
                discovery_auth_reasons.append('PACK_NOT_DISCOVERY_READY')
            if _consumed(pack, 'provider_discovery'):
                discovery_auth_reasons.append('DISCOVERY_PHASE_ALREADY_CONSUMED')
            if discovery_auth['decision'] != 'APPROVED':
                discovery_auth_reasons.append('DISCOVERY_OPERATOR_DENIED')
            if discovery_auth['exact_revision'] != revision:
                discovery_auth_reasons.append('DISCOVERY_REVISION_MISMATCH')
            if discovery_auth['procurement_pack_digest'] != pack_digest:
                discovery_auth_reasons.append('DISCOVERY_PACK_DIGEST_MISMATCH')
            if discovery_auth['target_project_reference'] != pack['target_specification']['project_reference']:
                discovery_auth_reasons.append('DISCOVERY_PROJECT_MISMATCH')
            if set(discovery_auth['allowed_actions']) != DISCOVERY_ACTIONS:
                discovery_auth_reasons.append('DISCOVERY_SCOPE_MISMATCH')
            discovery_auth_reasons.extend(_time_reason_codes(discovery_auth, now=now, max_hours=4, prefix='DISCOVERY_AUTHORIZATION'))
    discovery_auth_reasons = list(dict.fromkeys(discovery_auth_reasons))
    discovery_auth_effective = discovery_auth is not None and (not discovery_auth_reasons)
    discovery_evidence_reasons: list[str] = []
    discovery_evidence: dict[str, Any] | None = None
    if discovery_evidence_receipt is None:
        discovery_evidence_reasons.append('DISCOVERY_EVIDENCE_RECEIPT_MISSING')
    else:
        try:
            discovery_evidence = strict_validate('provider_discovery_evidence_receipt', discovery_evidence_receipt)
        except StagingProcurementContractError:
            discovery_evidence_reasons.append('DISCOVERY_EVIDENCE_RECEIPT_INVALID')
        else:
            if not discovery_auth_effective:
                discovery_evidence_reasons.append('DISCOVERY_AUTHORIZATION_NOT_EFFECTIVE')
            if discovery_evidence['exact_revision'] != revision:
                discovery_evidence_reasons.append('DISCOVERY_EVIDENCE_REVISION_MISMATCH')
            if discovery_evidence['procurement_pack_digest'] != pack_digest:
                discovery_evidence_reasons.append('DISCOVERY_EVIDENCE_PACK_DIGEST_MISMATCH')
            if discovery_auth and discovery_evidence['discovery_authorization_receipt_id'] != discovery_auth['receipt_id']:
                discovery_evidence_reasons.append('DISCOVERY_EVIDENCE_AUTHORIZATION_MISMATCH')
            if discovery_evidence['target_project_reference'] != pack['target_specification']['project_reference']:
                discovery_evidence_reasons.append('DISCOVERY_EVIDENCE_PROJECT_MISMATCH')
            if discovery_evidence['result'] not in {'SUCCESS', 'PARTIAL'}:
                discovery_evidence_reasons.append('DISCOVERY_EVIDENCE_FAILED')
            if discovery_evidence['review_status'] != 'ACCEPTED':
                discovery_evidence_reasons.append('DISCOVERY_EVIDENCE_NOT_ACCEPTED')
    discovery_evidence_reasons = list(dict.fromkeys(discovery_evidence_reasons))
    discovery_evidence_accepted = discovery_evidence is not None and (not discovery_evidence_reasons)
    discovery_evidence_digest = canonical_digest(discovery_evidence) if discovery_evidence else None
    plan_auth_reasons: list[str] = []
    plan_auth: dict[str, Any] | None = None
    if plan_authorization_receipt is None:
        plan_auth_reasons.append('PLAN_AUTHORIZATION_RECEIPT_MISSING')
    else:
        try:
            plan_auth = strict_validate('staging_plan_authorization_receipt', plan_authorization_receipt)
        except StagingProcurementContractError:
            plan_auth_reasons.append('PLAN_AUTHORIZATION_RECEIPT_INVALID')
        else:
            phase = plan_auth['phase']
            expected_status = 'STATE_BACKEND_PLAN_READY' if phase == 'STATE_BACKEND_BOOTSTRAP' else 'IDENTITY_BOOTSTRAP_PLAN_READY'
            phase_key = 'state_backend_plan' if phase == 'STATE_BACKEND_BOOTSTRAP' else 'identity_bootstrap_plan'
            if not discovery_evidence_accepted:
                plan_auth_reasons.append('DISCOVERY_EVIDENCE_NOT_ACCEPTED')
            if pack['status'] != expected_status:
                plan_auth_reasons.append('PACK_NOT_READY_FOR_REQUESTED_PLAN_PHASE')
            if _consumed(pack, phase_key):
                plan_auth_reasons.append('PLAN_PHASE_ALREADY_CONSUMED')
            if phase == 'IDENTITY_BOOTSTRAP':
                state = pack['verified_provider_state']['terraform_state']
                if state['bootstrap_status'] != 'BOOTSTRAPPED_VERIFIED':
                    plan_auth_reasons.append('STATE_BACKEND_NOT_BOOTSTRAPPED')
            if plan_auth['decision'] != 'APPROVED':
                plan_auth_reasons.append('PLAN_OPERATOR_DENIED')
            if plan_auth['exact_revision'] != revision:
                plan_auth_reasons.append('PLAN_REVISION_MISMATCH')
            if plan_auth['procurement_pack_digest'] != pack_digest:
                plan_auth_reasons.append('PLAN_PACK_DIGEST_MISMATCH')
            if plan_auth['target_project_reference'] != pack['target_specification']['project_reference']:
                plan_auth_reasons.append('PLAN_PROJECT_MISMATCH')
            if discovery_evidence:
                if plan_auth['discovery_evidence_receipt_id'] != discovery_evidence['receipt_id']:
                    plan_auth_reasons.append('PLAN_DISCOVERY_EVIDENCE_ID_MISMATCH')
                if plan_auth['discovery_evidence_digest'] != discovery_evidence_digest:
                    plan_auth_reasons.append('PLAN_DISCOVERY_EVIDENCE_DIGEST_MISMATCH')
            if set(plan_auth['allowed_actions']) != REQUIRED_PLAN_ACTIONS:
                plan_auth_reasons.append('PLAN_SCOPE_MISMATCH')
            plan_auth_reasons.extend(_time_reason_codes(plan_auth, now=now, max_hours=4, prefix='PLAN_AUTHORIZATION'))
    plan_auth_reasons = list(dict.fromkeys(plan_auth_reasons))
    plan_auth_effective = plan_auth is not None and (not plan_auth_reasons)
    plan_evidence_reasons: list[str] = []
    plan_evidence: dict[str, Any] | None = None
    if plan_evidence_receipt is None:
        plan_evidence_reasons.append('PLAN_EVIDENCE_RECEIPT_MISSING')
    else:
        try:
            plan_evidence = strict_validate('staging_plan_evidence_receipt', plan_evidence_receipt)
        except StagingProcurementContractError:
            plan_evidence_reasons.append('PLAN_EVIDENCE_RECEIPT_INVALID')
        else:
            if not plan_auth_effective:
                plan_evidence_reasons.append('PLAN_AUTHORIZATION_NOT_EFFECTIVE')
            if plan_evidence['exact_revision'] != revision:
                plan_evidence_reasons.append('PLAN_EVIDENCE_REVISION_MISMATCH')
            if plan_evidence['procurement_pack_digest'] != pack_digest:
                plan_evidence_reasons.append('PLAN_EVIDENCE_PACK_DIGEST_MISMATCH')
            if plan_auth and plan_evidence['plan_authorization_receipt_id'] != plan_auth['receipt_id']:
                plan_evidence_reasons.append('PLAN_EVIDENCE_AUTHORIZATION_MISMATCH')
            if plan_auth and plan_evidence['phase'] != plan_auth['phase']:
                plan_evidence_reasons.append('PLAN_EVIDENCE_PHASE_MISMATCH')
            if plan_evidence['target_project_reference'] != pack['target_specification']['project_reference']:
                plan_evidence_reasons.append('PLAN_EVIDENCE_PROJECT_MISMATCH')
            if discovery_evidence:
                if plan_evidence['discovery_evidence_receipt_id'] != discovery_evidence['receipt_id']:
                    plan_evidence_reasons.append('PLAN_EVIDENCE_DISCOVERY_ID_MISMATCH')
                if plan_evidence['discovery_evidence_digest'] != discovery_evidence_digest:
                    plan_evidence_reasons.append('PLAN_EVIDENCE_DISCOVERY_DIGEST_MISMATCH')
            if plan_evidence['plan_result'] != 'SUCCESS':
                plan_evidence_reasons.append('PLAN_EVIDENCE_FAILED')
            if plan_evidence['review_status'] != 'ACCEPTED':
                plan_evidence_reasons.append('PLAN_EVIDENCE_NOT_ACCEPTED')
    plan_evidence_reasons = list(dict.fromkeys(plan_evidence_reasons))
    plan_evidence_accepted = plan_evidence is not None and (not plan_evidence_reasons)
    plan_evidence_digest = canonical_digest(plan_evidence) if plan_evidence else None
    apply_auth_reasons: list[str] = []
    apply_auth: dict[str, Any] | None = None
    if apply_authorization_receipt is None:
        apply_auth_reasons.append('APPLY_AUTHORIZATION_RECEIPT_MISSING')
    else:
        try:
            apply_auth = strict_validate('staging_apply_authorization_receipt', apply_authorization_receipt)
        except StagingProcurementContractError:
            apply_auth_reasons.append('APPLY_AUTHORIZATION_RECEIPT_INVALID')
        else:
            if not plan_evidence_accepted:
                apply_auth_reasons.append('PLAN_EVIDENCE_NOT_ACCEPTED')
            phase_key = 'state_backend_apply' if apply_auth['phase'] == 'STATE_BACKEND_BOOTSTRAP' else 'identity_bootstrap_apply'
            if _consumed(pack, phase_key):
                apply_auth_reasons.append('APPLY_PHASE_ALREADY_CONSUMED')
            if apply_auth['decision'] != 'APPROVED':
                apply_auth_reasons.append('APPLY_OPERATOR_DENIED')
            if apply_auth['provider_mutation_authorized'] is not True:
                apply_auth_reasons.append('APPLY_PROVIDER_MUTATION_NOT_AUTHORIZED')
            if apply_auth['terraform_apply_authorized'] is not True:
                apply_auth_reasons.append('TERRAFORM_APPLY_NOT_AUTHORIZED')
            if apply_auth['exact_revision'] != revision:
                apply_auth_reasons.append('APPLY_REVISION_MISMATCH')
            if apply_auth['procurement_pack_digest'] != pack_digest:
                apply_auth_reasons.append('APPLY_PACK_DIGEST_MISMATCH')
            if apply_auth['target_project_reference'] != pack['target_specification']['project_reference']:
                apply_auth_reasons.append('APPLY_PROJECT_MISMATCH')
            if discovery_evidence:
                if apply_auth['discovery_evidence_receipt_id'] != discovery_evidence['receipt_id']:
                    apply_auth_reasons.append('APPLY_DISCOVERY_EVIDENCE_ID_MISMATCH')
                if apply_auth['discovery_evidence_digest'] != discovery_evidence_digest:
                    apply_auth_reasons.append('APPLY_DISCOVERY_EVIDENCE_DIGEST_MISMATCH')
            if plan_auth and apply_auth['plan_authorization_receipt_id'] != plan_auth['receipt_id']:
                apply_auth_reasons.append('APPLY_PLAN_AUTHORIZATION_ID_MISMATCH')
            if plan_evidence:
                comparisons = (('plan_evidence_receipt_id', plan_evidence['receipt_id'], 'APPLY_PLAN_EVIDENCE_ID_MISMATCH'), ('plan_evidence_digest', plan_evidence_digest, 'APPLY_PLAN_EVIDENCE_DIGEST_MISMATCH'), ('plan_artifact_digest', plan_evidence['plan_artifact_digest'], 'APPLY_PLAN_ARTIFACT_MISMATCH'), ('planned_resources', plan_evidence['planned_resources'], 'APPLY_RESOURCE_LIST_MISMATCH'), ('planned_iam_delta', plan_evidence['planned_iam_delta'], 'APPLY_IAM_DELTA_MISMATCH'), ('authorized_origins', plan_evidence['authorized_origins'], 'APPLY_ORIGIN_LIST_MISMATCH'), ('authorized_redirect_uris', plan_evidence['authorized_redirect_uris'], 'APPLY_REDIRECT_LIST_MISMATCH'), ('secret_references', plan_evidence['secret_references'], 'APPLY_SECRET_REFERENCE_LIST_MISMATCH'), ('phase', plan_evidence['phase'], 'APPLY_PHASE_MISMATCH'))
                for key, expected, reason in comparisons:
                    if apply_auth[key] != expected:
                        apply_auth_reasons.append(reason)
            apply_auth_reasons.extend(_time_reason_codes(apply_auth, now=now, max_hours=1, prefix='APPLY_AUTHORIZATION'))
    apply_auth_reasons = list(dict.fromkeys(apply_auth_reasons))
    apply_auth_effective = apply_auth is not None and (not apply_auth_reasons)
    post_apply_reasons: list[str] = []
    post_apply: dict[str, Any] | None = None
    if post_apply_evidence_receipt is None:
        post_apply_reasons.append('POST_APPLY_EVIDENCE_RECEIPT_MISSING')
    else:
        try:
            post_apply = strict_validate('staging_post_apply_operational_evidence', post_apply_evidence_receipt)
        except StagingProcurementContractError:
            post_apply_reasons.append('POST_APPLY_EVIDENCE_RECEIPT_INVALID')
        else:
            if not apply_auth_effective:
                post_apply_reasons.append('APPLY_AUTHORIZATION_NOT_EFFECTIVE')
            if post_apply['exact_revision'] != revision:
                post_apply_reasons.append('POST_APPLY_REVISION_MISMATCH')
            if post_apply['procurement_pack_digest'] != pack_digest:
                post_apply_reasons.append('POST_APPLY_PACK_DIGEST_MISMATCH')
            if apply_auth and post_apply['apply_authorization_receipt_id'] != apply_auth['receipt_id']:
                post_apply_reasons.append('POST_APPLY_AUTHORIZATION_ID_MISMATCH')
            if plan_evidence:
                if post_apply['plan_evidence_receipt_id'] != plan_evidence['receipt_id']:
                    post_apply_reasons.append('POST_APPLY_PLAN_EVIDENCE_ID_MISMATCH')
                if post_apply['plan_evidence_digest'] != plan_evidence_digest:
                    post_apply_reasons.append('POST_APPLY_PLAN_EVIDENCE_DIGEST_MISMATCH')
                if post_apply['plan_artifact_digest'] != plan_evidence['plan_artifact_digest']:
                    post_apply_reasons.append('POST_APPLY_PLAN_ARTIFACT_MISMATCH')
                if post_apply['phase'] != plan_evidence['phase']:
                    post_apply_reasons.append('POST_APPLY_PHASE_MISMATCH')
            if post_apply['target_project_reference'] != pack['target_specification']['project_reference']:
                post_apply_reasons.append('POST_APPLY_PROJECT_MISMATCH')
            if post_apply['result'] != 'SUCCESS':
                post_apply_reasons.append('POST_APPLY_RESULT_NOT_SUCCESS')
            if post_apply['review_status'] != 'ACCEPTED':
                post_apply_reasons.append('POST_APPLY_EVIDENCE_NOT_ACCEPTED')
    post_apply_reasons = list(dict.fromkeys(post_apply_reasons))
    post_apply_accepted = post_apply is not None and (not post_apply_reasons)
    final_reasons = lifecycle_reasons + transition_reasons + target_reasons + _final_readiness_reason_codes(pack)
    final_reasons = list(dict.fromkeys(final_reasons))
    ready_for_operator_review = not final_reasons
    material = '|'.join([revision, pack_digest, ','.join(discovery_auth_reasons), ','.join(discovery_evidence_reasons), ','.join(plan_auth_reasons), ','.join(plan_evidence_reasons), ','.join(apply_auth_reasons), ','.join(post_apply_reasons), ','.join(final_reasons)])
    evaluation = {'contract_id': 'AIGC-STAGING-PROCUREMENT-STATE-EVALUATION-001', 'contract_version': '1.1.0', 'evaluation_id': 'SPSE-' + hashlib.sha256(material.encode('utf-8')).hexdigest()[:24].upper(), 'exact_revision': revision, 'procurement_pack_digest': pack_digest, 'pack_artifact_kind': pack['artifact_kind'], 'pack_status': pack['status'], 'target_specification_complete': target_complete, 'pack_lifecycle_effective': lifecycle_effective, 'discovery_authorization_present': discovery_auth is not None, 'discovery_authorization_effective': discovery_auth_effective, 'discovery_authorization_reason_codes': discovery_auth_reasons, 'discovery_evidence_present': discovery_evidence is not None, 'discovery_evidence_accepted': discovery_evidence_accepted, 'discovery_evidence_reason_codes': discovery_evidence_reasons, 'plan_authorization_present': plan_auth is not None, 'plan_authorization_effective': plan_auth_effective, 'plan_authorization_reason_codes': plan_auth_reasons, 'plan_evidence_present': plan_evidence is not None, 'plan_evidence_accepted': plan_evidence_accepted, 'plan_evidence_reason_codes': plan_evidence_reasons, 'apply_authorization_present': apply_auth is not None, 'apply_authorization_effective': apply_auth_effective, 'apply_authorization_reason_codes': apply_auth_reasons, 'post_apply_evidence_present': post_apply is not None, 'post_apply_evidence_accepted': post_apply_accepted, 'post_apply_evidence_reason_codes': post_apply_reasons, 'ready_for_operator_review': ready_for_operator_review, 'final_readiness_reason_codes': final_reasons, 'evaluated_at': now.isoformat(), 'operator_review_required': True, 'automatic_apply_allowed': False, 'external_action_performed': False}
    return strict_validate('staging_procurement_state_evaluation', evaluation)
