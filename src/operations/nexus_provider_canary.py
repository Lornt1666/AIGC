from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.live_provider_runtime import (
    GovernedLiveNexusProviderRuntime,
    LiveProviderExecutionPolicy,
)
from src.core.nexus.provider_registry import ProviderRegistry
from src.core.nexus.provider_runtime import bind_provider_request_digest
from src.domain.nexus.contracts import ExecutionPermit, GovernanceDecision
from src.domain.nexus.provider_runtime import ProviderInvocation, ProviderRuntimeLimits
from src.infrastructure.credentials.regional_secret_manager import (
    REGION,
    RegionalSecretManagerResolver,
)
from src.infrastructure.providers.google_vertex_gemini import GoogleVertexGeminiAdapter
from src.infrastructure.providers.openai_responses import OpenAIResponsesAdapter
from src.infrastructure.providers.pricing import TokenPricing
from src.infrastructure.runtime.postgres_control_store import PostgresRuntimeControlStore


class CanaryConfigurationError(RuntimeError):
    pass


class ProviderCanaryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["aigc.nexus-provider-canary.v1"] = "aigc.nexus-provider-canary.v1"
    provider_id: Literal["google_vertex_gemini", "openai_responses"]
    project_id: str = Field(min_length=6, max_length=30)
    location: str = REGION
    model: str = Field(min_length=1, max_length=200)
    exact_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    principal: str = Field(min_length=1, max_length=200)
    change_set_id: str = Field(pattern=r"^CHG-[A-Z0-9_-]{6,64}$")
    parent_state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    purpose: str = Field(min_length=1, max_length=2000)
    input_payload: str = Field(min_length=1, max_length=12000)
    reserved_usage_units: int = Field(ge=1, le=4096)
    maximum_cost_cad: Decimal = Field(gt=Decimal("0.00"), le=Decimal("5.00"))
    input_cad_per_million: Decimal = Field(ge=Decimal("0.00"))
    output_cad_per_million: Decimal = Field(ge=Decimal("0.00"))
    runtime_control_dsn_secret_ref: str = Field(min_length=1, max_length=1000)
    openai_api_key_secret_ref: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def provider_specific_requirements(self) -> "ProviderCanaryPlan":
        if self.location != REGION:
            raise ValueError(f"provider canary location must equal {REGION}")
        if self.provider_id == "openai_responses" and not self.openai_api_key_secret_ref:
            raise ValueError("OpenAI canary requires an exact regional API-key secret reference")
        if self.provider_id == "google_vertex_gemini" and self.openai_api_key_secret_ref is not None:
            raise ValueError("Gemini canary cannot carry an OpenAI secret reference")
        return self

    @property
    def resource_ref(self) -> str:
        return f"provider://{self.provider_id}/model/{self.model}"

    @property
    def capability(self) -> str:
        return "generate.text"


def _load_json(path: Path | None, env_name: str) -> dict:
    if path is not None:
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = os.environ.get(env_name, "").strip()
        if not raw:
            raise CanaryConfigurationError(f"{env_name} or a file argument is required")
        value = json.loads(raw)
    if not isinstance(value, dict):
        raise CanaryConfigurationError(f"{env_name} must decode to an object")
    return value


def _plan_seed(plan: ProviderCanaryPlan) -> str:
    return canonical_sha256(plan.model_dump(mode="json"))


def build_invocation(
    plan: ProviderCanaryPlan,
    *,
    permit_id: str | None = None,
) -> ProviderInvocation:
    seed = _plan_seed(plan)
    invocation = ProviderInvocation(
        invocation_id="PINV-CANARY-" + seed[:20].upper(),
        request_id="TREQ-CANARY-" + seed[20:40].upper(),
        change_set_id=plan.change_set_id,
        parent_state_hash=plan.parent_state_hash,
        principal=plan.principal,
        provider_id=plan.provider_id,
        capability=plan.capability,
        model_or_resource=plan.model,
        exact_revision=plan.exact_revision,
        request_digest="0" * 64,
        idempotency_key=canonical_sha256(
            {"canary_plan": plan.model_dump(mode="json"), "purpose": "provider-canary"}
        ),
        reserved_usage_units=plan.reserved_usage_units,
        maximum_cost_cad=plan.maximum_cost_cad,
        resource_ref=plan.resource_ref,
        purpose=plan.purpose,
        requested_effect_class="READ_EXTERNAL",
        input_payload=plan.input_payload,
        permit_id=None,
    )
    invocation = bind_provider_request_digest(invocation)
    if permit_id is not None:
        invocation = invocation.model_copy(update={"permit_id": permit_id})
    return invocation


def plan_receipt(plan: ProviderCanaryPlan) -> dict:
    invocation = build_invocation(plan)
    return {
        "schema_version": "aigc.nexus-provider-canary-plan.v1",
        "provider_id": plan.provider_id,
        "model": plan.model,
        "exact_revision": plan.exact_revision,
        "principal": plan.principal,
        "resource_ref": plan.resource_ref,
        "request_digest": invocation.request_digest,
        "idempotency_key": invocation.idempotency_key,
        "maximum_cost_cad": str(plan.maximum_cost_cad),
        "reserved_usage_units": plan.reserved_usage_units,
        "required_governance_condition": f"MAX_COST_CAD={plan.maximum_cost_cad}",
        "required_maximum_invocations": 1,
        "provider_call_performed": False,
        "network_call_performed": False,
        "credential_used": False,
    }


def _validate_authority(
    plan: ProviderCanaryPlan,
    invocation: ProviderInvocation,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
) -> None:
    if decision.decision != "approved":
        raise CanaryConfigurationError("provider canary requires an approved GovernanceDecision")
    if decision.authority_source != "HUMAN":
        raise CanaryConfigurationError("first live provider canary requires HUMAN governance authority")
    if permit.governance_decision_id != decision.decision_id:
        raise CanaryConfigurationError("ExecutionPermit is not bound to the supplied GovernanceDecision")
    if decision.exact_revision != plan.exact_revision or permit.exact_revision != plan.exact_revision:
        raise CanaryConfigurationError("provider canary exact revision authority mismatch")
    if permit.change_set_hash != decision.change_set_hash:
        raise CanaryConfigurationError("GovernanceDecision/ExecutionPermit ChangeSet hash mismatch")
    if permit.principal != plan.principal:
        raise CanaryConfigurationError("ExecutionPermit principal mismatch")
    if permit.capability != plan.capability:
        raise CanaryConfigurationError("ExecutionPermit capability mismatch")
    if plan.resource_ref not in permit.resource_scope:
        raise CanaryConfigurationError("ExecutionPermit does not contain exact provider resource scope")
    if permit.request_digest != invocation.request_digest:
        raise CanaryConfigurationError("ExecutionPermit request digest mismatch")
    if permit.maximum_invocations != 1:
        raise CanaryConfigurationError("provider canary ExecutionPermit must be one-use")
    required_cost = f"MAX_COST_CAD={plan.maximum_cost_cad}"
    if required_cost not in decision.conditions:
        raise CanaryConfigurationError("GovernanceDecision does not bind the exact canary cost ceiling")


def _adapter(plan: ProviderCanaryPlan, resolver: RegionalSecretManagerResolver):
    pricing = TokenPricing(
        input_cad_per_million=plan.input_cad_per_million,
        output_cad_per_million=plan.output_cad_per_million,
    )
    if plan.provider_id == "google_vertex_gemini":
        return GoogleVertexGeminiAdapter(
            project=plan.project_id,
            location=plan.location,
            model=plan.model,
            pricing=pricing,
        )
    if plan.openai_api_key_secret_ref is None:
        raise CanaryConfigurationError("OpenAI secret reference is missing")
    resolver.parse_reference(plan.openai_api_key_secret_ref)
    return OpenAIResponsesAdapter(
        model=plan.model,
        pricing=pricing,
        api_key_supplier=lambda: resolver.resolve_text(plan.openai_api_key_secret_ref or ""),
    )


def execute_canary(
    plan: ProviderCanaryPlan,
    *,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
    authoritative_now: datetime | None = None,
):
    now = authoritative_now or datetime.now(timezone.utc)
    invocation = build_invocation(plan, permit_id=permit.permit_id)
    _validate_authority(plan, invocation, decision, permit)

    resolver = RegionalSecretManagerResolver()
    resolver.parse_reference(plan.runtime_control_dsn_secret_ref)
    dsn = resolver.resolve_text(plan.runtime_control_dsn_secret_ref)
    try:
        control_store = PostgresRuntimeControlStore(dsn)
    finally:
        dsn = ""

    adapter = _adapter(plan, resolver)
    registry = ProviderRegistry((adapter,))
    limits = ProviderRuntimeLimits(
        principal_invocations_per_minute=1,
        principal_invocations_per_day=1,
        global_invocations_per_minute=1,
        global_invocations_per_day=1,
        principal_reserved_usage_per_day=plan.reserved_usage_units,
        global_reserved_usage_per_day=plan.reserved_usage_units,
        maximum_usage_per_invocation=plan.reserved_usage_units,
        maximum_cost_cad_per_invocation=plan.maximum_cost_cad,
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=registry,
        control_store=control_store,
        limits=limits,
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({plan.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
            require_durable_control_store=True,
        ),
    )
    result = runtime.execute(invocation, authoritative_now=now, permit=permit)
    safe_attempt = result.attempt.model_copy(update={"response_payload": None})
    safe_result = result.model_copy(update={"attempt": safe_attempt})
    return safe_result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--governance", type=Path)
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    plan = ProviderCanaryPlan.model_validate(_load_json(args.plan, "AIGC_CANARY_PLAN_JSON"))
    if args.plan_only:
        payload = plan_receipt(plan)
    else:
        decision = GovernanceDecision.model_validate(
            _load_json(args.governance, "AIGC_CANARY_GOVERNANCE_JSON")
        )
        permit = ExecutionPermit.model_validate(
            _load_json(args.permit, "AIGC_CANARY_PERMIT_JSON")
        )
        result = execute_canary(plan, decision=decision, permit=permit)
        payload = {
            "schema_version": "aigc.nexus-live-provider-canary-receipt.v1",
            "provider_id": plan.provider_id,
            "model": plan.model,
            "exact_revision": plan.exact_revision,
            "invocation_id": result.invocation_id,
            "attempt": result.attempt.model_dump(mode="json"),
            "receipt": result.receipt.model_dump(mode="json"),
            "audit": result.audit.model_dump(mode="json"),
            "replayed": result.replayed,
            "response_payload_retained": False,
        }

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("AIGC_CANARY_RECEIPT:" + encoded)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CanaryConfigurationError, ValueError) as exc:
        raise SystemExit(f"Nexus provider canary blocked: {exc}") from exc
