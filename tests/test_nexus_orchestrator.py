from src.core.epistemic.verifier import DeterministicEpistemicVerifier
from src.core.nexus.orchestrator import DryRunGovernanceOrchestrator, DryRunRound
from src.domain.epistemic.models import ArtifactState
from src.domain.epistemic.verification import UtilityWeights
from src.domain.nexus.contracts import WorkOrder


WEIGHTS = UtilityWeights(fidelity=0.30, evidence=0.25, completeness=0.20, redundancy=0.10, unsupported=0.15)


def _orchestrator() -> DryRunGovernanceOrchestrator:
    return DryRunGovernanceOrchestrator(
        DeterministicEpistemicVerifier(weights=WEIGHTS, utility_threshold=0.0),
        exact_revision="aa2ed77e4396f46b0c8ee9e17da8e3122f0c8a41",
    )


def _work_order() -> WorkOrder:
    return WorkOrder(work_order_id="WO-NEXUSRUN1", objective="Validate integrated brain", domain_tags=("software",))


def test_dry_run_accepts_preserved_empty_state_and_is_replay_deterministic() -> None:
    initial = ArtifactState(stage="ingest", revision=1)
    architect = ArtifactState(stage="architect", revision=2)
    critic = ArtifactState(stage="critic", revision=3)
    synth = ArtifactState(stage="synthesizer", revision=4)
    rounds = (DryRunRound(1, architect, critic, synth),)

    first = _orchestrator().execute(_work_order(), initial, rounds)
    second = _orchestrator().execute(_work_order(), initial, rounds)

    assert first.terminal_state == "accepted"
    assert first.run_id == second.run_id
    assert first.decisions[-1].decision == "approved"
    assert first.external_action_performed is False


def test_noncontiguous_rounds_fail_closed() -> None:
    initial = ArtifactState(stage="ingest", revision=1)
    state = ArtifactState(stage="synthesizer", revision=2)
    try:
        _orchestrator().execute(_work_order(), initial, (DryRunRound(2, state, state, state),))
    except ValueError as exc:
        assert "contiguous" in str(exc)
    else:
        raise AssertionError("noncontiguous round was accepted")


def test_dry_run_never_emits_execution_permit_or_tool_invocation() -> None:
    initial = ArtifactState(stage="ingest", revision=1)
    state = ArtifactState(stage="synthesizer", revision=2)
    result = _orchestrator().execute(_work_order(), initial, (DryRunRound(1, state, state, state),))

    assert not hasattr(result, "execution_permit")
    assert not hasattr(result, "tool_invocations")
    assert result.external_action_performed is False
