from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Mapping
from src.core.staging_procurement_contracts import DISCOVERY_ACTIONS, REQUIRED_APIS, REQUIRED_PLAN_ACTIONS, STATUS_ORDER, STATUS_TRANSITIONS, StagingProcurementContractError, _time_reason_codes, _utc, canonical_digest, strict_validate
from src.core.staging_procurement_evaluator import evaluate_staging_procurement

def evaluate_procurement_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    """Compatibility wrapper. A pack alone can never authorize provider action."""
    result = evaluate_staging_procurement(procurement_pack=pack, exact_revision=None)
    return {'pack_digest': result['procurement_pack_digest'], 'ready_for_operator_review': result['ready_for_operator_review'], 'reason_codes': result['final_readiness_reason_codes'], 'plan_authorization_effective': False, 'apply_authorization_effective': False, 'operator_review_required': True, 'automatic_apply_allowed': False, 'external_action_performed': False}

def evaluate_plan_authorization(receipt: Mapping[str, Any], *, exact_revision: str, procurement_pack_digest: str, evaluated_at: datetime | None=None) -> dict[str, Any]:
    """Compatibility wrapper. Full effectiveness requires integrated pack/evidence evaluation."""
    now = _utc(evaluated_at or datetime.now(timezone.utc))
    reasons: list[str] = []
    try:
        value = strict_validate('staging_plan_authorization_receipt', receipt)
    except StagingProcurementContractError:
        reasons.append('PLAN_AUTHORIZATION_RECEIPT_INVALID')
        value = None
    if value:
        if value['exact_revision'] != exact_revision:
            reasons.append('PLAN_REVISION_MISMATCH')
        if value['procurement_pack_digest'] != procurement_pack_digest:
            reasons.append('PLAN_PACK_DIGEST_MISMATCH')
        reasons.append('INTEGRATED_DISCOVERY_EVIDENCE_REQUIRED')
        reasons.extend(_time_reason_codes(value, now=now, max_hours=4, prefix='PLAN_AUTHORIZATION'))
    return {'effective': False, 'reason_codes': list(dict.fromkeys(reasons)), 'provider_action_performed': False, 'terraform_apply_performed': False, 'external_action_performed': False}

def evaluate_apply_authorization(receipt: Mapping[str, Any], *, exact_revision: str, procurement_pack_digest: str, plan_artifact_digest: str, evaluated_at: datetime | None=None) -> dict[str, Any]:
    """Compatibility wrapper. Apply is ineffective without accepted plan evidence."""
    now = _utc(evaluated_at or datetime.now(timezone.utc))
    reasons: list[str] = []
    try:
        value = strict_validate('staging_apply_authorization_receipt', receipt)
    except StagingProcurementContractError:
        reasons.append('APPLY_AUTHORIZATION_RECEIPT_INVALID')
        value = None
    if value:
        if value['exact_revision'] != exact_revision:
            reasons.append('APPLY_REVISION_MISMATCH')
        if value['procurement_pack_digest'] != procurement_pack_digest:
            reasons.append('APPLY_PACK_DIGEST_MISMATCH')
        if value['plan_artifact_digest'] != plan_artifact_digest:
            reasons.append('APPLY_PLAN_ARTIFACT_MISMATCH')
        reasons.append('INTEGRATED_PLAN_EVIDENCE_REQUIRED')
        reasons.extend(_time_reason_codes(value, now=now, max_hours=1, prefix='APPLY_AUTHORIZATION'))
    return {'effective': False, 'reason_codes': list(dict.fromkeys(reasons)), 'provider_action_performed': False, 'terraform_apply_performed': False, 'external_action_performed': False}
