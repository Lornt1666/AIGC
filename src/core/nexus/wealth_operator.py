from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.autonomy_policy import assess_autonomy
from src.domain.nexus.autonomy import ActionIntent
from src.domain.nexus.wealth import WealthOperatorPolicy, WealthWorkRequest


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = ROOT / "config" / "aigc_wealth_operator_policy.v1.json"
DEFAULT_SCHEMA_PATH = ROOT / "schemas" / "aigc_wealth_operator_policy.schema.json"


def load_wealth_policy(
    policy_path: Path = DEFAULT_POLICY_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> WealthOperatorPolicy:
    policy_document = json.loads(policy_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(policy_document)
    return WealthOperatorPolicy.model_validate(policy_document)


def _intent_for(request: WealthWorkRequest, policy: WealthOperatorPolicy) -> ActionIntent:
    action_policy = policy.policy_for(request.action)
    intent_id = "ACT-WEALTH" + canonical_sha256(request)[:20].upper()
    return ActionIntent(
        intent_id=intent_id,
        effect_class=action_policy.effect_class,
        public_read_only=action_policy.public_read_only,
        internal_sandbox_only=action_policy.internal_sandbox_only,
        persistent_internal_mutation=action_policy.persistent_internal_mutation,
        external_mutation=action_policy.external_mutation,
        communication=action_policy.communication,
        financial_spend_cad=request.financial_amount_cad,
        authorized_spend_cad=0,
        legal_commitment=action_policy.legal_commitment,
        existing_explicit_authority=False,
        permit_id=None,
    )


def build_wealth_work_plan(
    request: WealthWorkRequest,
    *,
    policy: WealthOperatorPolicy | None = None,
) -> dict[str, object]:
    """Build a deterministic plan; never retrieve, persist, communicate, or transact."""

    active_policy = policy or load_wealth_policy()
    action_policy = active_policy.policy_for(request.action)
    assessment = assess_autonomy(_intent_for(request, active_policy))

    missing_bindings: list[str] = []
    if action_policy.target_required and request.target_ref is None:
        missing_bindings.append("EXACT_TARGET")
    if action_policy.evidence_required and not request.evidence_refs:
        missing_bindings.append("VERIFIED_EVIDENCE_REFERENCE")

    approval_required = action_policy.approval_required
    required_bindings = (
        [
            "EXACT_TARGET",
            "CANONICAL_PAYLOAD_DIGEST",
            "COST_CEILING",
            "EXPIRY",
            "EXACT_REVISION",
            "CERTIFIED_CONNECTOR",
            "ONE_USE_EXECUTION_PERMIT",
            "SECRET_BROKER_REFERENCE_ONLY",
            "RECONCILIATION_PLAN",
        ]
        if approval_required
        else []
    )

    first_blocker = None
    if missing_bindings:
        first_blocker = f"{missing_bindings[0]}_REQUIRED"
    elif approval_required:
        first_blocker = "NEW_EXPLICIT_AUTHORITY_REQUIRED"

    stages = [
        {
            "stage": "OBSERVE",
            "status": "SIMULATED",
            "description": "validate objective, source provenance, policy, and supplied evidence references",
        },
        {
            "stage": "PRODUCE",
            "status": "SIMULATED",
            "description": action_policy.description,
        },
        {
            "stage": "VERIFY",
            "status": "SIMULATED",
            "description": "check truthfulness, target binding, cost, duplication, compliance, and evidence",
        },
        {
            "stage": "EXECUTE",
            "status": "BLOCKED_PERMISSION" if approval_required else "NOT_REQUESTED",
            "description": (
                "requires a server-side request-bound one-use permit"
                if approval_required
                else "planning tool performs no external or financial execution"
            ),
        },
    ]

    terminal_status = "BLOCKED" if approval_required else "PASS"
    body: dict[str, object] = {
        "schema_version": "aigc.wealth-work-plan.v1",
        "policy_id": active_policy.policy_id,
        "request": request.model_dump(mode="json"),
        "phase": action_policy.phase,
        "autonomy": assessment.model_dump(mode="json"),
        "stages": stages,
        "approval_packet": {
            "required": approval_required,
            "required_bindings": required_bindings,
            "missing_bindings": missing_bindings,
            "caller_supplied_authority_accepted": False,
        },
        "first_blocker": first_blocker,
        "terminal_status": terminal_status,
        "execution_may_continue_without_new_authority": assessment.execution_may_continue_without_new_authority,
        "zero_egress": True,
        "provider_calls_performed": 0,
        "authority_granted": False,
        "external_action_performed": False,
        "financial_action_performed": False,
        "profit_or_revenue_outcome_promised": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body
