from __future__ import annotations

from src.domain.epistemic.models import ArtifactState, Claim, Entity
from src.domain.epistemic.verification import UtilityWeights
from src.core.epistemic.verifier import DeterministicEpistemicVerifier


WEIGHTS = UtilityWeights(
    fidelity=0.30,
    evidence=0.25,
    completeness=0.20,
    redundancy=0.10,
    unsupported=0.15,
)


def _entity(entity_id: str = "ENT-VERIFY01", name: str = "Verifier Entity") -> Entity:
    return Entity(
        id=entity_id,
        name=name,
        description="Deterministic verifier fixture",
        entity_type="primitive",
    )


def _observation(
    claim_id: str = "CLM-VERIFY01",
    *,
    evidence: tuple[str, ...] = ("evidence:verified:001",),
) -> Claim:
    return Claim(
        id=claim_id,
        statement="A supported observation",
        basis="observation",
        verification_state="verified" if evidence else "unverified",
        confidence=0.9,
        evidence_refs=evidence,
    )


def _state(*, revision: int = 1, entity: Entity | None = None, claim: Claim | None = None) -> ArtifactState:
    return ArtifactState(
        stage="synthesizer",
        revision=revision,
        entities=((entity or _entity()),),
        claims=((claim or _observation()),),
    )


def _verifier(threshold: float = 0.0) -> DeterministicEpistemicVerifier:
    return DeterministicEpistemicVerifier(weights=WEIGHTS, utility_threshold=threshold)


def test_equivalent_transition_is_deterministic_and_passing() -> None:
    baseline = _state()
    target = baseline.model_copy(update={"revision": 2})
    first = _verifier().evaluate(baseline, target)
    second = _verifier().evaluate(baseline, target)

    assert first.report_id == second.report_id
    assert first.target_state_hash == second.target_state_hash
    assert first.utility_score.semantic_fidelity_f == 1.0
    assert first.is_passing is True
    assert first.external_action_performed is False
    assert first.output_modified is False


def test_dropped_claim_is_critical_fidelity_failure() -> None:
    baseline = _state()
    target = ArtifactState(
        stage="synthesizer",
        revision=2,
        entities=baseline.entities,
        claims=(),
    )
    report = _verifier().evaluate(baseline, target)

    assert report.is_passing is False
    assert report.hard_failure is True
    assert any(finding.code == "CLAIM_DROPPED" for finding in report.findings)
    assert report.utility_score.semantic_fidelity_f < 1.0


def test_same_claim_id_with_modified_content_is_critical() -> None:
    baseline = _state()
    mutated = Claim(
        id="CLM-VERIFY01",
        statement="Content changed behind the same identifier",
        basis="observation",
        verification_state="verified",
        confidence=0.9,
        evidence_refs=("evidence:verified:001",),
    )
    target = _state(revision=2, claim=mutated)
    report = _verifier().evaluate(baseline, target)

    assert report.is_passing is False
    assert any(finding.code == "CLAIM_MUTATED_IN_PLACE" for finding in report.findings)


def test_unverified_empirical_claim_is_nonpassing_and_penalized() -> None:
    baseline = ArtifactState(stage="critic", revision=1)
    unsupported = _observation(evidence=())
    target = ArtifactState(stage="synthesizer", revision=2, claims=(unsupported,))
    report = _verifier().evaluate(baseline, target)

    assert report.is_passing is False
    assert report.unverified_claims == 1
    assert report.utility_score.evidence_coverage_e == 0.0
    assert report.utility_score.unsupported_claims_x == 1.0
    assert any(finding.code == "UNVERIFIED_ACTIVE_CLAIM" for finding in report.findings)
    assert any(finding.code == "EMPIRICAL_CLAIM_WITHOUT_EVIDENCE" for finding in report.findings)


def test_superseded_unverified_claim_becomes_historical_not_active() -> None:
    old = Claim(
        id="CLM-OLD0001",
        statement="Preliminary observation",
        basis="observation",
        verification_state="unverified",
        confidence=0.5,
    )
    replacement = Claim(
        id="CLM-NEW0001",
        statement="Evidence-backed replacement observation",
        basis="observation",
        verification_state="verified",
        confidence=0.95,
        evidence_refs=("evidence:replacement:001",),
        supersedes="CLM-OLD0001",
    )
    baseline = ArtifactState(stage="critic", revision=1, claims=(old,))
    target = ArtifactState(stage="synthesizer", revision=2, claims=(old, replacement))
    report = _verifier().evaluate(baseline, target)

    assert report.unverified_claims == 0
    assert report.utility_score.evidence_coverage_e == 1.0
    assert report.utility_score.unsupported_claims_x == 0.0
    assert not any(
        finding.code == "UNVERIFIED_ACTIVE_CLAIM" and "CLM-OLD0001" in finding.claim_ids
        for finding in report.findings
    )
    assert report.is_passing is True


def test_falsified_active_claim_is_hard_failure() -> None:
    baseline = ArtifactState(stage="critic", revision=1)
    claim = Claim(
        id="CLM-FALSE001",
        statement="A claim falsified by deterministic evidence",
        basis="hypothesis",
        verification_state="falsified",
        confidence=0.1,
        falsifier="A defined counter-observation falsifies the claim",
        falsification_evidence_refs=("evidence:falsifier:001",),
    )
    target = ArtifactState(stage="synthesizer", revision=2, claims=(claim,))
    report = _verifier().evaluate(baseline, target)

    assert report.falsified_claims == 1
    assert report.hard_failure is True
    assert report.is_passing is False
    assert any(finding.code == "FALSIFIED_CLAIM_PRESENT" for finding in report.findings)


def test_duplicate_semantics_are_warning_and_normalized_penalty() -> None:
    left = _entity("ENT-LEFT001", "Repeated Name")
    right = _entity("ENT-RIGHT01", " repeated   name ")
    baseline = ArtifactState(stage="critic", revision=1)
    target = ArtifactState(stage="synthesizer", revision=2, entities=(left, right))
    report = _verifier().evaluate(baseline, target)

    assert any(finding.code == "DUPLICATE_ENTITY_SEMANTICS" for finding in report.findings)
    assert 0.0 < report.utility_score.redundancy_r <= 1.0


def test_weights_must_sum_to_one() -> None:
    try:
        UtilityWeights(
            fidelity=0.5,
            evidence=0.5,
            completeness=0.5,
            redundancy=0.5,
            unsupported=0.5,
        )
    except ValueError as exc:
        assert "sum to 1.0" in str(exc)
    else:
        raise AssertionError("non-normalized verifier weights were accepted")


def test_utility_threshold_is_enforced_without_fake_semantic_metric() -> None:
    baseline = ArtifactState(stage="critic", revision=1)
    target = ArtifactState(stage="synthesizer", revision=2)
    report = _verifier(threshold=0.9).evaluate(baseline, target)

    assert report.utility_score.total_score < 0.9
    assert report.is_passing is False
