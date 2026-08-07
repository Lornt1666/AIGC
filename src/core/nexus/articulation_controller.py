from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.domain.nexus.articulation import (
    ArticulationBudget,
    ArticulationMessage,
    ArticulationSession,
    DialogueLedger,
    DisagreementRecord,
)
from src.domain.nexus.contracts import ContextEnvelope, WorkOrder


@dataclass(frozen=True)
class FixtureContribution:
    fixture_key: str
    provider_id: str
    model_label: str
    primary_claim: str
    content: str
    evidence_refs: tuple[str, ...] = ()
    uncertainty: float = 0.0
    accounted_tokens: int = 0
    cost_cad: Decimal = Decimal("0")


@dataclass(frozen=True)
class ContributionRequest:
    fixture_key: str
    session_id: str
    round_id: int
    role: str
    response_type: str
    parent_message_ids: tuple[str, ...]
    created_at: datetime
    repository_context_id: str | None = None


class ContributionResolver(Protocol):
    def resolve(self, request: ContributionRequest) -> FixtureContribution: ...


class DeterministicFixtureResolver:
    """Pure fixture resolver for exact replay; performs no provider or network work."""

    def __init__(self, fixtures: tuple[FixtureContribution, ...]) -> None:
        fixture_map = {item.fixture_key: item for item in fixtures}
        if len(fixture_map) != len(fixtures):
            raise ValueError("duplicate deterministic fixture keys are not permitted")
        self._fixtures = fixture_map

    def resolve(self, request: ContributionRequest) -> FixtureContribution:
        try:
            contribution = self._fixtures[request.fixture_key]
        except KeyError as exc:
            raise ValueError(f"deterministic fixture not found: {request.fixture_key}") from exc
        if contribution.cost_cad != Decimal("0"):
            raise ValueError("deterministic fixture cannot carry non-zero provider cost")
        return contribution


@dataclass(frozen=True)
class ArticulationSideEffectAudit:
    provider_calls_performed: int = 0
    network_calls_performed: int = 0
    repository_reads_performed: int = 0
    repository_writes_performed: int = 0
    credentials_used: int = 0
    spend_cad: Decimal = Decimal("0")
    external_action_performed: bool = False


@dataclass(frozen=True)
class ArticulationResult:
    session: ArticulationSession
    ledger: DialogueLedger
    synthesis: str | None
    jsonl_transcript: str
    markdown_transcript: str
    audit: ArticulationSideEffectAudit = ArticulationSideEffectAudit()


class ArticulationController:
    """Provider-blind deterministic articulation coordinator.

    This controller accepts only a ContributionResolver. It has no provider SDK,
    repository, credential, network, ToolBroker, or execution dependency.
    """

    def __init__(self, resolver: ContributionResolver) -> None:
        self._resolver = resolver

    def run_parallel(
        self,
        *,
        work_order: WorkOrder,
        context: ContextEnvelope,
        session_id: str,
        budget: ArticulationBudget,
        participant_a_fixture: str,
        participant_b_fixture: str,
        created_at: datetime,
        repository_context_id: str | None = None,
    ) -> ArticulationResult:
        self._validate_inputs(work_order, context, budget, created_at)
        if budget.maximum_rounds < 1 or budget.maximum_contributions < 2:
            raise ValueError("parallel articulation requires one round and two contributions")

        messages = (
            self._resolve_message(
                ContributionRequest(
                    fixture_key=participant_a_fixture,
                    session_id=session_id,
                    round_id=1,
                    role="PROPOSER",
                    response_type="PROPOSAL",
                    parent_message_ids=(),
                    created_at=created_at,
                    repository_context_id=repository_context_id,
                )
            ),
            self._resolve_message(
                ContributionRequest(
                    fixture_key=participant_b_fixture,
                    session_id=session_id,
                    round_id=1,
                    role="PROPOSER",
                    response_type="PROPOSAL",
                    parent_message_ids=(),
                    created_at=created_at + timedelta(seconds=1),
                    repository_context_id=repository_context_id,
                )
            ),
        )
        disagreements = self._proposal_disagreements(messages[0], messages[1])
        return self._result(
            work_order=work_order,
            context=context,
            session_id=session_id,
            mode="PARALLEL",
            budget=budget,
            messages=messages,
            disagreements=disagreements,
            status="COMPLETE",
            synthesis=None,
        )

    def run_critique_ceremony(
        self,
        *,
        work_order: WorkOrder,
        context: ContextEnvelope,
        session_id: str,
        budget: ArticulationBudget,
        proposal_a_fixture: str,
        proposal_b_fixture: str,
        critique_a_fixture: str,
        critique_b_fixture: str,
        created_at: datetime,
        repository_context_id: str | None = None,
    ) -> ArticulationResult:
        self._validate_inputs(work_order, context, budget, created_at)
        if budget.maximum_rounds < 3:
            raise ValueError("critique ceremony requires at least three rounds")
        if budget.maximum_contributions < 5:
            raise ValueError("critique ceremony requires at least five contributions")
        if budget.maximum_elapsed_seconds < 4:
            raise ValueError("critique ceremony exceeds maximum elapsed time")

        proposal_a = self._resolve_message(
            ContributionRequest(
                fixture_key=proposal_a_fixture,
                session_id=session_id,
                round_id=1,
                role="PROPOSER",
                response_type="PROPOSAL",
                parent_message_ids=(),
                created_at=created_at,
                repository_context_id=repository_context_id,
            )
        )
        proposal_b = self._resolve_message(
            ContributionRequest(
                fixture_key=proposal_b_fixture,
                session_id=session_id,
                round_id=1,
                role="PROPOSER",
                response_type="PROPOSAL",
                parent_message_ids=(),
                created_at=created_at + timedelta(seconds=1),
                repository_context_id=repository_context_id,
            )
        )
        critique_a = self._resolve_message(
            ContributionRequest(
                fixture_key=critique_a_fixture,
                session_id=session_id,
                round_id=2,
                role="CRITIC",
                response_type="CRITIQUE",
                parent_message_ids=(proposal_b.message_id,),
                created_at=created_at + timedelta(seconds=2),
                repository_context_id=repository_context_id,
            )
        )
        critique_b = self._resolve_message(
            ContributionRequest(
                fixture_key=critique_b_fixture,
                session_id=session_id,
                round_id=2,
                role="CRITIC",
                response_type="CRITIQUE",
                parent_message_ids=(proposal_a.message_id,),
                created_at=created_at + timedelta(seconds=3),
                repository_context_id=repository_context_id,
            )
        )
        disagreements = self._proposal_disagreements(proposal_a, proposal_b)
        synthesis_text = self._synthesis_text(
            proposal_a=proposal_a,
            proposal_b=proposal_b,
            critique_a=critique_a,
            critique_b=critique_b,
            disagreements=disagreements,
        )
        synthesis = self._build_message(
            session_id=session_id,
            round_id=3,
            provider_id="nexus_fixture_synthesizer",
            model_label="deterministic-synthesizer-not-model",
            role="SYNTHESIZER",
            response_type="SYNTHESIS",
            parent_message_ids=(
                proposal_a.message_id,
                proposal_b.message_id,
                critique_a.message_id,
                critique_b.message_id,
            ),
            content=synthesis_text,
            claim_refs=(),
            evidence_refs=tuple(
                sorted(
                    {
                        *proposal_a.evidence_refs,
                        *proposal_b.evidence_refs,
                        *critique_a.evidence_refs,
                        *critique_b.evidence_refs,
                    }
                )
            ),
            repository_context_id=repository_context_id,
            uncertainty=max(
                proposal_a.uncertainty,
                proposal_b.uncertainty,
                critique_a.uncertainty,
                critique_b.uncertainty,
            ),
            created_at=created_at + timedelta(seconds=4),
            accounted_tokens=self._accounted_tokens(synthesis_text),
            cost_cad=Decimal("0"),
            content_classification="DERIVED_UNTRUSTED_SYNTHESIS",
        )

        messages = (proposal_a, proposal_b, critique_a, critique_b, synthesis)
        return self._result(
            work_order=work_order,
            context=context,
            session_id=session_id,
            mode="CRITIQUE",
            budget=budget,
            messages=messages,
            disagreements=disagreements,
            status="SYNTHESIZED",
            synthesis=synthesis_text,
        )

    @staticmethod
    def _validate_inputs(
        work_order: WorkOrder,
        context: ContextEnvelope,
        budget: ArticulationBudget,
        created_at: datetime,
    ) -> None:
        if context.work_order_id != work_order.work_order_id:
            raise ValueError("ContextEnvelope is not bound to the supplied WorkOrder")
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("articulation created_at must be timezone-aware")
        if budget.live_calls_allowed:
            raise ValueError("live provider calls are prohibited in deterministic articulation")
        if budget.maximum_cost_cad != Decimal("0"):
            raise ValueError("deterministic articulation requires a zero-CAD budget")

    def _resolve_message(self, request: ContributionRequest) -> ArticulationMessage:
        fixture = self._resolver.resolve(request)
        return self._build_message(
            session_id=request.session_id,
            round_id=request.round_id,
            provider_id=fixture.provider_id,
            model_label=fixture.model_label,
            role=request.role,
            response_type=request.response_type,
            parent_message_ids=request.parent_message_ids,
            content=fixture.content,
            claim_refs=(fixture.primary_claim,),
            evidence_refs=fixture.evidence_refs,
            repository_context_id=request.repository_context_id,
            uncertainty=fixture.uncertainty,
            created_at=request.created_at,
            accounted_tokens=fixture.accounted_tokens,
            cost_cad=fixture.cost_cad,
            content_classification="UNTRUSTED_MODEL_OUTPUT",
        )

    @staticmethod
    def _build_message(
        *,
        session_id: str,
        round_id: int,
        provider_id: str,
        model_label: str,
        role: str,
        response_type: str,
        parent_message_ids: tuple[str, ...],
        content: str,
        claim_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        repository_context_id: str | None,
        uncertainty: float,
        created_at: datetime,
        accounted_tokens: int,
        cost_cad: Decimal,
        content_classification: str,
    ) -> ArticulationMessage:
        identity_payload = {
            "session_id": session_id,
            "round_id": round_id,
            "provider_id": provider_id,
            "model_label": model_label,
            "role": role,
            "response_type": response_type,
            "parent_message_ids": parent_message_ids,
            "content": content,
            "claim_refs": claim_refs,
            "evidence_refs": evidence_refs,
            "repository_context_id": repository_context_id,
            "uncertainty": uncertainty,
            "created_at": created_at.isoformat(),
            "accounted_tokens": accounted_tokens,
            "cost_cad": str(cost_cad),
            "content_classification": content_classification,
        }
        message_id = "ARTMSG-" + canonical_sha256(identity_payload)[:24].upper()
        message = ArticulationMessage(
            message_id=message_id,
            session_id=session_id,
            round_id=round_id,
            provider_id=provider_id,
            model_label=model_label,
            role=role,
            response_type=response_type,
            parent_message_ids=parent_message_ids,
            content=content,
            claim_refs=claim_refs,
            evidence_refs=evidence_refs,
            repository_context_id=repository_context_id,
            uncertainty=uncertainty,
            created_at=created_at,
            accounted_tokens=accounted_tokens,
            cost_cad=cost_cad,
            content_classification=content_classification,
            canonical_hash="0" * 64,
        )
        digest = canonical_sha256(message.model_dump(mode="json", exclude={"canonical_hash"}))
        return message.model_copy(update={"canonical_hash": digest})

    @staticmethod
    def _proposal_disagreements(
        proposal_a: ArticulationMessage,
        proposal_b: ArticulationMessage,
    ) -> tuple[DisagreementRecord, ...]:
        claim_a = proposal_a.claim_refs[0] if proposal_a.claim_refs else proposal_a.content
        claim_b = proposal_b.claim_refs[0] if proposal_b.claim_refs else proposal_b.content
        if claim_a == claim_b:
            return ()
        payload = {
            "message_a": proposal_a.message_id,
            "message_b": proposal_b.message_id,
            "claim_a": claim_a,
            "claim_b": claim_b,
            "evidence_refs_a": proposal_a.evidence_refs,
            "evidence_refs_b": proposal_b.evidence_refs,
            "uncertainty": max(proposal_a.uncertainty, proposal_b.uncertainty),
            "resolution_status": "OPEN",
            "human_decision_required": True,
        }
        disagreement_id = "DIS-" + canonical_sha256(payload)[:24].upper()
        return (
            DisagreementRecord(
                disagreement_id=disagreement_id,
                message_a=proposal_a.message_id,
                message_b=proposal_b.message_id,
                claim_a=claim_a,
                claim_b=claim_b,
                evidence_refs_a=proposal_a.evidence_refs,
                evidence_refs_b=proposal_b.evidence_refs,
                uncertainty=payload["uncertainty"],
                resolution_status="OPEN",
                human_decision_required=True,
            ),
        )

    @staticmethod
    def _synthesis_text(
        *,
        proposal_a: ArticulationMessage,
        proposal_b: ArticulationMessage,
        critique_a: ArticulationMessage,
        critique_b: ArticulationMessage,
        disagreements: tuple[DisagreementRecord, ...],
    ) -> str:
        lines = [
            "DETERMINISTIC FIXTURE SYNTHESIS — NOT A LIVE MODEL RESULT",
            f"Proposal A ({proposal_a.provider_id}): {proposal_a.content}",
            f"Proposal B ({proposal_b.provider_id}): {proposal_b.content}",
            f"Critique A ({critique_a.provider_id}): {critique_a.content}",
            f"Critique B ({critique_b.provider_id}): {critique_b.content}",
            "Open disagreements:",
        ]
        if disagreements:
            lines.extend(f"- {item.claim_a} <> {item.claim_b}" for item in disagreements)
        else:
            lines.append("- none")
        lines.append("Authority granted: false")
        return "\n".join(lines)

    @staticmethod
    def _accounted_tokens(content: str) -> int:
        return max(1, (len(content) + 3) // 4)

    def _result(
        self,
        *,
        work_order: WorkOrder,
        context: ContextEnvelope,
        session_id: str,
        mode: str,
        budget: ArticulationBudget,
        messages: tuple[ArticulationMessage, ...],
        disagreements: tuple[DisagreementRecord, ...],
        status: str,
        synthesis: str | None,
    ) -> ArticulationResult:
        ledger = DialogueLedger(
            session_id=session_id,
            messages=messages,
            canonical_hash="0" * 64,
        )
        ledger_hash = canonical_sha256(ledger.model_dump(mode="json", exclude={"canonical_hash"}))
        ledger = ledger.model_copy(update={"canonical_hash": ledger_hash})

        session = ArticulationSession(
            session_id=session_id,
            work_order_id=work_order.work_order_id,
            context_envelope_id=context.context_id,
            mode=mode,
            budget=budget,
            messages=messages,
            disagreements=disagreements,
            status=status,
            canonical_hash="0" * 64,
        )
        session_hash = canonical_sha256(session.model_dump(mode="json", exclude={"canonical_hash"}))
        session = session.model_copy(update={"canonical_hash": session_hash})

        return ArticulationResult(
            session=session,
            ledger=ledger,
            synthesis=synthesis,
            jsonl_transcript=self.to_jsonl(ledger),
            markdown_transcript=self.to_markdown(ledger),
        )

    @staticmethod
    def to_jsonl(ledger: DialogueLedger) -> str:
        return "".join(canonical_json_bytes(message).decode("utf-8") + "\n" for message in ledger.messages)

    @staticmethod
    def to_markdown(ledger: DialogueLedger) -> str:
        lines = [
            f"# Nexus Articulation Session {ledger.session_id}",
            "",
            f"Ledger SHA-256: `{ledger.canonical_hash}`",
            "",
        ]
        for message in ledger.messages:
            lines.extend(
                [
                    f"## Round {message.round_id} — {message.response_type}",
                    "",
                    f"- Provider: `{message.provider_id}`",
                    f"- Model label: `{message.model_label}`",
                    f"- Trust: `{message.content_classification}`",
                    f"- Message hash: `{message.canonical_hash}`",
                    "",
                    message.content,
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"
