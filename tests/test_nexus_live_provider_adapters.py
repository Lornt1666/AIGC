from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import inspect
import json

import pytest

from src.core.nexus.live_provider_runtime import (
    GovernedLiveNexusProviderRuntime,
    LiveProviderExecutionPolicy,
)
from src.core.nexus.provider_registry import ProviderAdapterError, ProviderRegistry
from src.core.nexus.provider_runtime import (
    InMemoryRuntimeControlStore,
    NexusProviderRuntime,
    ProviderExecutionBlocked,
    ProviderRuntimeError,
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


def invocation(
    provider_id: str,
    model: str,
    *,
    key: str = "1",
    maximum_input_units: int = 128,
    maximum_output_units: int = 128,
) -> ProviderInvocation:
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
        reserved_usage_units=256,
        maximum_input_units=maximum_input_units,
        maximum_output_units=maximum_output_units,
        request_timeout_seconds=30,
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
        model="gemini-2.5-flash",
        pricing=pricing(),
        client_factory=lambda: client,
    )
    runtime = NexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=InMemoryRuntimeControlStore(clock=lambda: NOW),
        limits=limits(),
    )
    value = invocation(adapter.provider_id, "gemini-2.5-flash")
    with pytest.raises(ProviderExecutionBlocked, match="live providers are disabled"):
        runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert client.models.calls == []


def test_live_runtime_requires_durable_control_store():
    client = GeminiClient()
    adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-2.5-flash",
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
    value = invocation(adapter.provider_id, "gemini-2.5-flash")
    with pytest.raises(RuntimeControlUnavailable, match="durable"):
        runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert client.models.calls == []


def test_vertex_gemini_adapter_executes_only_inside_live_runtime_with_actual_permit():
    client = GeminiClient()
    adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-2.5-flash",
        pricing=pricing(),
        client_factory=lambda: client,
    )
    store = DurableControlForTest(clock=lambda: NOW)
    runtime = GovernedLiveNexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=store,
        limits=limits(),
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({adapter.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
        ),
    )
    value = invocation(adapter.provider_id, "gemini-2.5-flash")
    result = runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert result.attempt.status == "succeeded"
    assert result.attempt.response_payload == "gemini governed result"
    assert result.attempt.usage_units == 15
    assert result.attempt.cost_cad == Decimal("0.000020")
    assert result.receipt.external_action_performed is True
    assert store.get_invocation(value.invocation_id).actual_usage_units == 15
    assert result.audit.provider_api_calls_performed == 1
    assert result.audit.network_calls_performed == 1
    assert result.audit.credentials_used == 1
    assert result.audit.spend_cad == Decimal("0.000020")
    assert len(client.models.calls) == 1
    config = client.models.calls[0]["config"]
    assert config["max_output_tokens"] == 128
    assert config["http_options"] == {
        "timeout": 30000,
        "retry_options": {"attempts": 1},
    }
    assert config["automatic_function_calling"] == {"disable": True}
    assert config["thinking_config"] == {
        "thinking_budget": 0,
        "include_thoughts": False,
    }


def test_gemini_thinking_tokens_are_output_usage_and_cost():
    class ThinkingUsage:
        prompt_token_count = 10
        candidates_token_count = 5
        thoughts_token_count = 100
        tool_use_prompt_token_count = 0
        total_token_count = 115

    class ThinkingResponse(GeminiResponse):
        usage_metadata = ThinkingUsage()

    client = GeminiClient()
    client.models.generate_content = lambda **_kwargs: ThinkingResponse()
    adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-2.5-flash",
        pricing=pricing(),
        client_factory=lambda: client,
    )
    attempt = adapter.invoke(invocation(adapter.provider_id, "gemini-2.5-flash"))
    assert attempt.status == "failed"
    assert attempt.finish_status == "gemini_unexpected_thinking"
    assert attempt.input_usage_units == 10
    assert attempt.output_usage_units == 105
    assert attempt.usage_units == 115
    assert attempt.cost_cad == Decimal("0.000220")


def test_gemini_usage_components_must_equal_provider_total():
    class InconsistentUsage(GeminiUsage):
        thoughts_token_count = 100
        total_token_count = 15

    class InconsistentResponse(GeminiResponse):
        usage_metadata = InconsistentUsage()

    client = GeminiClient()
    client.models.generate_content = lambda **_kwargs: InconsistentResponse()
    adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-2.5-flash",
        pricing=pricing(),
        client_factory=lambda: client,
    )
    attempt = adapter.invoke(invocation(adapter.provider_id, "gemini-2.5-flash"))
    assert attempt.status == "indeterminate"
    assert attempt.finish_status == "gemini_usage_total_mismatch"
    assert attempt.usage_units == 115
    assert attempt.cost_known is False


def test_openai_usage_components_must_equal_provider_total():
    class InconsistentUsage(OpenAIUsage):
        input_tokens = 10
        output_tokens = 5
        total_tokens = 115

    class InconsistentResponse(OpenAIResponse):
        usage = InconsistentUsage()

    client = OpenAIClient()
    client.responses.create = lambda **_kwargs: InconsistentResponse()
    adapter = OpenAIResponsesAdapter(
        model="gpt-fixture",
        pricing=pricing(),
        api_key_supplier=lambda: "test_only_openai_credential",
        client_factory=lambda _supplied: client,
    )
    attempt = adapter.invoke(invocation(adapter.provider_id, "gpt-fixture"))
    assert attempt.status == "indeterminate"
    assert attempt.finish_status == "openai_usage_total_mismatch"
    assert attempt.usage_units == 15
    assert attempt.cost_known is False


@pytest.mark.parametrize("provider", ["gemini", "openai"])
def test_adapter_rejects_worst_case_cost_before_credentials_or_client(provider):
    expensive = TokenPricing(
        input_cad_per_million=Decimal("10000.00"),
        output_cad_per_million=Decimal("10000.00"),
    )
    client_initializations = []
    credential_reads = []
    if provider == "gemini":
        client = GeminiClient()

        def gemini_client_factory():
            client_initializations.append(True)
            return client

        adapter = GoogleVertexGeminiAdapter(
            project="project-fixture",
            location="northamerica-northeast1",
            model="gemini-2.5-flash",
            pricing=expensive,
            client_factory=gemini_client_factory,
        )
        value = invocation(adapter.provider_id, "gemini-2.5-flash")
    else:
        client = OpenAIClient()

        def credential_supplier():
            credential_reads.append(True)
            return "test_only_openai_credential"

        adapter = OpenAIResponsesAdapter(
            model="gpt-fixture",
            pricing=expensive,
            api_key_supplier=credential_supplier,
            client_factory=lambda _supplied: client,
        )
        value = invocation(adapter.provider_id, "gpt-fixture")

    with pytest.raises(ProviderAdapterError, match="worst-case token cost") as raised:
        adapter.invoke(value)
    assert raised.value.attempted is False
    assert client_initializations == []
    assert credential_reads == []


def test_openai_adapter_uses_responses_store_false_and_never_serializes_key():
    client = OpenAIClient()
    credential_value = "sk-" + "fixture-project-key-not-real"
    adapter = OpenAIResponsesAdapter(
        model="gpt-fixture",
        pricing=pricing(),
        api_key_supplier=lambda: credential_value,
        client_factory=lambda supplied: client if supplied == credential_value else None,
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
            "max_output_tokens": 128,
            "store": False,
            "timeout": 30.0,
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
    assert credential_value not in serialized


def test_live_adapter_unknown_outcome_becomes_indeterminate_and_not_retryable():
    class BrokenModels:
        def generate_content(self, **kwargs):
            raise OSError("uncertain transport")
    class BrokenClient:
        models = BrokenModels()

    adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-2.5-flash",
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
    value = invocation(adapter.provider_id, "gemini-2.5-flash", key="3")
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
        model="gemini-2.5-flash",
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
    value = invocation(adapter.provider_id, "gemini-2.5-flash", key="4")
    with pytest.raises(ProviderExecutionBlocked, match="allowlist"):
        runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert client.models.calls == []


def test_live_runtime_terminalizes_usage_overrun_without_persisting_payload():
    class ExcessUsage(OpenAIUsage):
        input_tokens = 160
        output_tokens = 160
        total_tokens = 320

    class ExcessResponse(OpenAIResponse):
        output_text = "sensitive response that must not enter failure_reason"
        usage = ExcessUsage()

    class ExcessResponses(OpenAIResponses):
        def create(self, **kwargs):
            self.calls.append(kwargs)
            return ExcessResponse()

    client = OpenAIClient()
    client.responses = ExcessResponses()
    store = DurableControlForTest(clock=lambda: NOW)
    adapter = OpenAIResponsesAdapter(
        model="gpt-fixture",
        pricing=pricing(),
        api_key_supplier=lambda: "test_only_openai_credential",
        client_factory=lambda _supplied: client,
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=store,
        limits=limits(),
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({adapter.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
        ),
    )
    value = invocation(adapter.provider_id, "gpt-fixture", key="5")
    with pytest.raises(ProviderRuntimeError, match="reserved usage units"):
        runtime.execute(value, authoritative_now=NOW, permit=permit(value))

    reservation = store.get_invocation(value.invocation_id)
    assert reservation.state == "indeterminate"
    assert reservation.actual_usage_units == 320
    assert reservation.failure_reason == "POST_PROVIDER_VALIDATION_FAILED:ProviderRuntimeError"
    assert "sensitive response" not in reservation.failure_reason
    retained = store.get_execution_result(value.invocation_id)
    assert retained is not None
    assert retained.attempt.status == "indeterminate"
    assert retained.attempt.response_payload is None
    assert retained.attempt.usage_units == 320
    assert retained.audit.spend_cad == Decimal("0.000480")
    replay = runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert replay.replayed is True
    assert replay.attempt.status == "indeterminate"
    assert len(client.responses.calls) == 1


def test_provider_partial_finishes_never_satisfy_canary_success():
    openai_client = OpenAIClient()
    openai_client.responses = OpenAIResponses()
    incomplete = OpenAIResponse()
    incomplete.status = "incomplete"
    openai_client.responses.create = lambda **_kwargs: incomplete
    openai_adapter = OpenAIResponsesAdapter(
        model="gpt-fixture",
        pricing=pricing(),
        api_key_supplier=lambda: "test_only_openai_credential",
        client_factory=lambda _supplied: openai_client,
    )
    openai_attempt = openai_adapter.invoke(
        invocation(openai_adapter.provider_id, "gpt-fixture", key="6")
    )
    assert openai_attempt.status == "failed"
    assert openai_attempt.finish_status == "openai_incomplete"
    assert openai_attempt.response_payload is None

    class MaxTokenCandidate:
        finish_reason = "MAX_TOKENS"

    gemini_client = GeminiClient()
    response = GeminiResponse()
    response.candidates = (MaxTokenCandidate(),)
    gemini_client.models.generate_content = lambda **_kwargs: response
    gemini_adapter = GoogleVertexGeminiAdapter(
        project="project-fixture",
        location="northamerica-northeast1",
        model="gemini-2.5-flash",
        pricing=pricing(),
        client_factory=lambda: gemini_client,
    )
    gemini_attempt = gemini_adapter.invoke(
        invocation(gemini_adapter.provider_id, "gemini-2.5-flash", key="7")
    )
    assert gemini_attempt.status == "failed"
    assert gemini_attempt.finish_status == "gemini_max_tokens"
    assert gemini_attempt.response_payload is None


def test_production_openai_client_disables_sdk_retries():
    source = inspect.getsource(OpenAIResponsesAdapter._client)
    assert "max_retries=0" in source
    assert "timeout=float(timeout_seconds)" in source


def test_live_adapters_reject_unreserved_input_before_client_call():
    client = OpenAIClient()
    adapter = OpenAIResponsesAdapter(
        model="gpt-fixture",
        pricing=pricing(),
        api_key_supplier=lambda: "test_only_openai_credential",
        client_factory=lambda _supplied: client,
    )
    value = invocation(
        adapter.provider_id,
        "gpt-fixture",
        key="8",
        maximum_input_units=90,
    )
    with pytest.raises(ProviderAdapterError, match="input ceiling"):
        adapter.invoke(value)
    assert client.responses.calls == []


def test_invocation_rejects_usage_partition_above_total_reservation():
    value = invocation("openai_responses", "gpt-fixture", key="9")
    payload = value.model_dump(mode="python")
    payload["maximum_input_units"] = 200
    payload["maximum_output_units"] = 100
    with pytest.raises(ValueError, match="exceed reserved"):
        ProviderInvocation.model_validate(payload)


def test_provider_observed_model_mismatch_is_terminal_and_replayable():
    class DriftedResponse(OpenAIResponse):
        model = "gpt-unreviewed-drift"

    client = OpenAIClient()
    client.responses.create = lambda **_kwargs: DriftedResponse()
    store = DurableControlForTest(clock=lambda: NOW)
    adapter = OpenAIResponsesAdapter(
        model="gpt-fixture",
        pricing=pricing(),
        api_key_supplier=lambda: "test_only_openai_credential",
        client_factory=lambda _supplied: client,
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=store,
        limits=limits(),
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({adapter.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
        ),
    )
    value = invocation(adapter.provider_id, "gpt-fixture", key="0")
    with pytest.raises(ProviderRuntimeError, match="model/resource mismatch"):
        runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    retained = store.get_execution_result(value.invocation_id)
    assert retained is not None
    assert retained.attempt.status == "indeterminate"
    assert retained.attempt.model_or_resource == "gpt-fixture"
    assert retained.attempt.response_payload is None


def test_provider_usage_components_cannot_hide_behind_underreported_total():
    class UnderreportedUsage:
        input_tokens = 129
        output_tokens = 1
        total_tokens = 1

    class UnderreportedResponse(OpenAIResponse):
        usage = UnderreportedUsage()

    client = OpenAIClient()
    client.responses.create = lambda **_kwargs: UnderreportedResponse()
    store = DurableControlForTest(clock=lambda: NOW)
    adapter = OpenAIResponsesAdapter(
        model="gpt-fixture",
        pricing=pricing(),
        api_key_supplier=lambda: "test_only_openai_credential",
        client_factory=lambda _supplied: client,
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=store,
        limits=limits(),
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({adapter.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
        ),
    )
    value = invocation(adapter.provider_id, "gpt-fixture", key="1")
    with pytest.raises(ProviderRuntimeError, match="maximum input units"):
        runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    retained = store.get_execution_result(value.invocation_id)
    assert retained is not None
    assert retained.attempt.status == "indeterminate"
    assert retained.attempt.usage_units == 130
    assert retained.attempt.input_usage_units == 129
    assert retained.attempt.output_usage_units == 1
    assert retained.attempt.response_payload is None


@pytest.mark.parametrize("provider", ["openai", "gemini"])
def test_provider_http_error_after_dispatch_is_indeterminate_with_unknown_cost(provider):
    class ProviderHttpError(RuntimeError):
        status_code = 500
        code = 500

    if provider == "openai":
        class BrokenResponses:
            calls = 0

            def create(self, **_kwargs):
                self.calls += 1
                raise ProviderHttpError("server error after dispatch")

        client = OpenAIClient()
        client.responses = BrokenResponses()
        adapter = OpenAIResponsesAdapter(
            model="gpt-fixture",
            pricing=pricing(),
            api_key_supplier=lambda: "test_only_openai_credential",
            client_factory=lambda _supplied: client,
        )
        model = "gpt-fixture"
    else:
        class BrokenModels:
            calls = 0

            def generate_content(self, **_kwargs):
                self.calls += 1
                raise ProviderHttpError("server error after dispatch")

        client = GeminiClient()
        client.models = BrokenModels()
        adapter = GoogleVertexGeminiAdapter(
            project="project-fixture",
            location="northamerica-northeast1",
            model="gemini-2.5-flash",
            pricing=pricing(),
            client_factory=lambda: client,
        )
        model = "gemini-2.5-flash"
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
    value = invocation(adapter.provider_id, model, key="2" if provider == "openai" else "3")
    result = runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert result.attempt.status == "indeterminate"
    assert result.attempt.outcome_known is False
    assert result.attempt.cost_known is False
    assert result.audit.spend_known is False
    assert result.receipt.reconciliation_required is True
    assert client.responses.calls == 1 if provider == "openai" else client.models.calls == 1


def test_missing_usage_after_provider_response_requires_reconciliation():
    response = OpenAIResponse()
    response.usage = None
    client = OpenAIClient()
    client.responses.create = lambda **_kwargs: response
    adapter = OpenAIResponsesAdapter(
        model="gpt-fixture",
        pricing=pricing(),
        api_key_supplier=lambda: "test_only_openai_credential",
        client_factory=lambda _supplied: client,
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
    value = invocation(adapter.provider_id, "gpt-fixture", key="4")
    result = runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert result.attempt.status == "indeterminate"
    assert result.attempt.usage_units is None
    assert result.attempt.cost_known is False
    assert result.receipt.reconciliation_required is True


def test_finalization_failure_retains_redacted_measured_reconciliation_result():
    class CompletionRejectingStore(DurableControlForTest):
        def complete_invocation(self, **_kwargs):
            raise RuntimeControlUnavailable("simulated completion acknowledgement failure")

    client = OpenAIClient()
    store = CompletionRejectingStore(clock=lambda: NOW)
    adapter = OpenAIResponsesAdapter(
        model="gpt-fixture",
        pricing=pricing(),
        api_key_supplier=lambda: "test_only_openai_credential",
        client_factory=lambda _supplied: client,
    )
    runtime = GovernedLiveNexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=store,
        limits=limits(),
        execution_policy=LiveProviderExecutionPolicy(
            allowed_provider_ids=frozenset({adapter.provider_id}),
            allow_live_providers=True,
            allow_network=True,
            allow_credentials=True,
        ),
    )
    value = invocation(adapter.provider_id, "gpt-fixture", key="5")
    with pytest.raises(RuntimeControlUnavailable, match="acknowledgement"):
        runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    reservation = store.get_invocation(value.invocation_id)
    retained = store.get_execution_result(value.invocation_id)
    assert reservation.state == "indeterminate"
    assert reservation.actual_usage_units == 20
    assert retained is not None
    assert retained.attempt.status == "indeterminate"
    assert retained.attempt.usage_units == 20
    assert retained.attempt.cost_cad == Decimal("0.000028")
    assert retained.attempt.response_payload is None
    replay = runtime.execute(value, authoritative_now=NOW, permit=permit(value))
    assert replay.replayed is True
    assert replay.attempt.status == "indeterminate"
    assert len(client.responses.calls) == 1
