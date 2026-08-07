from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.epistemic.verifier import DeterministicEpistemicVerifier
from src.domain.epistemic.models import ArtifactState
from src.domain.epistemic.verification import VerifierReport
from src.domain.nexus.contracts import GovernanceDecision, WorkOrder


@dataclass(frozen=True)
class DryRunRound:
    round_number: int
    architect_state: ArtifactState
    critic_state: ArtifactState
    synthesizer_state: ArtifactState


@dataclass(frozen=True)
class DryRunResult:
    run_id: str
    terminal_state: str
    final_state: ArtifactState
    reports: tuple[VerifierReport, ...]
    decisions: tuple[GovernanceDecision, ...]
    external_action_performed: bool = False


class DryRunGovernanceOrchestrator:
    """Evaluate precomputed stage states only; never invoke agents or tools."""

    def __init__(self, verifier: DeterministicEpistemicVerifier, exact_revision: str, maximum_rounds: int = 3):
        if not 1 <= maximum_rounds <= 10:
            raise ValueError("maximum_rounds must be between 1 and 10")
        self.verifier = verifier
        self.exact_revision = exact_revision
        self.maximum_rounds = maximum_rounds

    def execute(self, work_order: WorkOrder, initial_state: ArtifactState, rounds: tuple[DryRunRound, ...]) -> DryRunResult:
        if not rounds or len(rounds) > self.maximum_rounds:
            raise ValueError("invalid bounded round set")
        baseline = initial_state
        reports = []
        decisions = []
        terminal = "blocked"

        for expected, item in enumerate(rounds, start=1):
            if item.round_number != expected:
                raise ValueError("round numbers must be contiguous from one")

            for target in (item.architect_state, item.critic_state, item.synthesizer_state):
                report = self.verifier.evaluate(baseline, target)
                reports.append(report)
                if report.hard_failure:
                    decisions.append(self._decision(work_order, target, report, "blocked"))
                    return self._result(work_order, initial_state, target, reports, decisions, "blocked")
                baseline = target

            report = reports[-1]
            if report.is_passing:
                decisions.append(self._decision(work_order, baseline, report, "approved"))
                terminal = "accepted"
                break

            if expected < len(rounds):
                decisions.append(self._decision(work_order, baseline, report, "revise"))
                continue

            decisions.append(self._decision(work_order, baseline, report, "requires_human_review"))
            terminal = "requires_human_review"

        return self._result(work_order, initial_state, baseline, reports, decisions, terminal)

    def _decision(self, work_order: WorkOrder, state: ArtifactState, report: VerifierReport, decision: str) -> GovernanceDecision:
        state_hash = canonical_sha256(state)
        report_hash = canonical_sha256(report)
        change_hash = sha256(f"dry-run:{work_order.work_order_id}:{state_hash}".encode()).hexdigest()
        decision_id = "GOV-" + sha256(
            json.dumps([work_order.work_order_id, state_hash, report_hash, decision, self.exact_revision]).encode()
        ).hexdigest()[:24].upper()
        return GovernanceDecision(
            decision_id=decision_id,
            decision=decision,
            authority_source="POLICY",
            authority_actor="nexus-v1-dry-run-policy",
            artifact_state_hash=state_hash,
            change_set_hash=change_hash,
            verifier_report_hash=report_hash,
            exact_revision=self.exact_revision,
        )

    def _result(self, work_order, initial_state, final_state, reports, decisions, terminal):
        payload = [work_order.work_order_id, canonical_sha256(initial_state), canonical_sha256(final_state), terminal]
        run_id = "RUN-" + sha256(json.dumps(payload).encode()).hexdigest()[:24].upper()
        return DryRunResult(run_id, terminal, final_state, tuple(reports), tuple(decisions))
