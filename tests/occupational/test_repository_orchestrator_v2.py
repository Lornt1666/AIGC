from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.occupational.contracts import EvidenceReceipt, OccupationalBinding, OutcomeContract, WorkAttempt, WorkCommission
from src.occupational.repository_engineering import MethodGenomeName, RepositoryAtlas, WriteEligibility
from src.occupational.repository_orchestrator_v2 import (
    EngineeringMemoryEntry,
    ImpactDomain,
    ImpactEdge,
    ImpactGraph,
    MethodOutcome,
    RepositoryEngineeringAuthority,
    RepositoryEngineeringOrchestratorV2,
)

ROOT = Path(__file__).resolve().parents[2]
COMMISSION_PATH = ROOT / "config" / "aigc_repository_engineering_self_hosting_commission.v1.json"


def _contracts() -> tuple[WorkCommission, OutcomeContract, WorkAttempt]:
    payload = json.loads(COMMISSION_PATH.read_text(encoding="utf-8"))
    commission = WorkCommission.model_validate(payload["work_commission"])
    contract = OutcomeContract.model_validate(payload["outcome_contract"])
    binding = OccupationalBinding.from_contracts(
        commission,
        contract,
        career_mandate_id="CM_AIGC_001",
        career_mandate_version=1,
        policy_version="occupational-autonomy-v2",
    )
    return commission, contract, WorkAttempt(work_attempt_id="WA1", occupational_binding=binding, writer_lineage_id="WRITER")


def _impact_graph(*, unresolved: tuple[str, ...] = ()) -> ImpactGraph:
    return ImpactGraph(
        proposal_id="P1",
        repository_digest="a" * 64,
        edges=(ImpactEdge(source="src/x.py", target="tests/test_x.py", domain=ImpactDomain.TESTS, relation="AFFECTS", confidence=0.9),),
        unresolved_impacts=unresolved,
    )


def test_effective_authority_is_minimum_boundary() -> None:
    effective = RepositoryEngineeringOrchestratorV2.effective_authority(
        RepositoryEngineeringAuthority.RE4,
        RepositoryEngineeringAuthority.RE3,
        RepositoryEngineeringAuthority.RE6,
    )
    assert effective is RepositoryEngineeringAuthority.RE3
    with pytest.raises(PermissionError, match="requires RE4"):
        RepositoryEngineeringOrchestratorV2.require_authority(effective, RepositoryEngineeringAuthority.RE4)


def test_write_requires_impact_analysis_in_addition_to_existing_gate() -> None:
    write = WriteEligibility(
        repository_mapped=True,
        requirements_bound=True,
        impact_analyzed=True,
        work_attempt_valid=True,
        authority_valid=True,
    )
    assert RepositoryEngineeringOrchestratorV2.write_eligible(write, _impact_graph())
    assert not RepositoryEngineeringOrchestratorV2.write_eligible(write, _impact_graph(unresolved=("unknown deployment effect",)))


def test_method_genome_profiles_are_risk_proportional() -> None:
    bug = RepositoryEngineeringOrchestratorV2.evaluator_profile(MethodGenomeName.BUG_REPAIR)
    migration = RepositoryEngineeringOrchestratorV2.evaluator_profile(MethodGenomeName.ARCHITECTURE_MIGRATION)
    assert "targeted_tests" in bug.required_gates
    assert migration.independent_verification_required
    assert migration.rollback_test_required
    assert migration.mutation_test_required
    assert len(migration.required_gates) > len(bug.required_gates)


def test_engineering_memory_requires_evidence_and_lineage() -> None:
    bad = EngineeringMemoryEntry(memory_id="M0", category="fact", statement="trust me", evidence_receipt_ids=(), source_attempt_ids=())
    with pytest.raises(ValueError, match="requires evidence"):
        RepositoryEngineeringOrchestratorV2.admit_memory(bad)

    good = EngineeringMemoryEntry(memory_id="M1", category="fact", statement="verified repository fact", evidence_receipt_ids=("ER1",), source_attempt_ids=("WA1",))
    RepositoryEngineeringOrchestratorV2.admit_memory(good)


def test_method_selection_optimizes_verified_quality_per_total_burden() -> None:
    a = MethodOutcome(method_genome=MethodGenomeName.BUG_REPAIR, verified_quality=8, cost=1, latency=1, human_attention=1, risk=1)
    b = MethodOutcome(method_genome=MethodGenomeName.FEATURE_IMPLEMENTATION, verified_quality=10, cost=4, latency=4, human_attention=4, risk=4)
    selected = RepositoryEngineeringOrchestratorV2.select_method((a, b))
    assert selected is a


def test_completion_fails_closed_on_missing_contract_gates_and_evidence() -> None:
    commission, contract, attempt = _contracts()
    atlas = RepositoryAtlas(
        root="/tmp/repo",
        repository_digest="b" * 64,
        file_graph=(), symbol_graph=(), import_graph=(), call_graph=(), test_coverage_graph=(), configuration_graph=(), build_graph=(), deployment_graph=(), data_flow_graph=(), authority_boundary_graph=(), evidence_graph=(), requirement_traceability_graph=(), parse_errors=(),
    )
    decision = RepositoryEngineeringOrchestratorV2.completion_decision(
        commission=commission,
        contract=contract,
        attempt=attempt,
        atlas=atlas,
        impact_graph=_impact_graph(),
        passed_gates=set(),
        evidence_receipts=(),
        authority_sufficient=True,
        current_mandate_version=1,
        current_policy_version="occupational-autonomy-v2",
    )
    assert not decision.complete
    assert decision.missing_gates
    assert decision.missing_evidence
