from __future__ import annotations

from dataclasses import dataclass

from .models import GateRecord, ProgramSnapshot


@dataclass(frozen=True)
class GateEvaluation:
    gate_id: str
    internal_progress: int
    final_credit: int
    valid: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CompletionEvaluation:
    gate_evaluations: tuple[GateEvaluation, ...]
    gate_final_total: int
    authorization_percentage: float
    apex_verified_complete: bool
    reasons: tuple[str, ...]


def _evaluate_gate(gate: GateRecord, snapshot: ProgramSnapshot) -> GateEvaluation:
    reasons: list[str] = []
    evidence_by_type = {}
    for evidence in gate.evidence:
        evidence_by_type.setdefault(evidence.evidence_type, []).append(evidence)

    for required_type in gate.required_evidence_types:
        matching = evidence_by_type.get(required_type, [])
        if not matching:
            reasons.append(f"MISSING_EVIDENCE_TYPE:{required_type}")
            continue
        if not any(item.state == "PRESENT" for item in matching):
            reasons.append(f"NO_PRESENT_EVIDENCE:{required_type}")

    if gate.gate_id == "G4":
        if not gate.candidate_revision:
            reasons.append("G4_CANDIDATE_REVISION_MISSING")
        elif gate.candidate_revision != snapshot.integration_revision:
            reasons.append("G4_CANDIDATE_NOT_CURRENT_INTEGRATION_HEAD")
        exact_ci = [item for item in gate.evidence if item.evidence_type == "EXACT_HEAD_CI" and item.state == "PRESENT"]
        if not exact_ci:
            reasons.append("G4_EXACT_HEAD_CI_MISSING")
        elif not any(item.exact_revision == gate.candidate_revision for item in exact_ci):
            reasons.append("G4_CI_REVISION_MISMATCH")

    if gate.state == "VERIFIED_COMPLETE" and reasons:
        reasons.append("VERIFIED_COMPLETE_STATE_CONTRADICTS_EVIDENCE")

    if gate.state == "VERIFIED_COMPLETE" and not reasons:
        internal_progress = 100
        final_credit = 10
        valid = True
    elif gate.state == "NOT_APPLICABLE" and not reasons:
        internal_progress = 100
        final_credit = 10
        valid = True
    else:
        final_credit = 0
        valid = not (gate.state == "VERIFIED_COMPLETE" and reasons)
        internal_progress = {
            "UNKNOWN": 0,
            "BLOCKED": 0,
            "AWAITING_AUTHORIZATION": 10,
            "PARTIAL": 50,
            "IMPLEMENTED": 75,
            "VERIFIED_COMPLETE": 95,
            "NOT_APPLICABLE": 100,
        }[gate.state]

    return GateEvaluation(
        gate_id=gate.gate_id,
        internal_progress=internal_progress,
        final_credit=final_credit,
        valid=valid,
        reasons=tuple(reasons),
    )


def evaluate_snapshot(snapshot: ProgramSnapshot) -> CompletionEvaluation:
    gate_evaluations = tuple(_evaluate_gate(gate, snapshot) for gate in snapshot.gates)
    gate_map = {item.gate_id: item for item in gate_evaluations}
    global_reasons: list[str] = []

    missing_gates = sorted(set(f"G{i}" for i in range(2, 10)) - set(gate_map))
    if missing_gates:
        global_reasons.extend(f"MISSING_GATE:{gate}" for gate in missing_gates)

    invalid = [item.gate_id for item in gate_evaluations if not item.valid]
    global_reasons.extend(f"INVALID_GATE:{gate}" for gate in invalid)

    if snapshot.authorization_completed != snapshot.authorization_total:
        global_reasons.append("AUTHORIZATION_REGISTER_INCOMPLETE")
    if snapshot.underlying_facts_strict < 100:
        global_reasons.append("STRICT_FACTS_INCOMPLETE")
    if snapshot.revenue_commercial_readiness < 100:
        global_reasons.append("REVENUE_COMMERCIAL_INCOMPLETE")
    if snapshot.revenue_operational_readiness < 100:
        global_reasons.append("REVENUE_OPERATIONAL_INCOMPLETE")
    if snapshot.critical_blockers:
        global_reasons.append("CRITICAL_BLOCKERS_PRESENT")
    if any(item.final_credit != 10 for item in gate_evaluations) or missing_gates:
        global_reasons.append("GATES_INCOMPLETE")

    authorization_percentage = round(
        snapshot.authorization_completed / snapshot.authorization_total * 100,
        2,
    )
    apex_complete = not global_reasons
    return CompletionEvaluation(
        gate_evaluations=gate_evaluations,
        gate_final_total=sum(item.final_credit for item in gate_evaluations),
        authorization_percentage=authorization_percentage,
        apex_verified_complete=apex_complete,
        reasons=tuple(global_reasons),
    )
