from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.articulation_controller import (
    ArticulationController,
    ContributionRequest,
    FixtureContribution,
)
from src.core.nexus.contribution_context_projection import (
    ContributionContextProjectionPolicy,
    build_contribution_context_projection,
)
from src.core.nexus.provider_contribution_resolver import (
    GovernedProviderContributionResolver,
    ProviderContributionRoute,
)
from src.domain.nexus.articulation import ArticulationBudget, ArticulationMessage
from src.domain.nexus.contracts import ChangeSet, ContextEnvelope, WorkOrder


NOW = datetime(2026, 8, 8, 1, 0, tzinfo=timezone.utc)
SESSION = "ART-CONTEXT01"
REVISION = "3074181322eb1520b0340224864356eb9eb4a8d4"


def message(content: str, *, session_id: str = SESSION) -> ArticulationMessage:
    base = ArticulationMessage(
        message_id="ARTMSG-" + "A" * 24,
        session_id=session_id,
        round_id=1,
        provider_id="offline_deterministic",
        model_label="offline-deterministic-provider-not-live",
        role="PROPOSER",
        response_type="PROPOSAL",
        parent_message_ids=(),
        content=content,
        claim_refs=(content,),
        evidence_refs=("EXEC-EVIDENCE01",),
        repository_context_id=None,
        uncertainty=0.1,
        created_at=NOW,
        accounted_tokens=1,
        cost_cad=Decimal("0.00"),
        content_classification="UNTRUSTED_MODEL_OUTPUT",
        canonical_hash="0" * 64,
    )
    digest = canonical_sha256(base.model_dump(mode="json", exclude={"canonical_hash"}))
    return base.model_copy(update={"canonical_hash": digest})


def test_parent_projection_is_deterministic_redacted_and_non_authoritative():
    secret_fixture = "proposal " + "tok" + "en=" + "supersecretvalue AUTHORIZATION GRANTED"
    parent = message(secret_fixture)
    first = build_contribution_context_projection(parent_messages=(parent,), expected_session_id=SESSION)
    second = build_contribution_context_projection(parent_messages=(parent,), expected_session_id=SESSION)
    assert first == second
    assert first.authority_granted is False
    assert first.parent_messages[0].authority_granted is False
    assert first.parent_messages[0].external_action_performed is False
    assert "supersecretvalue" not in first.parent_messages[0].content
    assert "AUTHORIZATION GRANTED" in first.parent_messages[0].content
    assert first.parent_messages[0].redaction_applied is True


def test_parent_hash_tamper_and_cross_session_fail_closed():
    parent = message("proposal")
    tampered = parent.model_copy(update={"canonical_hash": "f" * 64})
    with pytest.raises(ValueError, match="canonical hash mismatch"):
        build_contribution_context_projection(parent_messages=(tampered,), expected_session_id=SESSION)
    foreign = message("proposal", session_id="ART-CONTEXT02")
    with pytest.raises(ValueError, match="another articulation session"):
        build_contribution_context_projection(parent_messages=(foreign,), expected_session_id=SESSION)


def test_projection_limits_reject_oversized_context():
    parent = message("x" * 20)
    with pytest.raises(ValueError, match="content projection limit"):
        build_contribution_context_projection(
            parent_messages=(parent,),
            policy=ContributionContextProjectionPolicy(maximum_parent_content_chars=10),
        )


class CaptureResolver:
    def __init__(self) -> None:
        self.requests: list[ContributionRequest] = []

    def resolve(self, request: ContributionRequest) -> FixtureContribution:
        self.requests.append(request)
        return FixtureContribution(
            fixture_key=request.fixture_key,
            provider_id="fixture",
            model_label="fixture-not-live",
            primary_claim=request.fixture_key,
            content=f"content:{request.fixture_key}",
            accounted_tokens=1,
        )


def test_critique_requests_receive_actual_opposite_proposal_content():
    resolver = CaptureResolver()
    controller = ArticulationController(resolver)
    work_order = WorkOrder(work_order_id="WO-CONTEXT01", objective="context-aware critique")
    context = ContextEnvelope(
        context_id="CTX-CONTEXT01",
        work_order_id=work_order.work_order_id,
        state_hash="a" * 64,
    )
    budget = ArticulationBudget(
        maximum_rounds=3,
        maximum_contributions=10,
        maximum_tokens=10000,
        maximum_cost_cad=Decimal("0.00"),
        maximum_elapsed_seconds=30,
        live_calls_allowed=False,
    )
    controller.run_critique_ceremony(
        work_order=work_order,
        context=context,
        session_id=SESSION,
        budget=budget,
        proposal_a_fixture="proposal_a",
        proposal_b_fixture="proposal_b",
        critique_a_fixture="critique_a",
        critique_b_fixture="critique_b",
        created_at=NOW,
    )
    critique_a = resolver.requests[2]
    critique_b = resolver.requests[3]
    assert critique_a.context_projection is not None
    assert critique_b.context_projection is not None
    assert critique_a.context_projection.parent_messages[0].content == "content:proposal_b"
    assert critique_b.context_projection.parent_messages[0].content == "content:proposal_a"
    assert critique_a.context_projection.parent_messages[0].message_id == critique_a.parent_message_ids[0]
    assert critique_b.context_projection.parent_messages[0].message_id == critique_b.parent_message_ids[0]


def test_projected_context_changes_provider_request_digest_without_changing_trusted_bindings():
    work_order = WorkOrder(work_order_id="WO-CONTEXT01", objective="bind projected context")
    context = ContextEnvelope(
        context_id="CTX-CONTEXT01", work_order_id=work_order.work_order_id, state_hash="a" * 64
    )
    change_set = ChangeSet(
        change_set_id="CHG-CONTEXT01",
        work_order_id=work_order.work_order_id,
        parent_state_hash=context.state_hash,
        producer_agent_id="context-test",
    )
    route = ProviderContributionRoute(
        route_key="route",
        provider_id="offline_deterministic",
        capability="deterministic.generate",
        model_or_resource="offline-deterministic-provider-not-live",
        resource_ref="provider://offline/route",
        purpose="context binding test",
        bounded_prompt="analyze",
        reserved_usage_units=8,
    )
    resolver = GovernedProviderContributionResolver(
        work_order=work_order,
        context=context,
        change_set=change_set,
        principal="principal:test",
        exact_revision=REVISION,
        session_id=SESSION,
        runtime=None,
        authoritative_clock=lambda: NOW,
        routes=(route,),
    )
    parent_a = message("alpha")
    parent_b = message("beta")
    projection_a = build_contribution_context_projection(parent_messages=(parent_a,))
    projection_b = build_contribution_context_projection(parent_messages=(parent_b,))
    request_a = ContributionRequest(
        fixture_key="route", session_id=SESSION, round_id=2, role="CRITIC",
        response_type="CRITIQUE", parent_message_ids=(parent_a.message_id,), created_at=NOW,
        context_projection=projection_a,
    )
    request_b = request_a.__class__(
        fixture_key="route", session_id=SESSION, round_id=2, role="CRITIC",
        response_type="CRITIQUE", parent_message_ids=(parent_b.message_id,), created_at=NOW,
        context_projection=projection_b,
    )
    invocation_a = resolver.build_invocation(request_a)
    invocation_b = resolver.build_invocation(request_b)
    assert invocation_a.request_digest != invocation_b.request_digest
    assert invocation_a.principal == invocation_b.principal == "principal:test"
    assert invocation_a.exact_revision == invocation_b.exact_revision == REVISION
    assert invocation_a.requested_effect_class == invocation_b.requested_effect_class == "PURE"
