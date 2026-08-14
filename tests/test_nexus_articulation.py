from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from src.core.nexus.articulation_controller import (
    ArticulationController,
    DeterministicFixtureResolver,
    FixtureContribution,
)
from src.domain.nexus.articulation import ArticulationBudget
from src.domain.nexus.contracts import ContextEnvelope, WorkOrder


CREATED_AT = datetime(2026, 8, 7, 14, 0, tzinfo=timezone.utc)


def _work_order() -> WorkOrder:
    return WorkOrder(
        work_order_id="WO-ART001",
        objective="Compare two deterministic provider-neutral proposals.",
    )


def _context(work_order: WorkOrder) -> ContextEnvelope:
    return ContextEnvelope(
        context_id="CTX-ART001",
        work_order_id=work_order.work_order_id,
        state_hash="a" * 64,
    )


def _budget(*, rounds: int = 3, contributions: int = 5, tokens: int = 10000) -> ArticulationBudget:
    return ArticulationBudget(
        maximum_rounds=rounds,
        maximum_contributions=contributions,
        maximum_tokens=tokens,
        maximum_cost_cad=Decimal("0.00"),
        maximum_elapsed_seconds=10,
        live_calls_allowed=False,
    )


def _resolver(*, same_claim: bool = False) -> DeterministicFixtureResolver:
    claim_b = "Use a single provider-neutral runtime boundary." if same_claim else "Keep provider runtime and articulation separate."
    return DeterministicFixtureResolver(
        (
            FixtureContribution(
                fixture_key="google-proposal",
                provider_id="google_fixture",
                model_label="fixture-google-not-live",
                primary_claim="Use a single provider-neutral runtime boundary.",
                content="Proposal A: keep providers behind a neutral resolver.",
                evidence_refs=("EV-A",),
                uncertainty=0.20,
                accounted_tokens=32,
            ),
            FixtureContribution(
                fixture_key="openai-proposal",
                provider_id="openai_fixture",
                model_label="fixture-openai-not-live",
                primary_claim=claim_b,
                content="Proposal B: preserve a separate articulation layer above runtime.",
                evidence_refs=("EV-B",),
                uncertainty=0.25,
                accounted_tokens=34,
            ),
            FixtureContribution(
                fixture_key="google-critique",
                provider_id="google_fixture",
                model_label="fixture-google-not-live",
                primary_claim="Critique B",
                content="Critique B: verify that separation cannot bypass execution governance.",
                evidence_refs=("EV-C",),
                uncertainty=0.15,
                accounted_tokens=28,
            ),
            FixtureContribution(
                fixture_key="openai-critique",
                provider_id="openai_fixture",
                model_label="fixture-openai-not-live",
                primary_claim="Critique A",
                content="Critique A: avoid coupling articulation contracts to provider execution state.",
                evidence_refs=("EV-D",),
                uncertainty=0.10,
                accounted_tokens=29,
            ),
        )
    )


def _controller(*, same_claim: bool = False) -> ArticulationController:
    return ArticulationController(_resolver(same_claim=same_claim))


def test_parallel_mode_is_provider_neutral_and_side_effect_free() -> None:
    work_order = _work_order()
    result = _controller().run_parallel(
        work_order=work_order,
        context=_context(work_order),
        session_id="ART-PAR001",
        budget=_budget(rounds=1, contributions=2),
        participant_a_fixture="google-proposal",
        participant_b_fixture="openai-proposal",
        created_at=CREATED_AT,
    )

    assert result.session.mode == "PARALLEL"
    assert [message.provider_id for message in result.ledger.messages] == [
        "google_fixture",
        "openai_fixture",
    ]
    assert all(message.response_type == "PROPOSAL" for message in result.ledger.messages)
    assert all(message.authority_granted is False for message in result.ledger.messages)
    assert all(message.external_action_performed is False for message in result.ledger.messages)
    assert all(message.live_provider_call_performed is False for message in result.ledger.messages)
    assert result.audit.provider_calls_performed == 0
    assert result.audit.network_calls_performed == 0
    assert result.audit.repository_reads_performed == 0
    assert result.audit.repository_writes_performed == 0
    assert result.audit.credentials_used == 0
    assert result.audit.spend_cad == Decimal("0")
    assert result.audit.external_action_performed is False


def test_critique_ceremony_produces_deterministic_synthesis_and_disagreement() -> None:
    work_order = _work_order()
    kwargs = dict(
        work_order=work_order,
        context=_context(work_order),
        session_id="ART-CRT001",
        budget=_budget(),
        proposal_a_fixture="google-proposal",
        proposal_b_fixture="openai-proposal",
        critique_a_fixture="google-critique",
        critique_b_fixture="openai-critique",
        created_at=CREATED_AT,
    )

    first = _controller().run_critique_ceremony(**kwargs)
    second = _controller().run_critique_ceremony(**kwargs)

    assert first == second
    assert first.session.mode == "CRITIQUE"
    assert first.session.status == "SYNTHESIZED"
    assert len(first.ledger.messages) == 5
    assert [message.response_type for message in first.ledger.messages] == [
        "PROPOSAL",
        "PROPOSAL",
        "CRITIQUE",
        "CRITIQUE",
        "SYNTHESIS",
    ]
    assert len(first.session.disagreements) == 1
    assert first.session.disagreements[0].resolution_status == "OPEN"
    assert first.session.disagreements[0].human_decision_required is True
    assert "DETERMINISTIC FIXTURE SYNTHESIS" in first.synthesis
    assert "Authority granted: false" in first.synthesis
    assert first.ledger.canonical_hash == second.ledger.canonical_hash
    assert first.session.canonical_hash == second.session.canonical_hash
    assert first.jsonl_transcript == second.jsonl_transcript
    assert first.markdown_transcript == second.markdown_transcript


def test_consensus_does_not_create_authority_or_forced_disagreement() -> None:
    work_order = _work_order()
    result = _controller(same_claim=True).run_parallel(
        work_order=work_order,
        context=_context(work_order),
        session_id="ART-CON001",
        budget=_budget(rounds=1, contributions=2),
        participant_a_fixture="google-proposal",
        participant_b_fixture="openai-proposal",
        created_at=CREATED_AT,
    )

    assert result.session.disagreements == ()
    assert result.session.authority_granted is False
    assert result.ledger.authority_granted is False
    assert not hasattr(result, "governance_decision")
    assert not hasattr(result, "execution_permit")


def test_transcript_projections_are_views_of_one_canonical_ledger() -> None:
    work_order = _work_order()
    result = _controller().run_parallel(
        work_order=work_order,
        context=_context(work_order),
        session_id="ART-VIEW01",
        budget=_budget(rounds=1, contributions=2),
        participant_a_fixture="google-proposal",
        participant_b_fixture="openai-proposal",
        created_at=CREATED_AT,
    )

    assert result.jsonl_transcript.count("\n") == 2
    assert result.ledger.canonical_hash in result.markdown_transcript
    assert "fixture-google-not-live" in result.markdown_transcript
    assert "fixture-openai-not-live" in result.markdown_transcript
    assert "UNTRUSTED_MODEL_OUTPUT" in result.markdown_transcript
