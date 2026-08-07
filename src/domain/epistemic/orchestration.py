from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from src.domain.epistemic.models import ArtifactState, ContractModel, RunReceipt
from src.domain.epistemic.verification import VerifierReport


GateAction = Literal["accepted", "revise", "rejected", "blocked", "requires_human_review"]


class DryRunRound(ContractModel):
    round_index: int = Field(ge=1, le=100)
    architect_state: ArtifactState
    critic_state: ArtifactState
    synthesizer_state: ArtifactState

    @model_validator(mode="after")
    def enforce_stage_contract(self) -> "DryRunRound":
        expected = (
            (self.architect_state, "architect"),
            (self.critic_state, "critic"),
            (self.synthesizer_state, "synthesizer"),
        )
        for state, stage in expected:
            if state.stage != stage:
                raise ValueError(f"Dry-run {stage} state must declare stage={stage}")
        revisions = (
            self.architect_state.revision,
            self.critic_state.revision,
            self.synthesizer_state.revision,
        )
        if not revisions[0] < revisions[1] < revisions[2]:
            raise ValueError("Dry-run stage revisions must increase architect < critic < synthesizer")
        return self


class GovernanceDecision(ContractModel):
    round_index: int = Field(ge=1)
    report_id: str = Field(pattern=r"^VRF-[A-F0-9]{24}$")
    action: GateAction
    reason_codes: tuple[str, ...] = ()
    external_action_performed: Literal[False] = False
    authority_expanded: Literal[False] = False


class DryRunExecutionResult(ContractModel):
    receipt: RunReceipt
    final_state: ArtifactState
    verifier_reports: tuple[VerifierReport, ...]
    decisions: tuple[GovernanceDecision, ...]
    rounds_consumed: int = Field(ge=0)
    block_reason_codes: tuple[str, ...] = ()
    external_action_performed: Literal[False] = False
    tool_invocations_performed: Literal[0] = 0
