from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.context_projection import ContextProjectionPolicy, build_context_envelope
from src.core.nexus.odse import strategy_to_artifact_state, synthesize_strategy
from src.domain.epistemic.models import ArtifactState
from src.domain.epistemic.verification import UtilityScore, VerifierReport
from src.domain.nexus.contracts import ExecutionReceipt, WorkOrder
from src.domain.nexus.evidence import EvidenceReference
from src.domain.nexus.memory import MemoryAdmissionDecision, MemoryCandidate, MemoryRecord
from src.domain.nexus.odse import KnowledgePillar, OperationalStrategyArtifact
from src.infrastructure.persistence.sqlite.nexus_evidence import SqliteNexusEvidenceRepository
from src.infrastructure.persistence.sqlite.nexus_memory import SqliteNexusMemoryRepository

NOW = datetime(2026, 8, 7, tzinfo=timezone.utc)


def _evidence(evidence_id: str = "EVD-NEXUS001") -> EvidenceReference:
    return EvidenceReference(
        evidence_id=evidence_id,
        kind="test",
        source="tests/test_nexus_memory_evidence_odse.py",
        digest="a" * 64,
        observed_at=NOW,
        integrity_state="verified",
        provenance="deterministic test fixture",
    )


def _candidate() -> MemoryCandidate:
    return MemoryCandidate(
        candidate_id="MEMC-NEXUS001",
        source_run_id="RUN-NEXUS001",
        source_artifact_hash="b" * 64,
        memory_type="PROJECT",
        content="Nexus dashboard governance and evidence integration",
        evidence_refs=("EVD-NEXUS001",),
        confidence=0.9,
        proposed_retention="project_lifetime",
        producer="AGT-SYNTHESIZER",
        created_at=NOW,
    )


def _verifier_report(candidate: MemoryCandidate) -> VerifierReport:
    return VerifierReport(
        baseline_state_hash="d" * 64,
        target_state_hash=candidate.source_artifact_hash,
        report_id="VRF-" + "A" * 24,
        total_claims_audited=1,
        unverified_claims=0,
        falsified_claims=0,
        utility_score=UtilityScore(
            total_score=1.0,
            semantic_fidelity_f=1.0,
            evidence_coverage_e=1.0,
            structural_completeness_c=1.0,
            redundancy_r=0.0,
            unsupported_claims_x=0.0,
        ),
        utility_threshold=0.0,
        hard_failure=False,
        is_passing=True,
    )


def _accepted_record(
    candidate: MemoryCandidate,
) -> tuple[MemoryAdmissionDecision, MemoryRecord, VerifierReport]:
    candidate_hash = canonical_sha256(candidate)
    verifier_report = _verifier_report(candidate)
    decision = MemoryAdmissionDecision(
        decision_id="MEMD-NEXUS001",
        candidate_hash=candidate_hash,
        verifier_report_hash=canonical_sha256(verifier_report),
        decision="ACCEPT",
        reason="Candidate passed deterministic admission fixtures.",
        authority_source="POLICY",
        authority_actor="nexus-memory-admission-test",
        admitted_at=NOW,
        resulting_memory_id="MEM-NEXUS001",
    )
    provisional = MemoryRecord(
        memory_id="MEM-NEXUS001",
        canonical_hash="0" * 64,
        source_candidate_hash=candidate_hash,
        admission_decision_id=decision.decision_id,
        memory_type="PROJECT",
        content=candidate.content,
        evidence_bindings=candidate.evidence_refs,
        verification_state="verified",
        valid_from=NOW,
        sensitivity="INTERNAL",
        retention_policy="project_lifetime",
    )
    digest = canonical_sha256(provisional.model_dump(mode="json", exclude={"canonical_hash"}))
    return decision, provisional.model_copy(update={"canonical_hash": digest}), verifier_report


def test_memory_candidate_requires_accepted_admission_before_persistence(tmp_path) -> None:
    repo = SqliteNexusMemoryRepository(tmp_path / "memory.sqlite")
    candidate = _candidate()
    decision, record, verifier_report = _accepted_record(candidate)
    rejected = decision.model_copy(update={"decision": "REJECT", "resulting_memory_id": None})

    with pytest.raises(ValueError, match="only accepted"):
        repo.admit(
            candidate=candidate,
            decision=rejected,
            verifier_report=verifier_report,
            record=record,
        )

    repo.admit(
        candidate=candidate,
        decision=decision,
        verifier_report=verifier_report,
        record=record,
    )
    stored = repo.get(record.memory_id)
    assert stored == record


def test_memory_admission_rejects_fabricated_verifier_hash(tmp_path) -> None:
    repo = SqliteNexusMemoryRepository(tmp_path / "memory.sqlite")
    candidate = _candidate()
    decision, record, verifier_report = _accepted_record(candidate)
    fabricated = decision.model_copy(update={"verifier_report_hash": "f" * 64})

    with pytest.raises(ValueError, match="supplied VerifierReport"):
        repo.admit(
            candidate=candidate,
            decision=fabricated,
            verifier_report=verifier_report,
            record=record,
        )


def test_memory_admission_rejects_mismatched_verifier_target(tmp_path) -> None:
    repo = SqliteNexusMemoryRepository(tmp_path / "memory.sqlite")
    candidate = _candidate()
    decision, record, verifier_report = _accepted_record(candidate)
    mismatched = verifier_report.model_copy(update={"target_state_hash": "e" * 64})
    rebound_decision = decision.model_copy(
        update={"verifier_report_hash": canonical_sha256(mismatched)}
    )

    with pytest.raises(ValueError, match="candidate source artifact"):
        repo.admit(
            candidate=candidate,
            decision=rebound_decision,
            verifier_report=mismatched,
            record=record,
        )


def test_memory_admission_rejects_nonpassing_verifier_report(tmp_path) -> None:
    repo = SqliteNexusMemoryRepository(tmp_path / "memory.sqlite")
    candidate = _candidate()
    decision, record, verifier_report = _accepted_record(candidate)
    failing = verifier_report.model_copy(update={"is_passing": False})
    rebound_decision = decision.model_copy(
        update={"verifier_report_hash": canonical_sha256(failing)}
    )

    with pytest.raises(ValueError, match="admission policy"):
        repo.admit(
            candidate=candidate,
            decision=rebound_decision,
            verifier_report=failing,
            record=record,
        )


def test_evidence_is_persistent_and_cannot_grant_authority(tmp_path) -> None:
    repo = SqliteNexusEvidenceRepository(tmp_path / "evidence.sqlite")
    evidence = _evidence()
    repo.put(evidence)
    assert repo.get(evidence.evidence_id) == evidence
    assert repo.get(evidence.evidence_id).grants_authority is False


def test_context_projection_excludes_superseded_and_sensitive_memory() -> None:
    candidate = _candidate()
    _, active, _ = _accepted_record(candidate)
    superseded = active.model_copy(update={"memory_id": "MEM-OLD0001", "superseded_by": active.memory_id})
    restricted = active.model_copy(update={"memory_id": "MEM-SECRET01", "sensitivity": "RESTRICTED"})
    state = ArtifactState(stage="candidate", revision=1)
    work_order = WorkOrder(
        work_order_id="WO-MEMORY01",
        objective="Integrate Nexus dashboard evidence",
        domain_tags=("software", "dashboard"),
    )
    envelope = build_context_envelope(
        work_order=work_order,
        state=state,
        memories=(superseded, restricted, active),
        evidence=(_evidence(),),
        authoritative_now=NOW,
    )
    assert envelope.memory_refs == (active.memory_id,)
    assert envelope.evidence_refs == ("EVD-NEXUS001",)


def test_context_projection_excludes_future_expired_revoked_and_superseded_memory() -> None:
    candidate = _candidate()
    _, active, _ = _accepted_record(candidate)
    future = active.model_copy(
        update={"memory_id": "MEM-FUTURE01", "valid_from": NOW + timedelta(seconds=1)}
    )
    expired = active.model_copy(
        update={"memory_id": "MEM-EXPIRED1", "valid_until": NOW}
    )
    revoked = active.model_copy(
        update={"memory_id": "MEM-REVOKED1", "revoked_at": NOW - timedelta(seconds=1)}
    )
    superseded = active.model_copy(
        update={"memory_id": "MEM-SUPER001", "superseded_by": active.memory_id}
    )
    envelope = build_context_envelope(
        work_order=WorkOrder(
            work_order_id="WO-MEMORY04",
            objective="Nexus dashboard governance",
            domain_tags=("dashboard",),
        ),
        state=ArtifactState(stage="candidate", revision=1),
        memories=(future, expired, revoked, superseded, active),
        evidence=(_evidence(),),
        authoritative_now=NOW,
    )
    assert envelope.memory_refs == (active.memory_id,)


def test_context_projection_fails_closed_when_evidence_does_not_resolve() -> None:
    candidate = _candidate()
    _, active, _ = _accepted_record(candidate)
    with pytest.raises(ValueError, match="does not resolve"):
        build_context_envelope(
            work_order=WorkOrder(work_order_id="WO-MEMORY02", objective="Nexus evidence", domain_tags=("software",)),
            state=ArtifactState(stage="candidate", revision=1),
            memories=(active,),
            evidence=(),
            authoritative_now=NOW,
        )


def test_context_projection_is_bounded_and_deterministic() -> None:
    candidate = _candidate()
    _, active, _ = _accepted_record(candidate)
    second = active.model_copy(update={"memory_id": "MEM-NEXUS002", "content": "Other unrelated project memory", "evidence_bindings": ()})
    kwargs = dict(
        work_order=WorkOrder(work_order_id="WO-MEMORY03", objective="Nexus dashboard governance", domain_tags=("dashboard",)),
        state=ArtifactState(stage="candidate", revision=1),
        memories=(second, active),
        evidence=(_evidence(),),
        authoritative_now=NOW,
        policy=ContextProjectionPolicy(maximum_memories=1, maximum_evidence_refs=2),
    )
    first = build_context_envelope(**kwargs)
    replay = build_context_envelope(**kwargs)
    assert first == replay
    assert first.memory_refs == (active.memory_id,)


def test_odse_produces_strategy_and_artifact_state_not_execution_receipt() -> None:
    work_order = WorkOrder(
        work_order_id="WO-ODSE0001",
        objective="Build evidence-aware Nexus memory integration",
        domain_tags=("software", "security", "dashboard"),
    )
    evidence = ("EVD-NEXUS001",)
    strategy = synthesize_strategy(
        work_order=work_order,
        academic=KnowledgePillar(pillar="ACADEMIC", findings=("Evidence-backed memory reduces repeated rediscovery.",), evidence_refs=evidence),
        disciplinary=KnowledgePillar(pillar="DISCIPLINARY", findings=("Governed admission separates candidate knowledge from accepted state.",), evidence_refs=evidence),
        occupational=KnowledgePillar(pillar="OCCUPATIONAL", findings=("Operators need inspectable provenance and supersession.",), evidence_refs=evidence),
        next_gen=KnowledgePillar(pillar="NEXT_GEN", findings=("Deterministic context projection can bound agent context.",), evidence_refs=evidence),
    )
    state = strategy_to_artifact_state(strategy, revision=2)

    assert isinstance(strategy, OperationalStrategyArtifact)
    assert isinstance(state, ArtifactState)
    assert strategy.external_action_performed is False
    assert not isinstance(strategy, ExecutionReceipt)
    assert len(state.entities) == 5
    assert len(state.relations) == 4
    assert "SPC-SECURITY" in strategy.recommended_specialists
