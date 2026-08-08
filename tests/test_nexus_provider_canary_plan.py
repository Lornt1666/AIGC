from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.domain.nexus.contracts import ExecutionPermit, GovernanceDecision
from src.operations.nexus_provider_canary import (
    CanaryConfigurationError,
    ProviderCanaryPlan,
    _validate_authority,
    build_invocation,
    plan_receipt,
)


REVISION = "a" * 40
STATE_HASH = "b" * 64
CHANGE_HASH = "c" * 64
REPORT_HASH = "d" * 64
DSN_REF = "projects/aigc-stage/locations/northamerica-northeast1/secrets/runtime-control-dsn/versions/7"
OPENAI_REF = "projects/aigc-stage/locations/northamerica-northeast1/secrets/openai-api-key/versions/3"
NOW = datetime(2026, 8, 8, 14, 0, tzinfo=timezone.utc)


def plan(provider: str = "google_vertex_gemini") -> ProviderCanaryPlan:
    return ProviderCanaryPlan(
        provider_id=provider,
        project_id="aigc-stage",
        location="northamerica-northeast1",
        model="example-model",
        exact_revision=REVISION,
        principal="operator:aigc-canary",
        change_set_id="CHG-CANARY001",
        parent_state_hash=STATE_HASH,
        purpose="One governed provider canary",
        input_payload="Return exactly: AIGC CANARY OK",
        reserved_usage_units=128,
        maximum_cost_cad=Decimal("0.05"),
        input_cad_per_million=Decimal("1.00"),
        output_cad_per_million=Decimal("2.00"),
        runtime_control_dsn_secret_ref=DSN_REF,
        openai_api_key_secret_ref=OPENAI_REF if provider == "openai_responses" else None,
    )


def authority(plan_value: ProviderCanaryPlan):
    invocation = build_invocation(plan_value)
    decision = GovernanceDecision(
        decision_id="GOV-CANARY001",
        decision="approved",
        authority_source="HUMAN",
        authority_actor="operator:test",
        artifact_state_hash=STATE_HASH,
        change_set_hash=CHANGE_HASH,
        verifier_report_hash=REPORT_HASH,
        exact_revision=REVISION,
        conditions=("MAX_COST_CAD=0.05",),
        expires_at=NOW + timedelta(minutes=10),
    )
    permit = ExecutionPermit(
        permit_id="PERMIT-CANARY001",
        governance_decision_id=decision.decision_id,
        principal=plan_value.principal,
        capability=plan_value.capability,
        resource_scope=(plan_value.resource_ref,),
        exact_revision=REVISION,
        change_set_hash=CHANGE_HASH,
        request_digest=invocation.request_digest,
        expires_at=NOW + timedelta(minutes=5),
        maximum_invocations=1,
    )
    return invocation, decision, permit


def test_canary_plan_is_deterministic_and_performs_no_provider_work():
    first = plan_receipt(plan())
    second = plan_receipt(plan())
    assert first == second
    assert first["provider_call_performed"] is False
    assert first["network_call_performed"] is False
    assert first["credential_used"] is False
    assert first["required_maximum_invocations"] == 1
    assert first["required_governance_condition"] == "MAX_COST_CAD=0.05"


def test_canary_requires_exact_regional_secret_versions():
    with pytest.raises(ValueError):
        ProviderCanaryPlan(
            **{
                **plan().model_dump(),
                "runtime_control_dsn_secret_ref": "projects/aigc-stage/secrets/runtime/versions/latest",
            }
        )


def test_openai_plan_requires_separate_exact_api_key_reference():
    with pytest.raises(ValueError, match="OpenAI canary requires"):
        ProviderCanaryPlan(**{**plan("openai_responses").model_dump(), "openai_api_key_secret_ref": None})


def test_canonical_human_decision_and_one_use_permit_bind_canary():
    p = plan()
    invocation, decision, permit = authority(p)
    _validate_authority(p, invocation, decision, permit)


def test_wrong_cost_condition_is_rejected_before_provider_execution():
    p = plan()
    invocation, decision, permit = authority(p)
    wrong = decision.model_copy(update={"conditions": ("MAX_COST_CAD=0.10",)})
    with pytest.raises(CanaryConfigurationError, match="cost ceiling"):
        _validate_authority(p, invocation, wrong, permit)


def test_reusable_permit_is_rejected_for_first_live_canary():
    p = plan()
    invocation, decision, permit = authority(p)
    reusable = permit.model_copy(update={"maximum_invocations": 2})
    with pytest.raises(CanaryConfigurationError, match="one-use"):
        _validate_authority(p, invocation, decision, reusable)
