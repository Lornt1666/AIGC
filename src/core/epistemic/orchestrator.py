from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.epistemic.verifier import DeterministicEpistemicVerifier
from src.domain.epistemic.models import ArtifactState, RunReceipt
from src.domain.epistemic.orchestration import (
    DryRunExecutionResult,
    DryRunRound,
    GovernanceDecision,
)
from src.domain.epistemic.verification import VerifierReport


class EpistemicDryRunOrchestrator:
    """Deterministic Governance Gate over precomputed epistemic stage states.

    It does not invoke agents, models, tools, filesystems, networks, credentials,
    repositories, or deployment systems. The only accepted inputs are already-built,
    immutable contract objects.
    """

    def __init__(self, *, config: dict, verifier: DeterministicEpistemicVerifier) -> None:
        orchestration = dict(config.get("orchestration") or {})
        self.maximum_rounds = int(orchestration.get("maximum_rounds", 0))
        self.dissent_policy = str(orchestration.get("unresolved_dissent_policy", ""))
        terminal_states = tuple(orchestration.get("terminal_states") or ())
        if not 1 <= self.maximum_rounds <= 10:
            raise ValueError("orchestration.maximum_rounds must be between 1 and 10")
        if self.dissent_policy not in {"preserve_and_surface", "terminate_run", "human_override"}:
            raise ValueError("unsupported unresolved_dissent_policy")
        expected_terminal = {"accepted", "rejected", "blocked", "requires_human_review"}
        if set(terminal_states) != expected_terminal:
            raise ValueError("orchestration terminal state set is incomplete")
        self.verifier = verifier

    def execute_dry_run(
        self,
        *,
        initial_prompt: str,
        starting_state: ArtifactState,
        rounds: tuple[DryRunRound, ...],
        started_at: datetime,
        completed_at: datetime,
        parent_run_id: str | None = None,
    ) -> DryRunExecutionResult:
        if started_at.tzinfo is None or completed_at.tzinfo is None:
            raise ValueError("dry-run timestamps must be timezone-aware")
        if completed_at < started_at:
            raise ValueError("completed_at cannot precede started_at")
        if len(rounds) > self.maximum_rounds:
            raise ValueError("precomputed rounds exceed configured maximum_rounds")
        if any(round_.round_index != index for index, round_ in enumerate(rounds, start=1)):
            raise ValueError("dry-run round indexes must be contiguous and start at 1")

        prompt_hash = sha256(initial_prompt.encode("utf-8")).hexdigest()
        input_hash = canonical_sha256(starting_state)
        run_seed = {
            "prompt_hash": prompt_hash,
            "input_hash": input_hash,
            "round_hashes": [canonical_sha256(round_) for round_ in rounds],
            "configuration_version": "2.0.0",
        }
        run_id = "RUN-" + canonical_sha256(run_seed)[:24].upper()

        current_state = starting_state
        reports: list[VerifierReport] = []
        decisions: list[GovernanceDecision] = []
        event_hashes: list[str] = []
        block_reasons: list[str] = []
        terminal_state = "requires_human_review"
        rounds_consumed = 0

        if not rounds:
            terminal_state = "requires_human_review"
            block_reasons.append("NO_PRECOMPUTED_ROUNDS")
        else:
            for round_ in rounds:
                rounds_consumed = round_.round_index

                architect_report = self.verifier.evaluate(current_state, round_.architect_state)
                critic_report = self.verifier.evaluate(round_.architect_state, round_.critic_state)
                synthesis_report = self.verifier.evaluate(round_.critic_state, round_.synthesizer_state)
                reports.extend((architect_report, critic_report, synthesis_report))

                for stage_name, report in (
                    ("architect", architect_report),
                    ("critic", critic_report),
                    ("synthesizer", synthesis_report),
                ):
                    event_hashes.append(
                        canonical_sha256(
                            {
                                "run_id": run_id,
                                "round_index": round_.round_index,
                                "stage": stage_name,
                                "report_id": report.report_id,
                                "target_state_hash": report.target_state_hash,
                            }
                        )
                    )

                if architect_report.hard_failure or critic_report.hard_failure:
                    decision = GovernanceDecision(
                        round_index=round_.round_index,
                        report_id=critic_report.report_id if critic_report.hard_failure else architect_report.report_id,
                        action="blocked",
                        reason_codes=("FUNCTORIAL_HANDOFF_VIOLATION",),
                    )
                    decisions.append(decision)
                    event_hashes.append(canonical_sha256(decision))
                    terminal_state = "blocked"
                    block_reasons.append("FUNCTORIAL_HANDOFF_VIOLATION")
                    current_state = round_.synthesizer_state
                    break

                current_state = round_.synthesizer_state
                if synthesis_report.is_passing:
                    decision = GovernanceDecision(
                        round_index=round_.round_index,
                        report_id=synthesis_report.report_id,
                        action="accepted",
                        reason_codes=("VERIFIER_PASS",),
                    )
                    decisions.append(decision)
                    event_hashes.append(canonical_sha256(decision))
                    terminal_state = "accepted"
                    break

                has_next_precomputed_round = round_.round_index < len(rounds)
                below_maximum = round_.round_index < self.maximum_rounds
                if below_maximum and has_next_precomputed_round:
                    decision = GovernanceDecision(
                        round_index=round_.round_index,
                        report_id=synthesis_report.report_id,
                        action="revise",
                        reason_codes=("VERIFIER_REVISION_REQUIRED",),
                    )
                    decisions.append(decision)
                    event_hashes.append(canonical_sha256(decision))
                    continue

                if below_maximum and not has_next_precomputed_round:
                    decision = GovernanceDecision(
                        round_index=round_.round_index,
                        report_id=synthesis_report.report_id,
                        action="requires_human_review",
                        reason_codes=("REVISION_REQUIRED_NO_PRECOMPUTED_ROUND",),
                    )
                    decisions.append(decision)
                    event_hashes.append(canonical_sha256(decision))
                    terminal_state = "requires_human_review"
                    break

                terminal_state, reason = self._terminal_for_exhausted_rounds()
                decision = GovernanceDecision(
                    round_index=round_.round_index,
                    report_id=synthesis_report.report_id,
                    action=terminal_state,
                    reason_codes=(reason,),
                )
                decisions.append(decision)
                event_hashes.append(canonical_sha256(decision))
                break

        output_hash = canonical_sha256(current_state)
        receipt = RunReceipt(
            run_id=run_id,
            parent_run_id=parent_run_id,
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            output_hash=output_hash,
            event_hashes=tuple(event_hashes),
            started_at=started_at,
            completed_at=completed_at,
            terminal_state=terminal_state,
        )
        return DryRunExecutionResult(
            receipt=receipt,
            final_state=current_state,
            verifier_reports=tuple(reports),
            decisions=tuple(decisions),
            rounds_consumed=rounds_consumed,
            block_reason_codes=tuple(block_reasons),
        )

    def _terminal_for_exhausted_rounds(self) -> tuple[str, str]:
        if self.dissent_policy == "terminate_run":
            return "rejected", "MAX_ROUNDS_TERMINATE_POLICY"
        if self.dissent_policy == "human_override":
            return "requires_human_review", "MAX_ROUNDS_HUMAN_OVERRIDE_POLICY"
        return "requires_human_review", "MAX_ROUNDS_PRESERVE_AND_SURFACE"
