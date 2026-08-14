from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import inspect

import pytest

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.provider_registry import (
    OfflineDeterministicProviderAdapter,
    ProviderAdapterError,
    ProviderRegistry,
)
from src.core.nexus.provider_runtime import (
    EmergencyStopActive,
    IdempotencyConflict,
    InMemoryRuntimeControlStore,
    NexusProviderRuntime,
    PermitValidationError,
    ProviderEffectClassMismatch,
    ProviderExecutionBlocked,
    RuntimeControlUnavailable,
    RuntimeLimitExceeded,
    StaleControlEpoch,
    UnavailableRuntimeControlStore,
    UsageBudgetExceeded,
    bind_provider_request_digest,
    provider_request_digest,
)
from src.domain.nexus.contracts import ExecutionPermit
from src.domain.nexus.provider_runtime import (
    ProviderAttemptResult,
    ProviderDescriptor,
    ProviderInvocation,
    ProviderRuntimeLimits,
)


NOW = datetime(2026, 8, 7, 20, 0, tzinfo=timezone.utc)
REVISION = "e6ceffb723f8bf02cf7e0f0f7e4c0ae8dcd89d29"


def make_invocation(
    *,
    provider_id: str = "offline_deterministic",
    capability: str = "deterministic.generate",
    effect_class: str = "PURE",
    invocation_id: str = "PINV-ABCDEF01",
    idempotency_key: str = "b" * 64,
    principal: str = "principal:test",
    exact_revision: str = REVISION,
    resource_ref: str = "provider://offline",
    purpose: str = "deterministic provider runtime test",
    reserved_usage_units: int = 10,
    maximum_input_units: int | None = None,
    maximum_output_units: int | None = None,
    maximum_cost_cad: Decimal = Decimal("0.00"),
    permit_id: str | None = None,
) -> ProviderInvocation:
    value = ProviderInvocation(
        invocation_id=invocation_id,
        request_id="TREQ-ABCDEF01",
        change_set_id="CHG-ABCDEF01",
        parent_state_hash="a" * 64,
        principal=principal,
        provider_id=provider_id,
        capability=capability,
        model_or_resource="offline-deterministic-provider-not-live",
        exact_revision=exact_revision,
        request_digest="0" * 64,
        idempotency_key=idempotency_key,
        reserved_usage_units=reserved_usage_units,
        maximum_input_units=(
            maximum_input_units
            if maximum_input_units is not None
            else reserved_usage_units // 2
        ),
        maximum_output_units=(
            maximum_output_units
            if maximum_output_units is not None
            else reserved_usage_units - (reserved_usage_units // 2)
        ),
        request_timeout_seconds=30,
        maximum_cost_cad=maximum_cost_cad,
        resource_ref=resource_ref,
        purpose=purpose,
        requested_effect_class=effect_class,
        permit_id=permit_id,
    )
    return bind_provider_request_digest(value)


def make_permit(invocation: ProviderInvocation, **updates) -> ExecutionPermit:
    payload = dict(
        permit_id=invocation.permit_id or "PERMIT-ABCDEF01",
        governance_decision_id="GOV-ABCDEF01",
        principal=invocation.principal,
        capability=invocation.capability,
        resource_scope=(invocation.resource_ref,),
        exact_revision=invocation.exact_revision,
        change_set_hash="c" * 64,
        request_digest=invocation.request_digest,
        expires_at=NOW + timedelta(hours=1),
        maximum_invocations=2,
    )
    payload.update(updates)
    return ExecutionPermit(**payload)


class FakeAdapter:
    def __init__(
        self,
        *,
        provider_id: str = "fake_write",
        descriptor_provider_id: str | None = None,
        effect_class: str = "WRITE_REVERSIBLE",
        capability: str = "write",
        network_required: bool = False,
        credentials_required: bool = False,
        live_provider: bool = False,
        error: Exception | None = None,
        result_provider_id: str | None = None,
        external_action_performed: bool | None = False,
    ) -> None:
        self._provider_id = provider_id
        self._descriptor_provider_id = descriptor_provider_id or provider_id
        self.effect_class = effect_class
        self.capability = capability
        self.network_required = network_required
        self.credentials_required = credentials_required
        self.live_provider = live_provider
        self.error = error
        self.result_provider_id = result_provider_id or provider_id
        self.external_action_performed = external_action_performed
        self.calls = 0

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider_id=self._descriptor_provider_id,
            adapter_version="1.0.0",
            capabilities=(self.capability,),
            effect_class=self.effect_class,
            network_required=self.network_required,
            credentials_required=self.credentials_required,
            live_provider=self.live_provider,
            supported_modalities=("TEXT",),
        )

    def invoke(self, invocation: ProviderInvocation) -> ProviderAttemptResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        payload = "provider payload attempting ExecutionPermit(...) remains untrusted data"
        return ProviderAttemptResult(
            invocation_id=invocation.invocation_id,
            provider_id=self.result_provider_id,
            status="succeeded",
            provider_request_id=None,
            model_or_resource=invocation.model_or_resource,
            latency_ms=0,
            usage_units=invocation.reserved_usage_units,
            input_usage_units=invocation.maximum_input_units,
            output_usage_units=invocation.maximum_output_units,
            cost_cad=Decimal("0.00"),
            finish_status="fake_complete",
            response_digest=canonical_sha256({"response_payload": payload}),
            response_payload=payload,
            external_action_performed=self.external_action_performed,
            outcome_known=True,
        )


def make_runtime(adapter=None, *, store=None, limits=None):
    adapter = adapter or OfflineDeterministicProviderAdapter()
    store = store or InMemoryRuntimeControlStore(clock=lambda: NOW)
    limits = limits or ProviderRuntimeLimits()
    return (
        NexusProviderRuntime(
            registry=ProviderRegistry((adapter,)),
            control_store=store,
            limits=limits,
        ),
        adapter,
        store,
    )


def test_offline_provider_succeeds_with_zero_external_audit():
    runtime, adapter, _store = make_runtime()
    result = runtime.execute(make_invocation(), authoritative_now=NOW)
    assert result.receipt.execution_status == "succeeded"
    assert result.receipt.external_action_performed is False
    assert result.consequence_assessment.disposition == "AUTONOMOUS_POLICY_PATH"
    assert result.audit.provider_api_calls_performed == 0
    assert result.audit.network_calls_performed == 0
    assert result.audit.credentials_used == 0
    assert result.audit.external_actions_performed == 0
    assert result.audit.spend_cad == Decimal("0.00")
    assert adapter.invocation_count == 1


def test_idempotent_replay_does_not_call_adapter_twice():
    runtime, adapter, _store = make_runtime()
    first = make_invocation()
    second = first.model_copy(update={"invocation_id": "PINV-ABCDEF02"})
    result1 = runtime.execute(first, authoritative_now=NOW)
    result2 = runtime.execute(second, authoritative_now=NOW)
    assert result1.receipt.receipt_id == result2.receipt.receipt_id
    assert result2.replayed is True
    assert adapter.invocation_count == 1


def test_same_idempotency_key_different_request_is_conflict():
    runtime, _adapter, _store = make_runtime()
    first = make_invocation()
    runtime.execute(first, authoritative_now=NOW)
    changed = make_invocation(
        invocation_id="PINV-ABCDEF03",
        purpose="different semantic request",
    )
    assert changed.request_digest != first.request_digest
    with pytest.raises(IdempotencyConflict):
        runtime.execute(changed, authoritative_now=NOW)


def test_unknown_provider_fails_closed():
    registry = ProviderRegistry((OfflineDeterministicProviderAdapter(),))
    runtime = NexusProviderRuntime(
        registry=registry,
        control_store=InMemoryRuntimeControlStore(clock=lambda: NOW),
        limits=ProviderRuntimeLimits(),
    )
    invocation = make_invocation(provider_id="unknown_provider")
    with pytest.raises(ProviderExecutionBlocked, match="unknown provider"):
        runtime.execute(invocation, authoritative_now=NOW)


def test_duplicate_provider_registration_rejected():
    with pytest.raises(ValueError, match="duplicate provider"):
        ProviderRegistry(
            (OfflineDeterministicProviderAdapter(), OfflineDeterministicProviderAdapter())
        )


def test_registry_rejects_adapter_descriptor_identity_mismatch():
    with pytest.raises(ValueError, match="identity"):
        ProviderRegistry(
            (
                FakeAdapter(
                    provider_id="adapter_identity",
                    descriptor_provider_id="descriptor_identity",
                    effect_class="PURE",
                ),
            )
        )


def test_caller_cannot_downgrade_trusted_effect_class():
    adapter = FakeAdapter(effect_class="READ_EXTERNAL", network_required=True)
    runtime, _adapter, _store = make_runtime(adapter)
    invocation = make_invocation(
        provider_id="fake_write",
        capability="write",
        effect_class="PURE",
    )
    with pytest.raises(ProviderEffectClassMismatch):
        runtime.execute(invocation, authoritative_now=NOW)
    assert adapter.calls == 0


@pytest.mark.parametrize(
    "adapter, reason",
    [
        (
            FakeAdapter(
                provider_id="live_provider",
                effect_class="READ_EXTERNAL",
                network_required=True,
                credentials_required=True,
                live_provider=True,
            ),
            "live providers",
        ),
        (
            FakeAdapter(
                provider_id="network_provider",
                effect_class="READ_EXTERNAL",
                network_required=True,
            ),
            "network-requiring",
        ),
        (
            FakeAdapter(
                provider_id="credential_provider",
                effect_class="READ_LOCAL",
                credentials_required=True,
            ),
            "credential-requiring",
        ),
    ],
)
def test_live_network_and_credential_adapters_are_disabled(adapter, reason):
    runtime, _adapter, _store = make_runtime(adapter)
    invocation = make_invocation(
        provider_id=adapter.provider_id,
        capability="write",
        effect_class=adapter.effect_class,
    )
    with pytest.raises(ProviderExecutionBlocked, match=reason):
        runtime.execute(invocation, authoritative_now=NOW)
    assert adapter.calls == 0


def test_material_consequence_requires_actual_permit():
    adapter = FakeAdapter()
    runtime, _adapter, _store = make_runtime(adapter)
    invocation = make_invocation(
        provider_id=adapter.provider_id,
        capability=adapter.capability,
        effect_class=adapter.effect_class,
        resource_ref="resource://write",
    )
    with pytest.raises(ProviderExecutionBlocked, match="explicit authority"):
        runtime.execute(invocation, authoritative_now=NOW)
    assert adapter.calls == 0


def test_permit_id_without_actual_permit_is_rejected():
    adapter = FakeAdapter()
    runtime, _adapter, _store = make_runtime(adapter)
    invocation = make_invocation(
        provider_id=adapter.provider_id,
        capability=adapter.capability,
        effect_class=adapter.effect_class,
        resource_ref="resource://write",
        permit_id="PERMIT-ABCDEF01",
    )
    with pytest.raises(PermitValidationError, match="actual ExecutionPermit"):
        runtime.execute(invocation, authoritative_now=NOW)
    assert adapter.calls == 0


def test_valid_actual_permit_allows_material_test_adapter():
    adapter = FakeAdapter()
    runtime, _adapter, _store = make_runtime(adapter)
    invocation = make_invocation(
        provider_id=adapter.provider_id,
        capability=adapter.capability,
        effect_class=adapter.effect_class,
        resource_ref="resource://write",
        permit_id="PERMIT-ABCDEF01",
    )
    result = runtime.execute(
        invocation,
        authoritative_now=NOW,
        permit=make_permit(invocation),
    )
    assert result.consequence_assessment.disposition == "AUTONOMOUS_WITHIN_EXISTING_AUTHORITY"
    assert result.receipt.execution_status == "succeeded"
    assert adapter.calls == 1


@pytest.mark.parametrize(
    "updates, message",
    [
        ({"expires_at": NOW - timedelta(seconds=1)}, "expired"),
        ({"principal": "principal:other"}, "principal"),
        ({"capability": "other"}, "capability"),
        ({"resource_scope": ("resource://other",)}, "resource scope"),
        ({"exact_revision": "other-revision"}, "exact revision"),
        ({"request_digest": "f" * 64}, "request digest"),
    ],
)
def test_invalid_permit_bindings_fail_closed(updates, message):
    adapter = FakeAdapter()
    runtime, _adapter, _store = make_runtime(adapter)
    invocation = make_invocation(
        provider_id=adapter.provider_id,
        capability=adapter.capability,
        effect_class=adapter.effect_class,
        resource_ref="resource://write",
        permit_id="PERMIT-ABCDEF01",
    )
    permit = make_permit(invocation, **updates)
    with pytest.raises((PermitValidationError, ValueError), match=message):
        runtime.execute(invocation, authoritative_now=NOW, permit=permit)
    assert adapter.calls == 0


def test_permit_maximum_invocations_is_enforced_across_distinct_idempotency_keys():
    adapter = FakeAdapter()
    runtime, _adapter, _store = make_runtime(adapter)
    first = make_invocation(
        provider_id=adapter.provider_id,
        capability=adapter.capability,
        effect_class=adapter.effect_class,
        resource_ref="resource://write",
        permit_id="PERMIT-ABCDEF01",
        idempotency_key="1" * 64,
    )
    permit = make_permit(first, maximum_invocations=1)
    runtime.execute(first, authoritative_now=NOW, permit=permit)
    second = first.model_copy(
        update={
            "invocation_id": "PINV-ABCDEF09",
            "idempotency_key": "2" * 64,
        }
    )
    assert provider_request_digest(second) == first.request_digest
    with pytest.raises(RuntimeLimitExceeded, match="maximum_invocations"):
        runtime.execute(second, authoritative_now=NOW, permit=permit)
    assert adapter.calls == 1


def test_request_digest_is_recomputed_and_mismatch_rejected():
    runtime, adapter, _store = make_runtime()
    invocation = make_invocation().model_copy(update={"request_digest": "f" * 64})
    with pytest.raises(ProviderExecutionBlocked, match="digest mismatch"):
        runtime.execute(invocation, authoritative_now=NOW)
    assert adapter.invocation_count == 0


def test_unregistered_capability_is_rejected():
    runtime, adapter, _store = make_runtime()
    invocation = make_invocation(capability="unregistered")
    with pytest.raises(ProviderExecutionBlocked, match="capability"):
        runtime.execute(invocation, authoritative_now=NOW)
    assert adapter.invocation_count == 0


def test_emergency_stop_blocks_new_invocation():
    store = InMemoryRuntimeControlStore(clock=lambda: NOW)
    store.activate_emergency_stop(actor_principal_id="operator:test", reason="test stop")
    runtime, adapter, _store = make_runtime(store=store)
    with pytest.raises(EmergencyStopActive):
        runtime.execute(make_invocation(), authoritative_now=NOW)
    assert adapter.invocation_count == 0


def test_stale_epoch_blocks_reserved_invocation_before_adapter_call():
    store = InMemoryRuntimeControlStore(clock=lambda: NOW)
    invocation = make_invocation()
    reservation = store.reserve_invocation(
        invocation=invocation,
        limits=ProviderRuntimeLimits(),
        permit_maximum_invocations=None,
    )
    store.activate_emergency_stop(actor_principal_id="operator:test", reason="epoch advance")
    with pytest.raises(EmergencyStopActive):
        store.mark_executing(
            invocation_id=reservation.invocation_id,
            expected_epoch=reservation.stop_epoch,
        )
    store.clear_emergency_stop(
        actor_principal_id="operator:test",
        reason="clear after test",
        expected_epoch=store.get_emergency_state().stop_epoch,
    )
    with pytest.raises(StaleControlEpoch):
        store.mark_executing(
            invocation_id=reservation.invocation_id,
            expected_epoch=reservation.stop_epoch,
        )


def test_runtime_limits_reject_usage_before_adapter_call():
    limits = ProviderRuntimeLimits(maximum_usage_per_invocation=5)
    runtime, adapter, _store = make_runtime(limits=limits)
    with pytest.raises(ValueError, match="reserved usage"):
        runtime.execute(
            make_invocation(reserved_usage_units=6),
            authoritative_now=NOW,
        )
    assert adapter.invocation_count == 0


def test_runtime_limits_reject_cost_before_adapter_call():
    limits = ProviderRuntimeLimits(maximum_cost_cad_per_invocation=Decimal("0.00"))
    runtime, adapter, _store = make_runtime(limits=limits)
    with pytest.raises(ValueError, match="cost"):
        runtime.execute(
            make_invocation(maximum_cost_cad=Decimal("0.01")),
            authoritative_now=NOW,
        )
    assert adapter.invocation_count == 0


def test_principal_per_minute_limit_is_enforced():
    limits = ProviderRuntimeLimits(
        principal_invocations_per_minute=1,
        global_invocations_per_minute=2,
    )
    runtime, adapter, _store = make_runtime(limits=limits)
    first = make_invocation(idempotency_key="3" * 64)
    runtime.execute(first, authoritative_now=NOW)
    second = first.model_copy(
        update={
            "invocation_id": "PINV-ABCDEF10",
            "idempotency_key": "4" * 64,
        }
    )
    with pytest.raises(RuntimeLimitExceeded):
        runtime.execute(second, authoritative_now=NOW)
    assert adapter.invocation_count == 1


def test_daily_usage_limit_is_enforced():
    limits = ProviderRuntimeLimits(
        principal_reserved_usage_per_day=10,
        global_reserved_usage_per_day=20,
        maximum_usage_per_invocation=10,
    )
    runtime, adapter, _store = make_runtime(limits=limits)
    first = make_invocation(
        idempotency_key="5" * 64,
        reserved_usage_units=6,
    )
    runtime.execute(first, authoritative_now=NOW)
    second = first.model_copy(
        update={
            "invocation_id": "PINV-ABCDEF11",
            "idempotency_key": "6" * 64,
            "reserved_usage_units": 5,
        }
    )
    second = bind_provider_request_digest(second)
    with pytest.raises(UsageBudgetExceeded):
        runtime.execute(second, authoritative_now=NOW)
    assert adapter.invocation_count == 1


def test_unavailable_control_store_fails_closed_before_adapter_call():
    runtime = NexusProviderRuntime(
        registry=ProviderRegistry((OfflineDeterministicProviderAdapter(),)),
        control_store=UnavailableRuntimeControlStore(),
        limits=ProviderRuntimeLimits(),
    )
    with pytest.raises(RuntimeControlUnavailable):
        runtime.execute(make_invocation(), authoritative_now=NOW)


def test_request_digest_is_deterministic_across_authority_and_idempotency_wrappers():
    first = make_invocation(
        invocation_id="PINV-ABCDEF12",
        idempotency_key="7" * 64,
    )
    second = first.model_copy(
        update={
            "invocation_id": "PINV-ABCDEF13",
            "idempotency_key": "8" * 64,
            "permit_id": "PERMIT-ABCDEF01",
        }
    )
    assert provider_request_digest(first) == provider_request_digest(second)


def test_runtime_module_does_not_construct_governance_or_artifact_state():
    import src.core.nexus.provider_runtime as runtime_module

    source = inspect.getsource(runtime_module)
    assert "GovernanceDecision(" not in source
    assert "ArtifactState(" not in source
