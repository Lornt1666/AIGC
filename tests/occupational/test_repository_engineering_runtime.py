from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.occupational.contracts import (
    EvidenceReceipt,
    OccupationalBinding,
    OutcomeContract,
    WorkAttempt,
    WorkAttemptStatus,
    WorkCommission,
)
from src.occupational.repository_engineering import (
    RepositoryEngineer,
    ScopeClassification,
)


ROOT = Path(__file__).resolve().parents[2]
COMMISSION_PATH = ROOT / "config" / "aigc_repository_engineering_self_hosting_commission.v1.json"


def _load_contracts() -> tuple[WorkCommission, OutcomeContract]:
    payload = json.loads(COMMISSION_PATH.read_text(encoding="utf-8"))
    return (
        WorkCommission.model_validate(payload["work_commission"]),
        OutcomeContract.model_validate(payload["outcome_contract"]),
    )


def _attempt() -> tuple[WorkCommission, OutcomeContract, WorkAttempt]:
    commission, contract = _load_contracts()
    binding = OccupationalBinding.from_contracts(
        commission,
        contract,
        career_mandate_id="CM_AIGC_001",
        career_mandate_version=1,
        policy_version="occupational-autonomy-v2",
    )
    attempt = WorkAttempt(
        work_attempt_id="WA_AIGC_REPO_001",
        occupational_binding=binding,
        writer_lineage_id="WRITER_A",
    )
    return commission, contract, attempt


def test_sealed_work_commission_and_outcome_contract_are_immutable() -> None:
    commission, contract = _load_contracts()

    with pytest.raises((ValidationError, TypeError)):
        commission.requested_outcome = "silently expanded scope"  # type: ignore[misc]
    with pytest.raises((ValidationError, TypeError)):
        contract.hard_gates = ("weakened",)  # type: ignore[misc]


def test_work_attempt_binds_exact_contract_digests() -> None:
    commission, contract, attempt = _attempt()

    assert attempt.occupational_binding.commission_sha256 == commission.digest
    assert attempt.occupational_binding.outcome_contract_sha256 == contract.digest
    assert attempt.occupational_binding.matches(
        commission,
        contract,
        current_mandate_version=1,
        current_policy_version="occupational-autonomy-v2",
    )


def test_mandate_or_policy_drift_denies_consequential_transition() -> None:
    commission, contract, attempt = _attempt()

    with pytest.raises(ValueError, match="consequential transition denied"):
        attempt.transition(
            WorkAttemptStatus.EXECUTING,
            commission=commission,
            outcome_contract=contract,
            current_mandate_version=2,
            current_policy_version="occupational-autonomy-v2",
        )

    assert attempt.status is WorkAttemptStatus.STALE_AUTHORIZATION


def test_supersession_denies_consequential_transition() -> None:
    commission, contract, attempt = _attempt()

    with pytest.raises(ValueError, match="consequential transition denied"):
        attempt.transition(
            WorkAttemptStatus.EXECUTING,
            commission=commission,
            outcome_contract=contract,
            current_mandate_version=1,
            current_policy_version="occupational-autonomy-v2",
            superseded=True,
        )

    assert attempt.status is WorkAttemptStatus.SUPERSEDED


def test_repository_atlas_is_required_before_write(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "worker.py").write_text(
        "import json\n\ndef run(value):\n    return json.dumps(value)\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_worker.py").write_text(
        "def test_placeholder():\n    assert True\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("pydantic==2.13.4\n", encoding="utf-8")

    commission, contract, attempt = _attempt()
    engineer = RepositoryEngineer(tmp_path)
    atlas = engineer.build_atlas()

    assert atlas.mapped
    assert atlas.file_graph
    assert atlas.symbol_graph
    assert atlas.import_graph
    assert atlas.configuration_graph

    denied = engineer.write_eligibility(
        atlas=atlas,
        commission=commission,
        outcome_contract=contract,
        attempt=attempt,
        current_mandate_version=1,
        current_policy_version="occupational-autonomy-v2",
        impact_analyzed=False,
        authority_valid=True,
    )
    assert not denied.eligible
    with pytest.raises(PermissionError, match="ImpactAnalyzed"):
        denied.require()

    admitted = engineer.write_eligibility(
        atlas=atlas,
        commission=commission,
        outcome_contract=contract,
        attempt=attempt,
        current_mandate_version=1,
        current_policy_version="occupational-autonomy-v2",
        impact_analyzed=True,
        authority_valid=True,
    )
    assert admitted.eligible
    admitted.require()


def test_scope_expansion_is_classified_not_silently_admitted() -> None:
    engineer = RepositoryEngineer(ROOT)

    unrelated = engineer.classify_discovery("unrelated cleanup")
    expansion = engineer.classify_discovery(
        "rewrite an unrelated subsystem",
        requires_scope_expansion=True,
    )
    dependency = engineer.classify_discovery(
        "required adapter",
        required_for_current_outcome=True,
    )

    assert unrelated.classification is ScopeClassification.FINDING
    assert not unrelated.may_enter_active_task_graph
    assert expansion.classification is ScopeClassification.COMMISSION_AMENDMENT_PROPOSAL
    assert not expansion.may_enter_active_task_graph
    assert dependency.classification is ScopeClassification.ADMITTED_DEPENDENCY
    assert dependency.may_enter_active_task_graph


def test_evidence_is_attempt_bound_and_writer_cannot_self_verify_independently() -> None:
    _, _, attempt = _attempt()

    with pytest.raises(ValueError, match="self-assert independent evidence"):
        EvidenceReceipt.for_attempt(
            receipt_id="ER_AIGC_001",
            attempt=attempt,
            evidence_type="TEST",
            result="PASS",
            verifier_id="WRITER_A",
            verifier_type="INDEPENDENT_AGENT",
            independent=True,
        )

    receipt = EvidenceReceipt.for_attempt(
        receipt_id="ER_AIGC_002",
        attempt=attempt,
        evidence_type="TEST",
        result="PASS",
        verifier_id="VERIFIER_B",
        verifier_type="INDEPENDENT_AGENT",
        independent=True,
    )
    assert receipt.work_attempt_id == attempt.work_attempt_id
    assert receipt.occupational_binding == attempt.occupational_binding
    assert receipt.independent is True


def test_semantic_no_progress_halts_bounded_retries() -> None:
    _, contract, attempt = _attempt()

    attempt.record_failure("same-failure", contract.no_progress_policy)
    assert attempt.status is WorkAttemptStatus.CREATED
    attempt.record_failure("same-failure", contract.no_progress_policy)
    assert attempt.status is WorkAttemptStatus.NO_PROGRESS


def test_quest_compatibility_has_no_authority() -> None:
    from src.occupational.contracts import QuestCompatibilityAlias

    alias = QuestCompatibilityAlias(
        quest_id="QUEST_LEGACY_001",
        commission_id="WC_AIGC_REPO_ENGINEERING_001",
        commission_revision=1,
        active_work_attempt_id="WA_AIGC_REPO_001",
    )
    assert alias.authority_source == "NONE_COMPATIBILITY_ONLY"
