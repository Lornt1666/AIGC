from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

from src.core.nexus.live_provider_runtime import (
    GovernedLiveNexusProviderRuntime,
    LiveProviderExecutionPolicy,
)
from src.core.nexus.provider_registry import ProviderRegistry
from src.core.nexus.provider_runtime import (
    InMemoryRuntimeControlStore,
    NexusProviderRuntime,
    ProviderExecutionBlocked,
    RuntimeControlHealth,
    RuntimeControlUnavailable,
    bind_provider_request_digest,
)
from src.domain.nexus.contracts import ExecutionPermit
from src.domain.nexus.provider_runtime import ProviderInvocation, ProviderRuntimeLimits
from src.infrastructure.providers.google_vertex_gemini import GoogleVertexGeminiAdapter
from src.infrastructure.providers.openai_responses import OpenAIResponsesAdapter
from src.infrastructure.providers.pricing import TokenPricing


NOW = datetime(2026, 8, 8, 5, 0, tzinfo=timezone.utc)
REVISION = "a" * 40


class DurableControlForTest(InMemoryRuntimeControlStore):
    def healthcheck(self):
        state = self.get_emergency_state()
        return RuntimeControlHealth(
            ok=True,
            durable=True,
            backend="test-durable-semantic-double",
            emergency_active=state.active,
            stop_epoch=state.stop_epoch,
        )


class GeminiUsage:
    prompt_token_count = 10
    candidates_token_count = 5
    total_token_count = 15


class GeminiCandidate:
    finish_reason = "STOP"


class GeminiResponse:
    text = "gemini governed result"
    usage_metadata = GeminiUsage()
    candidates = (GeminiCandidate(),)
    response_id = "gemini-response-fixture"


class GeminiModels:
    def __init__(self): self.calls = []
    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return GeminiResponse()


class GeminiClient:
    def __init__(self): self.models = GeminiModels()


class OpenAIUsage:
    input_tokens = 12
    output_tokens = 8
    total_tokens = 20


class OpenAIResponse:
    id = "resp_fixture"
    status = "completed"
    output_text = "openai governed result"
    usage = OpenAIUsage()


class OpenAIResponses:
    def __init__(self): self.calls = []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return OpenAIResponse()


class OpenAIClient:
    def __init__(self): self.responses = OpenAIResponses()


def pricing():
    return TokenPricing(
        input_cad_per_million=Decimal("1.00"),
        output_cad_per_million=Decimal("2.00"),
    )


def invocation(provider_id: str, model: str, *, key: str = "1") -> ProviderInvocation:
    value = ProviderInvocation(
        invocation_id=f"PINV-LIVE-{key}000001",
        request_id=f"TREQ-LIVE-{key}000001",
        change_set_id=f"CHG-LIVE-{key}000001",
        parent_state_hash="b" * 64,
        principal="principal:nexus-live-provider",
        provider_id=provider_id,
        capability="generate.text",
        model_or_resource=model,
        exact_revision=REVISION,
        request_digest="0" * 64,
        idempotency_key=(key * 64)[:64],
        reserved_usage_units=100,
        maximum_cost_cad=Decimal("0.01"),
        resource_ref=f"provider://{provider_id}/{model}",
        purpose="bounded governed provider canary",
        requested_effect_class="READ_EXTERNAL",
        input_payload="UNTRUSTED_PROVIDER_INPUT: produce one bounded test response",
        permit_id=f"PERMIT-LIVE-{key}000001",
    )
    return bind_provider_request_digest(value)


def permit(value: ProviderInvocation) -> ExecutionPermit:
    return ExecutionPermit(
        permit_id=value.permit_id,
        governance_decision_id="GOV-LIVE-PROVIDER01",
        principal=value.principal,
        capability=value.capability,
        resource_scope=(value.resource_ref,),
        exact_revision=value.exact_revision,
        change_set_hash="c" * 64,
        request_digest=value.request_digest,
        expires_at=NOW + timedelta(minutes=5),
        maximum_invocations=1,
    )


def limits():
    return ProviderRuntimeLimits(
        principal_invocations_per_minute=3,
        principal_invocations_per_day=10,
        global_invocations_per_minute=6,
        global_invocations_per_day=20,
        principal_reserved_usage_per_day=10000,
        global_reserved_usage_per_day=20000,
        maximum_usage_per_invocation=1000,
        maximum_cost_cad_per_invocation=Decimal("0.01"),
    )


def test_default_nexus_runtime_remains_fail_closed_for_live_provider():
    client = GeminiClient()
    adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-fixture",
        pricing=pricing(),
        client_factory=lambda: client,
    )
    runtime = NexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=InMemoryRuntimeControlStore(clock=lambda: NOW),
        limits=limits(),
    )
    value = invocation(adapter.provider_id, "gemini-fixture")
    with pytest.raises(ProviderExecutionBlocked, match="live providers are disabled"):
        runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert client.models.calls == []


def test_live_runtime_requires_durable_control_store():
    client = GeminiClient()
    adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-fixture",
        pricing=pricing(),
        client_factory=lambda: client,
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=InMemoryRuntimeControlStore(clock=lambda: NOW),
        limits=limits(),
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({adapter.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
        ),
    )
    value = invocation(adapter.provider_id, "gemini-fixture")
    with pytest.raises(RuntimeControlUnavailable, match="durable"):
        runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert client.models.calls == []


def test_vertex_gemini_adapter_executes_only_inside_live_runtime_with_actual_permit():
    client = GeminiClient()
    adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-fixture",
        pricing=pricing(),
        client_factory=lambda: client,
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=DurableControlForTest(clock=lambda: NOW),
        limits=limits(),
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({adapter.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
        ),
    )
    value = invocation(adapter.provider_id, "gemini-fixture")
    result = runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert result.attempt.status == "succeeded"
    assert result.attempt.response_payload == "gemini governed result"
    assert result.attempt.usage_units == 15
    assert result.attempt.cost_cad == Decimal("0.000020")
    assert result.receipt.external_action_performed is True
    assert result.audit.provider_api_calls_performed == 1
    assert result.audit.network_calls_performed == 1
    assert result.audit.credentials_used == 1
    assert result.audit.spend_cad == Decimal("0.000020")
    assert len(client.models.calls) == 1


def test_openai_adapter_uses_responses_store_false_and_never_serializes_key():
    client = OpenAIClient()
    secret = "sk-" + "fixture-project-key-not-real"
    adapter = OpenAIResponsesAdapter(
        model="gpt-fixture",
        pricing=pricing(),
        api_key_supplier=lambda: secret,
        client_factory=lambda supplied: client if supplied == secret else None,
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=DurableControlForTest(clock=lambda: NOW),
        limits=limits(),
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({adapter.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
        ),
    )
    value = invocation(adapter.provider_id, "gpt-fixture", key="2")
    result = runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert result.attempt.status == "succeeded"
    assert result.attempt.response_payload == "openai governed result"
    assert result.attempt.usage_units == 20
    assert result.attempt.cost_cad == Decimal("0.000028")
    assert result.receipt.external_action_performed is True
    assert client.responses.calls == [
        {
            "model": "gpt-fixture",
            "input": value.input_payload,
            "store": False,
        }
    ]
    serialized = json.dumps(
        {
            "invocation": value.model_dump(mode="json"),
            "permit": permit(value).model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        },
        sort_keys=True,
        default=str,
    )
    assert secret not in serialized


def test_live_adapter_unknown_outcome_becomes_indeterminate_and_not_retryable():
    class BrokenModels:
        def generate_content(self, **kwargs):
            raise OSError("uncertain transport")
    class BrokenClient:
        models = BrokenModels()

    adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-fixture",
        pricing=pricing(),
        client_factory=lambda: BrokenClient(),
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=DurableControlForTest(clock=lambda: NOW),
        limits=limits(),
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({adapter.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
        ),
    )
    value = invocation(adapter.provider_id, "gemini-fixture", key="3")
    result = runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert result.attempt.status == "indeterminate"
    assert result.attempt.outcome_known is False
    assert result.attempt.external_action_performed is True
    assert result.receipt.reconciliation_required is True
    assert result.receipt.operations[0].retryable is False
    assert result.audit.network_calls_performed == 1


def test_live_runtime_provider_allowlist_is_enforced_before_adapter_call():
    client = GeminiClient()
    adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-fixture",
        pricing=pricing(),
        client_factory=lambda: client,
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=DurableControlForTest(clock=lambda: NOW),
        limits=limits(),
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({"openai_responses"}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
        ),
    )
    value = invocation(adapter.provider_id, "gemini-fixture", key="4")
    with pytest.raises(ProviderExecutionBlocked, match="allowlist"):
        runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert client.models.calls == []
