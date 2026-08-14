from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from src.core.nexus.articulation_controller import ArticulationController, ContributionRequest
from src.core.nexus.provider_contribution_resolver import (
    GovernedProviderContributionResolver,
    ProviderContributionRoute,
)
from src.core.nexus.provider_registry import OfflineDeterministicProviderAdapter, ProviderRegistry
from src.core.nexus.provider_runtime import InMemoryRuntimeControlStore, NexusProviderRuntime
from src.domain.nexus.articulation import ArticulationBudget
from src.domain.nexus.contracts import ChangeSet, ContextEnvelope, WorkOrder
from src.domain.nexus.provider_runtime import ProviderInvocation, ProviderRuntimeLimits


NOW = datetime(2026, 8, 8, 0, 0, tzinfo=timezone.utc)
REVISION = "020c56483a52365b9afb7ab6acb95fc758a10e8a"
SESSION_ID = "ART-RESOLVER01"


def make_bound_context():
    work_order = WorkOrder(
        work_order_id="WO-RESOLVER01",
        objective="prove governed provider contribution resolution",
    )
    context = ContextEnvelope(
        context_id="CTX-RESOLVER01",
        work_order_id=work_order.work_order_id,
        state_hash="a" * 64,
    )
    change_set = ChangeSet(
        change_set_id="CHG-RESOLVER01",
        work_order_id=work_order.work_order_id,
        parent_state_hash=context.state_hash,
        producer_agent_id="nexus-provider-contribution-resolver",
    )
    return work_order, context, change_set


def make_route(route_key: str, *, prompt: str | None = None, uncertainty: float = 0.1):
    return ProviderContributionRoute(
        route_key=route_key,
        provider_id="offline_deterministic",
        capability="deterministic.generate",
        model_or_resource="offline-deterministic-provider-not-live",
        resource_ref=f"provider://offline/{route_key}",
        purpose=f"resolve articulation contribution {route_key}",
        bounded_prompt=prompt or f"Produce deterministic contribution for {route_key}.",
        reserved_usage_units=32,
        maximum_cost_cad=Decimal("0.00"),
        requested_effect_class="PURE",
        uncertainty=uncertainty,
    )


def make_runtime(adapter: OfflineDeterministicProviderAdapter | None = None):
    adapter = adapter or OfflineDeterministicProviderAdapter()
    runtime = NexusProviderRuntime(
        registry=ProviderRegistry((adapter,)),
        control_store=InMemoryRuntimeControlStore(clock=lambda: NOW),
        limits=ProviderRuntimeLimits(
            principal_invocations_per_minute=10,
            global_invocations_per_minute=20,
            maximum_usage_per_invocation=1024,
        ),
    )
    return runtime, adapter


def make_resolver(*routes: ProviderContributionRoute, adapter=None, clock=lambda: NOW):
    work_order, context, change_set = make_bound_context()
    runtime, adapter = make_runtime(adapter)
    resolver = GovernedProviderContributionResolver(
        work_order=work_order,
        context=context,
        change_set=change_set,
        principal="principal:nexus-articulation",
        exact_revision=REVISION,
        session_id=SESSION_ID,
        runtime=runtime,
        authoritative_clock=clock,
        routes=tuple(routes),
    )
    return resolver, adapter, work_order, context, change_set


def make_request(
    route_key: str,
    *,
    round_id: int = 1,
    role: str = "PROPOSER",
    response_type: str = "PROPOSAL",
    parents: tuple[str, ...] = (),
):
    return ContributionRequest(
        fixture_key=route_key,
        session_id=SESSION_ID,
        round_id=round_id,
        role=role,
        response_type=response_type,
        parent_message_ids=parents,
        created_at=NOW,
        repository_context_id=None,
    )


def articulation_budget():
    return ArticulationBudget(
        maximum_rounds=3,
        maximum_contributions=10,
        maximum_tokens=20000,
        maximum_cost_cad=Decimal("0.00"),
        maximum_elapsed_seconds=30,
        live_calls_allowed=False,
    )


def test_provider_invocation_input_payload_is_backward_compatible():
    invocation = ProviderInvocation(
        invocation_id="PINV-BACKWARD01",
        request_id="TREQ-BACKWARD01",
        change_set_id="CHG-BACKWARD01",
        parent_state_hash="a" * 64,
        principal="principal:test",
        provider_id="offline_deterministic",
        capability="deterministic.generate",
        model_or_resource="offline-deterministic-provider-not-live",
        exact_revision=REVISION,
        request_digest="b" * 64,
        idempotency_key="c" * 64,
        reserved_usage_units=1,
        maximum_cost_cad=Decimal("0.00"),
        resource_ref="provider://offline",
        purpose="backward compatibility",
        requested_effect_class="PURE",
    )
    assert invocation.input_payload == ""


def test_build_invocation_binds_untrusted_input_and_trusted_nexus_context():
    route = make_route("route_a", prompt="Analyze architecture A.")
    resolver, _adapter, _work_order, context, change_set = make_resolver(route)
    invocation = resolver.build_invocation(make_request("route_a"))

    assert invocation.change_set_id == change_set.change_set_id
    assert invocation.parent_state_hash == context.state_hash
    assert invocation.principal == "principal:nexus-articulation"
    assert invocation.exact_revision == REVISION
    assert invocation.provider_id == "offline_deterministic"
    assert invocation.requested_effect_class == "PURE"
    assert invocation.permit_id is None
    assert "UNTRUSTED_PROVIDER_INPUT" in invocation.input_payload
    assert "Analyze architecture A." in invocation.input_payload
    assert invocation.request_digest != "0" * 64


def test_provider_input_changes_request_and_response_digests():
    resolver_a, _adapter_a, *_ = make_resolver(make_route("route_a", prompt="alpha"))
    resolver_b, _adapter_b, *_ = make_resolver(make_route("route_a", prompt="beta"))
    request = make_request("route_a")

    invocation_a = resolver_a.build_invocation(request)
    invocation_b = resolver_b.build_invocation(request)
    assert invocation_a.request_digest != invocation_b.request_digest

    contribution_a = resolver_a.resolve(request)
    contribution_b = resolver_b.resolve(request)
    assert contribution_a.content != contribution_b.content
    assert "alpha" in contribution_a.content
    assert "beta" in contribution_b.content


def test_successful_runtime_execution_drives_fixture_contribution_and_receipt_evidence():
    resolver, adapter, *_ = make_resolver(make_route("route_a", prompt="exact input"))
    contribution = resolver.resolve(make_request("route_a"))

    assert contribution.provider_id == "offline_deterministic"
    assert contribution.model_label == "offline-deterministic-provider-not-live"
    assert contribution.content == contribution.primary_claim
    assert "OFFLINE DETERMINISTIC PROVIDER RESULT" in contribution.content
    assert "exact input" in contribution.content
    assert len(contribution.evidence_refs) == 1
    assert contribution.evidence_refs[0].startswith("EXEC-")
    assert contribution.accounted_tokens == 32
    assert contribution.cost_cad == Decimal("0.00")
    assert adapter.invocation_count == 1


def test_exact_replay_returns_same_contribution_without_second_adapter_invocation():
    resolver, adapter, *_ = make_resolver(make_route("route_a"))
    request = make_request("route_a")

    first = resolver.resolve(request)
    second = resolver.resolve(request)

    assert first == second
    assert adapter.invocation_count == 1


def test_changed_contribution_request_changes_invocation_identity():
    resolver, _adapter, *_ = make_resolver(make_route("route_a"))
    first = resolver.build_invocation(make_request("route_a", round_id=1))
    second = resolver.build_invocation(
        make_request("route_a", round_id=2, role="CRITIC", response_type="CRITIQUE")
    )
    assert first.invocation_id != second.invocation_id
    assert first.idempotency_key != second.idempotency_key
    assert first.request_digest != second.request_digest


def test_parallel_articulation_runs_provider_contributions_through_runtime():
    resolver, adapter, work_order, context, _change_set = make_resolver(
        make_route("route_a", prompt="proposal A"),
        make_route("route_b", prompt="proposal B"),
    )
    controller = ArticulationController(resolver)
    result = controller.run_parallel(
        work_order=work_order,
        context=context,
        session_id=SESSION_ID,
        budget=articulation_budget(),
        participant_a_fixture="route_a",
        participant_b_fixture="route_b",
        created_at=NOW,
    )

    assert len(result.ledger.messages) == 2
    assert adapter.invocation_count == 2
    assert all(message.provider_id == "offline_deterministic" for message in result.ledger.messages)
    assert all(message.content_classification == "UNTRUSTED_MODEL_OUTPUT" for message in result.ledger.messages)
    assert all(message.evidence_refs[0].startswith("EXEC-") for message in result.ledger.messages)
    assert all(message.external_action_performed is False for message in result.ledger.messages)


def test_critique_ceremony_routes_four_provider_contributions_and_keeps_synthesis_internal():
    resolver, adapter, work_order, context, _change_set = make_resolver(
        make_route("proposal_a", prompt="proposal A"),
        make_route("proposal_b", prompt="proposal B"),
        make_route("critique_a", prompt="critique proposal B"),
        make_route("critique_b", prompt="critique proposal A"),
    )
    controller = ArticulationController(resolver)
    result = controller.run_critique_ceremony(
        work_order=work_order,
        context=context,
        session_id=SESSION_ID,
        budget=articulation_budget(),
        proposal_a_fixture="proposal_a",
        proposal_b_fixture="proposal_b",
        critique_a_fixture="critique_a",
        critique_b_fixture="critique_b",
        created_at=NOW,
    )

    assert len(result.ledger.messages) == 5
    assert adapter.invocation_count == 4
    assert all(
        message.provider_id == "offline_deterministic"
        for message in result.ledger.messages[:4]
    )
    synthesis = result.ledger.messages[-1]
    assert synthesis.provider_id == "nexus_fixture_synthesizer"
    assert synthesis.model_label == "deterministic-synthesizer-not-model"
    assert synthesis.content_classification == "DERIVED_UNTRUSTED_SYNTHESIS"
    assert synthesis.live_provider_call_performed is False
    assert len(result.ledger.messages[2].parent_message_ids) == 1
    assert len(result.ledger.messages[3].parent_message_ids) == 1


def test_critique_parent_lineage_is_bound_into_provider_input():
    resolver, _adapter, *_ = make_resolver(make_route("critique"))
    parent = "ARTMSG-" + "A" * 24
    invocation = resolver.build_invocation(
        make_request(
            "critique",
            round_id=2,
            role="CRITIC",
            response_type="CRITIQUE",
            parents=(parent,),
        )
    )
    assert parent in invocation.input_payload
