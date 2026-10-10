from src.apex_completion.engine import evaluate_snapshot
from src.apex_completion.models import EvidenceBinding, GateRecord, ProgramSnapshot


def evidence(kind, *, revision="HEAD", state="PRESENT"):
    return EvidenceBinding(
        evidence_id=f"E-{kind}",
        evidence_type=kind,
        state=state,
        subject=kind,
        exact_revision=revision,
    )


def gate(gate_id, state="VERIFIED_COMPLETE", kinds=("RECEIPT",), *, revision="HEAD"):
    return GateRecord(
        gate_id=gate_id,
        state=state,
        required_evidence_types=tuple(kinds),
        evidence=tuple(evidence(kind, revision=revision) for kind in kinds),
        candidate_revision=revision if gate_id == "G4" else "",
        blocker="blocked" if state in {"BLOCKED", "AWAITING_AUTHORIZATION"} else "",
    )


def snapshot(gates, **overrides):
    values = dict(
        snapshot_id="S1",
        repository="Lornt1666/AIGC",
        canonical_branch="main",
        canonical_revision="MAIN",
        integration_pr=181,
        integration_branch="release/aigc-nexus-v1",
        integration_revision="HEAD",
        gates=tuple(gates),
        underlying_facts_weighted=100,
        underlying_facts_strict=100,
        authorization_completed=24,
        authorization_total=24,
        revenue_commercial_readiness=100,
        revenue_operational_readiness=100,
        critical_blockers=(),
    )
    values.update(overrides)
    return ProgramSnapshot(**values)


def complete_gates():
    result = []
    for index in range(2, 10):
        gate_id = f"G{index}"
        if gate_id == "G4":
            result.append(gate("G4", kinds=("EXACT_HEAD_CI",), revision="HEAD"))
        else:
            result.append(gate(gate_id))
    return result


def test_all_evidenced_gates_can_reach_verified_complete():
    result = evaluate_snapshot(snapshot(complete_gates()))
    assert result.gate_final_total == 80
    assert result.authorization_percentage == 100
    assert result.apex_verified_complete is True
    assert result.reasons == ()


def test_partial_gate_receives_zero_final_credit():
    gates = complete_gates()
    gates[0] = gate("G2", state="PARTIAL")
    result = evaluate_snapshot(snapshot(gates))
    assert next(item for item in result.gate_evaluations if item.gate_id == "G2").final_credit == 0
    assert result.apex_verified_complete is False


def test_verified_gate_without_required_evidence_is_invalid():
    gates = complete_gates()
    gates[0] = GateRecord(
        gate_id="G2",
        state="VERIFIED_COMPLETE",
        required_evidence_types=("DEVPOST_MATRIX",),
        evidence=(),
    )
    result = evaluate_snapshot(snapshot(gates))
    evaluated = next(item for item in result.gate_evaluations if item.gate_id == "G2")
    assert evaluated.final_credit == 0
    assert evaluated.valid is False
    assert "MISSING_EVIDENCE_TYPE:DEVPOST_MATRIX" in evaluated.reasons


def test_g4_old_ci_is_invalid_after_head_changes():
    gates = complete_gates()
    gates[2] = GateRecord(
        gate_id="G4",
        state="VERIFIED_COMPLETE",
        required_evidence_types=("EXACT_HEAD_CI",),
        evidence=(evidence("EXACT_HEAD_CI", revision="OLD"),),
        candidate_revision="HEAD",
    )
    result = evaluate_snapshot(snapshot(gates))
    evaluated = next(item for item in result.gate_evaluations if item.gate_id == "G4")
    assert evaluated.final_credit == 0
    assert "G4_CI_REVISION_MISMATCH" in evaluated.reasons


def test_g4_candidate_must_equal_current_integration_head():
    gates = complete_gates()
    gates[2] = gate("G4", kinds=("EXACT_HEAD_CI",), revision="OLD")
    result = evaluate_snapshot(snapshot(gates))
    evaluated = next(item for item in result.gate_evaluations if item.gate_id == "G4")
    assert "G4_CANDIDATE_NOT_CURRENT_INTEGRATION_HEAD" in evaluated.reasons


def test_prompt_or_plan_cannot_satisfy_required_receipt_type():
    gates = complete_gates()
    gates[4] = GateRecord(
        gate_id="G6",
        state="IMPLEMENTED",
        required_evidence_types=("DEPLOYMENT_RECEIPT",),
        evidence=(evidence("PLAN"),),
    )
    result = evaluate_snapshot(snapshot(gates))
    evaluated = next(item for item in result.gate_evaluations if item.gate_id == "G6")
    assert evaluated.final_credit == 0
    assert "MISSING_EVIDENCE_TYPE:DEPLOYMENT_RECEIPT" in evaluated.reasons


def test_global_completion_requires_facts_authorization_revenue_and_no_blockers():
    result = evaluate_snapshot(
        snapshot(
            complete_gates(),
            underlying_facts_strict=90,
            authorization_completed=23,
            revenue_commercial_readiness=99,
            revenue_operational_readiness=99,
            critical_blockers=("external cloud",),
        )
    )
    assert result.apex_verified_complete is False
    assert "STRICT_FACTS_INCOMPLETE" in result.reasons
    assert "AUTHORIZATION_REGISTER_INCOMPLETE" in result.reasons
    assert "REVENUE_COMMERCIAL_INCOMPLETE" in result.reasons
    assert "REVENUE_OPERATIONAL_INCOMPLETE" in result.reasons
    assert "CRITICAL_BLOCKERS_PRESENT" in result.reasons
