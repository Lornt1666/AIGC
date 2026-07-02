from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class QualityKernelRecord:
    record_id: str
    created_at: str
    phase: str
    status: str
    opportunity_id: str
    proposal_id: str
    fidelity_review_id: str
    customer_satisfaction_record_id: str
    title: str
    employer: str
    source_platform: str
    source_url: str
    quality_score: int
    uncertainty_score: int
    quality_state: str
    quantum_quality_model: Dict[str, Any]
    proto_omni_cycle: Dict[str, Any]
    ontology_matrix: Dict[str, Any]
    agent_panel: List[Dict[str, Any]]
    legal_ethical_boundary: Dict[str, Any]
    disciplinary_best_practices: List[str]
    risk_flags: List[str]
    improvement_directives: List[str]
    approval_required_before_external_action: bool = True
    external_action_performed: bool = False


class Phase22AuditLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, data: Dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "timestamp": utc_now(),
            "event_type": event_type,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event_id


class QuantumAwareQualityKernel:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[QualityKernelRecord]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        proposals = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("proposals", "")))
        authorizations = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("authorizations", "")))
        finance_records = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("finance_records", "")))
        compliance_reviews = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("compliance_reviews", "")))
        fidelity_reviews = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("fidelity_reviews", "")))
        customer_records = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("customer_satisfaction_records", "")))
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase22_quality/aigc_phase22_quality_kernel_records.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase22_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase22_audit.jsonl"),
        )
        records = self.build_records(
            config=config,
            proposals=proposals,
            authorizations=authorizations,
            finance_records=finance_records,
            compliance_reviews=compliance_reviews,
            fidelity_reviews=fidelity_reviews,
            customer_records=customer_records,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        Phase22AuditLedger(audit_path).record("phase22_quality_kernel_records_exported", {
            "path": str(output_path),
            "records": len(records),
            "external_action_performed": False,
            "literal_quantum_claims_made": False,
        })
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        return records

    def build_records(
        self,
        config: Dict[str, Any],
        proposals: List[Dict[str, Any]],
        authorizations: List[Dict[str, Any]],
        finance_records: List[Dict[str, Any]],
        compliance_reviews: List[Dict[str, Any]],
        fidelity_reviews: List[Dict[str, Any]],
        customer_records: List[Dict[str, Any]],
    ) -> List[QualityKernelRecord]:
        max_records = int(config.get("max_records", 25))
        proposals_by_id = {str(item.get("proposal_id", "")): item for item in proposals}
        authorizations_by_proposal = group_by(authorizations, "proposal_id")
        finance_by_proposal = {str(item.get("proposal_id", "")): item for item in finance_records}
        compliance_by_proposal = {str(item.get("proposal_id", "")): item for item in compliance_reviews}
        fidelity_by_proposal = {str(item.get("proposal_id", "")): item for item in fidelity_reviews}
        records: List[QualityKernelRecord] = []
        for customer in customer_records:
            proposal_id = str(customer.get("proposal_id", ""))
            proposal = proposals_by_id.get(proposal_id, {})
            if not proposal:
                continue
            records.append(self._build_record(
                config=config,
                proposal=proposal,
                authorizations=authorizations_by_proposal.get(proposal_id, []),
                finance=finance_by_proposal.get(proposal_id, {}),
                compliance=compliance_by_proposal.get(proposal_id, {}),
                fidelity=fidelity_by_proposal.get(proposal_id, {}),
                customer=customer,
            ))
            if len(records) >= max_records:
                break
        return records

    def _build_record(
        self,
        config: Dict[str, Any],
        proposal: Dict[str, Any],
        authorizations: List[Dict[str, Any]],
        finance: Dict[str, Any],
        compliance: Dict[str, Any],
        fidelity: Dict[str, Any],
        customer: Dict[str, Any],
    ) -> QualityKernelRecord:
        quality_score, uncertainty_score = score_quality(proposal, authorizations, finance, compliance, fidelity, customer)
        thresholds = config.get("score_thresholds", {})
        quality_state = quality_state_for(
            score=quality_score,
            uncertainty=uncertainty_score,
            compliance_status=str(compliance.get("compliance_status", "missing")),
            ascended=int(thresholds.get("ascended_ready", 90)),
            high=int(thresholds.get("high_quality_review", 80)),
            improvement=int(thresholds.get("improvement_required", 65)),
        )
        risk_flags = collect_risk_flags(authorizations, finance, compliance, fidelity, customer, uncertainty_score)
        directives = improvement_directives_for(quality_state, risk_flags, fidelity, customer)
        ontology_matrix = build_ontology_matrix(config, proposal, compliance, fidelity, customer, quality_score, uncertainty_score)
        quantum_model = build_quantum_quality_model(quality_score, uncertainty_score, compliance, fidelity, customer, authorizations)
        proto_cycle = build_proto_omni_cycle(proposal, fidelity, customer, ontology_matrix, quality_state, directives)
        agent_panel = build_agent_panel(config, quality_state, risk_flags, directives)
        legal_boundary = build_legal_ethical_boundary(config, compliance, authorizations)
        proposal_id = str(proposal.get("proposal_id", ""))
        opportunity_id = str(proposal.get("opportunity_id", customer.get("opportunity_id", "")))
        return QualityKernelRecord(
            record_id=make_record_id(proposal_id, opportunity_id),
            created_at=utc_now(),
            phase="phase22_quantum_aware_quality_kernel",
            status="internal_quality_state_recorded",
            opportunity_id=opportunity_id,
            proposal_id=proposal_id,
            fidelity_review_id=str(fidelity.get("review_id", "")),
            customer_satisfaction_record_id=str(customer.get("record_id", "")),
            title=str(proposal.get("title") or customer.get("title") or ""),
            employer=str(proposal.get("employer") or customer.get("employer") or ""),
            source_platform=str(proposal.get("source_platform") or customer.get("source_platform") or ""),
            source_url=str(proposal.get("source_url") or customer.get("source_url") or ""),
            quality_score=quality_score,
            uncertainty_score=uncertainty_score,
            quality_state=quality_state,
            quantum_quality_model=quantum_model,
            proto_omni_cycle=proto_cycle,
            ontology_matrix=ontology_matrix,
            agent_panel=agent_panel,
            legal_ethical_boundary=legal_boundary,
            disciplinary_best_practices=[str(item) for item in config.get("best_practice_standards", [])],
            risk_flags=risk_flags,
            improvement_directives=directives,
            approval_required_before_external_action=True,
            external_action_performed=False,
        )

    def signature_update(self, records: List[QualityKernelRecord]) -> str:
        counts = {
            state: len([record for record in records if record.quality_state == state])
            for state in [
                "ascended_ready_for_human_approval_review",
                "high_quality_superposition_review_required",
                "improvement_required_before_approval_review",
                "blocked_until_quality_repair",
            ]
        }
        average = round(sum(record.quality_score for record in records) / len(records), 2) if records else 0
        uncertainty = round(sum(record.uncertainty_score for record in records) / len(records), 2) if records else 0
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 22 - Quantum-Aware Quality Kernel",
            "Operational Identity:",
            "Internal Ascended Quality, Ology, and Uncertainty-Aware Review Layer",
            "Action Performed:",
            "Generated internal quality-kernel records from governed AIGC artifacts.",
            "Safety Review:",
            "No literal quantum cognition claimed.",
            "No external action performed.",
            "No approvals granted.",
            "No customers contacted.",
            "No contracts accepted.",
            "No credentials used.",
            f"Quality Kernel Records Created: {len(records)}",
            f"Average Quality Score: {average}",
            f"Average Uncertainty Score: {uncertainty}",
            f"Ascended Ready: {counts['ascended_ready_for_human_approval_review']}",
            f"High Quality Review Required: {counts['high_quality_superposition_review_required']}",
            f"Improvement Required: {counts['improvement_required_before_approval_review']}",
            f"Blocked Until Repair: {counts['blocked_until_quality_repair']}",
            "Approval Required:",
            "Yes, before any reviewed artifact can become an external action.",
        ]).strip() + "\n"


def score_quality(
    proposal: Dict[str, Any],
    authorizations: List[Dict[str, Any]],
    finance: Dict[str, Any],
    compliance: Dict[str, Any],
    fidelity: Dict[str, Any],
    customer: Dict[str, Any],
) -> tuple[int, int]:
    fidelity_score = int(fidelity.get("fidelity_score", 0) or 0)
    chi_score = int(customer.get("chi_score", 0) or 0)
    compliance_score = compliance_score_for(str(compliance.get("compliance_status", "missing")))
    authorization_score = authorization_score_for(authorizations)
    finance_score = max(0, 100 - 8 * len(finance.get("blockers", [])))
    best_practice_score = best_practice_score_for(proposal, fidelity, customer)
    raw_score = (
        0.28 * fidelity_score
        + 0.22 * chi_score
        + 0.18 * compliance_score
        + 0.12 * authorization_score
        + 0.10 * finance_score
        + 0.10 * best_practice_score
    )
    uncertainty = uncertainty_score_for(authorizations, finance, compliance, fidelity, customer)
    final_score = round(raw_score - (uncertainty * 0.12))
    return max(0, min(100, final_score)), uncertainty


def compliance_score_for(status: str) -> int:
    return {
        "green": 100,
        "yellow": 88,
        "orange": 74,
        "red": 20,
        "missing": 55,
    }.get(status, 55)


def authorization_score_for(authorizations: List[Dict[str, Any]]) -> int:
    if not authorizations:
        return 50
    decisions = {str(item.get("decision", "")) for item in authorizations}
    if "approved_for_phase_6" in decisions:
        return 100
    if "pending" in decisions:
        return 72
    if "revision_required" in decisions:
        return 55
    if "denied" in decisions or "blocked_by_safety" in decisions:
        return 20
    return 50


def best_practice_score_for(proposal: Dict[str, Any], fidelity: Dict[str, Any], customer: Dict[str, Any]) -> int:
    signals = [
        bool(proposal.get("source_url")),
        bool(proposal.get("audit_summary")),
        bool(proposal.get("ai_use_disclosure")),
        bool(proposal.get("forbidden_actions")),
        bool(proposal.get("quality_assurance_plan")),
        int(fidelity.get("fidelity_score", 0) or 0) >= 90,
        int(customer.get("chi_score", 0) or 0) >= 85,
    ]
    return round(100 * sum(1 for item in signals if item) / len(signals))


def uncertainty_score_for(
    authorizations: List[Dict[str, Any]],
    finance: Dict[str, Any],
    compliance: Dict[str, Any],
    fidelity: Dict[str, Any],
    customer: Dict[str, Any],
) -> int:
    uncertainty = 8
    if not authorizations or any(item.get("decision") == "pending" for item in authorizations):
        uncertainty += 12
    compliance_status = str(compliance.get("compliance_status", "missing"))
    if compliance_status == "yellow":
        uncertainty += 8
    elif compliance_status == "orange":
        uncertainty += 15
    elif compliance_status == "red":
        uncertainty += 35
    elif compliance_status == "missing":
        uncertainty += 18
    uncertainty += min(20, 6 * len(finance.get("blockers", [])))
    uncertainty += min(18, 3 * len(fidelity.get("risk_flags", [])))
    uncertainty += min(18, 3 * len(customer.get("risk_flags", [])))
    if customer.get("measurement_stage") == "pre_external_action":
        uncertainty += 8
    return max(0, min(100, uncertainty))


def quality_state_for(
    score: int,
    uncertainty: int,
    compliance_status: str,
    ascended: int,
    high: int,
    improvement: int,
) -> str:
    if compliance_status == "red" or score < improvement:
        return "blocked_until_quality_repair"
    if score >= ascended and uncertainty <= 25:
        return "ascended_ready_for_human_approval_review"
    if score >= high:
        return "high_quality_superposition_review_required"
    return "improvement_required_before_approval_review"


def collect_risk_flags(
    authorizations: List[Dict[str, Any]],
    finance: Dict[str, Any],
    compliance: Dict[str, Any],
    fidelity: Dict[str, Any],
    customer: Dict[str, Any],
    uncertainty_score: int,
) -> List[str]:
    flags: List[str] = []
    flags.extend(str(item) for item in finance.get("blockers", []) if item)
    flags.extend(str(item) for item in compliance.get("risk_flags", []) if item)
    flags.extend(str(item) for item in fidelity.get("risk_flags", []) if item)
    flags.extend(str(item) for item in customer.get("risk_flags", []) if item)
    status = str(compliance.get("compliance_status", "missing"))
    if status in {"orange", "red", "missing"}:
        flags.append(f"compliance_{status}")
    if not authorizations or any(item.get("decision") == "pending" for item in authorizations):
        flags.append("phase5_approval_pending")
    if uncertainty_score >= 50:
        flags.append("high_quality_uncertainty")
    return unique(flags)


def improvement_directives_for(
    quality_state: str,
    risk_flags: List[str],
    fidelity: Dict[str, Any],
    customer: Dict[str, Any],
) -> List[str]:
    directives: List[str] = []
    if quality_state != "ascended_ready_for_human_approval_review":
        directives.append("Keep artifact in internal review until uncertainty and approval gates are resolved.")
    if "phase5_approval_pending" in risk_flags:
        directives.append("Resolve Phase 5 authorization before any Phase 6 action can be considered.")
    if "compliance_orange" in risk_flags or "compliance_red" in risk_flags:
        directives.append("Run explicit operator compliance review before external action.")
    if "pay_or_budget_not_visible" in risk_flags or "pay_interval_unknown" in risk_flags:
        directives.append("Clarify payment and contract expectations before commitment.")
    directives.extend(str(item) for item in fidelity.get("revision_recommendations", []) if item)
    directives.extend(str(item) for item in customer.get("improvement_actions", []) if item)
    if not directives:
        directives.append("Preserve current quality posture and proceed only to human approval review.")
    return unique(directives)


def build_ontology_matrix(
    config: Dict[str, Any],
    proposal: Dict[str, Any],
    compliance: Dict[str, Any],
    fidelity: Dict[str, Any],
    customer: Dict[str, Any],
    quality_score: int,
    uncertainty_score: int,
) -> Dict[str, Any]:
    title = str(proposal.get("title", ""))
    matrix: Dict[str, Any] = {}
    for ology in config.get("ologys", []):
        matrix[str(ology)] = {
            "status": "reviewed",
            "quality_signal": quality_score,
            "uncertainty_signal": uncertainty_score,
            "evidence": evidence_for_ology(str(ology), title, proposal, compliance, fidelity, customer),
        }
    return matrix


def evidence_for_ology(
    ology: str,
    title: str,
    proposal: Dict[str, Any],
    compliance: Dict[str, Any],
    fidelity: Dict[str, Any],
    customer: Dict[str, Any],
) -> str:
    evidence = {
        "ontology": f"Work object mapped as {title}.",
        "epistemology": "Known facts are sourced from governed proposal, fidelity, compliance, and CHI artifacts.",
        "methodology": "Execution remains blueprint-driven through contract-first phase artifacts.",
        "praxeology": "Action is optimized by blocking external movement until approval and uncertainty gates resolve.",
        "axiology": "Values prioritize legality, ethics, professionalism, auditability, and customer trust.",
        "teleology": "Goal is high-quality work readiness without unsafe external execution.",
        "semiotics": "Customer-facing language and internal risk signals are interpreted as quality evidence.",
        "cybernetics": "Feedback comes from fidelity risks, CHI risks, compliance flags, and improvement directives.",
        "systems_theory": "Quality integrates proposal, finance, compliance, authorization, fidelity, and satisfaction subsystems.",
        "ethics": f"Compliance status is {compliance.get('compliance_status', 'missing')}.",
        "jurisprudence": "Legal-sensitive movement remains operator-gated.",
        "risk_theory": f"Recorded fidelity risks: {len(fidelity.get('risk_flags', []))}; CHI risks: {len(customer.get('risk_flags', []))}.",
    }
    return evidence.get(ology, "Reviewed as part of the Phase 22 ology capability matrix.")


def build_quantum_quality_model(
    quality_score: int,
    uncertainty_score: int,
    compliance: Dict[str, Any],
    fidelity: Dict[str, Any],
    customer: Dict[str, Any],
    authorizations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "model_type": "deterministic_uncertainty_aware_quality_state_model",
        "literal_quantum_claim": false_json(),
        "quality_probability": round(quality_score / 100, 4),
        "uncertainty_probability": round(uncertainty_score / 100, 4),
        "state_components": {
            "technical_fidelity": round(int(fidelity.get("fidelity_score", 0) or 0) / 100, 4),
            "customer_fit": round(int(customer.get("chi_score", 0) or 0) / 100, 4),
            "compliance_integrity": round(compliance_score_for(str(compliance.get("compliance_status", "missing"))) / 100, 4),
            "approval_resolution": round(authorization_score_for(authorizations) / 100, 4),
        },
        "collapse_conditions": [
            "contract validation passes",
            "secret scan passes",
            "compliance review is not red",
            "Phase 5 exact approval exists before external action",
            "Phase 6 execution scope matches the approved action",
            "operator accepts remaining uncertainty explicitly",
        ],
    }


def build_proto_omni_cycle(
    proposal: Dict[str, Any],
    fidelity: Dict[str, Any],
    customer: Dict[str, Any],
    ontology_matrix: Dict[str, Any],
    quality_state: str,
    directives: List[str],
) -> Dict[str, Any]:
    return {
        "perfect_draft_v1": {
            "summary": "Initial internal quality synthesis from currently available governed artifacts.",
            "proposal_status": proposal.get("status", ""),
            "fidelity_score": fidelity.get("fidelity_score", 0),
            "chi_score": customer.get("chi_score", 0),
        },
        "ontological_self_audit": {
            "ology_count": len(ontology_matrix),
            "critical_findings": directives,
            "quality_state_before_external_action": quality_state,
        },
        "ascended_output_v2": {
            "quality_state": quality_state,
            "improvement_directives": directives,
            "external_action_authorized": False,
        },
    }


def build_agent_panel(config: Dict[str, Any], quality_state: str, risk_flags: List[str], directives: List[str]) -> List[Dict[str, Any]]:
    panel: List[Dict[str, Any]] = []
    for role in config.get("agent_panel", []):
        panel.append({
            "role": str(role),
            "status": "internal_review_only",
            "finding": finding_for_role(str(role), quality_state, risk_flags),
            "directive": directives[0] if directives else "Preserve quality state and await operator gate.",
            "external_action_allowed": False,
        })
    return panel


def finding_for_role(role: str, quality_state: str, risk_flags: List[str]) -> str:
    if "Compliance" in role or "Ethics" in role:
        return "Legal, ethical, and approval boundaries remain active."
    if "Risk" in role:
        return f"Risk flags visible: {len(risk_flags)}."
    if "Technical" in role:
        return f"Technical quality state is {quality_state}."
    if "Meta" in role:
        return "Self-evaluation completed with explicit uncertainty."
    return "Internal quality review completed."


def build_legal_ethical_boundary(
    config: Dict[str, Any],
    compliance: Dict[str, Any],
    authorizations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "external_action_blocked": True,
        "approval_gate_required": True,
        "phase5_approval_present": any(item.get("decision") == "approved_for_phase_6" for item in authorizations),
        "compliance_status": compliance.get("compliance_status", "missing"),
        "secrets_used": False,
        "forbidden_behaviors": [str(item) for item in config.get("forbidden_behaviors", [])],
    }


def make_record_id(proposal_id: str, opportunity_id: str) -> str:
    seed = f"{proposal_id}|{opportunity_id}|phase22"
    return "AIGC-QK-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def group_by(records: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get(key, "")), []).append(record)
    return grouped


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


def false_json() -> bool:
    return False


def load_json_dict(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def load_json_list_if_exists(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return payload


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run AIGC Phase 22 quantum-aware quality kernel.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase22_quantum_quality_kernel.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = QuantumAwareQualityKernel(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nQuality kernel records exported: {args.project_root / 'data' / 'phase22_quality' / 'aigc_phase22_quality_kernel_records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
