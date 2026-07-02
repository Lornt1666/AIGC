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
class WorkOrderGovernanceRecord:
    record_id: str
    created_at: str
    phase: str
    status: str
    source_quality_record_id: str
    work_order_id: str
    opportunity_id: str
    proposal_id: str
    title: str
    employer: str
    source_platform: str
    source_url: str
    mission: str
    perfect_draft_v1: Dict[str, Any]
    ontological_self_audit: Dict[str, Any]
    ascended_output_v2: Dict[str, Any]
    ology_matrix: Dict[str, Any]
    agent_orchestration: List[Dict[str, Any]]
    quantum_quality_state: Dict[str, Any]
    legal_ethical_superstructure: Dict[str, Any]
    capability_procurements: List[str]
    required_next_actions: List[str]
    blocked_actions: List[str]
    approval_required_before_external_action: bool = True
    external_action_performed: bool = False


class Phase23AuditLedger:
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


class AscendedWorkOrderGovernor:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[WorkOrderGovernanceRecord]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        quality_records = load_json_list_if_exists(
            resolve_project_path(self.project_root, inputs.get("quality_kernel_records", ""))
        )
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase23_work_orders/aigc_phase23_work_order_governance_records.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase23_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase23_audit.jsonl"),
        )
        records = self.build_records(config, quality_records)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        Phase23AuditLedger(audit_path).record("phase23_work_order_governance_records_exported", {
            "path": str(output_path),
            "records": len(records),
            "external_action_performed": False,
            "literal_quantum_claims_made": False,
        })
        return records

    def build_records(
        self,
        config: Dict[str, Any],
        quality_records: List[Dict[str, Any]],
    ) -> List[WorkOrderGovernanceRecord]:
        max_records = int(config.get("max_records", 25))
        records: List[WorkOrderGovernanceRecord] = []
        for quality in quality_records[:max_records]:
            records.append(self._build_record(config, quality))
        return records

    def _build_record(
        self,
        config: Dict[str, Any],
        quality: Dict[str, Any],
    ) -> WorkOrderGovernanceRecord:
        work_order_id = str(quality.get("proposal_id") or quality.get("opportunity_id") or quality.get("record_id", ""))
        title = str(quality.get("title", "Untitled governed work order"))
        quality_score = int(quality.get("quality_score", 0) or 0)
        uncertainty_score = int(quality.get("uncertainty_score", 100) or 100)
        risk_flags = [str(item) for item in quality.get("risk_flags", [])]
        directives = [str(item) for item in quality.get("improvement_directives", [])]
        blocked_actions = [str(item) for item in config.get("blocked_actions", [])]
        next_actions = build_next_actions(quality_score, uncertainty_score, risk_flags, directives)
        ology_matrix = build_ology_matrix(config, quality, next_actions)
        perfect_draft = build_perfect_draft_v1(title, quality, next_actions)
        self_audit = build_ontological_self_audit(quality, ology_matrix, risk_flags, next_actions)
        ascended = build_ascended_output_v2(title, quality, next_actions, blocked_actions)
        agent_orchestration = build_agent_orchestration(config, quality, next_actions)
        quantum_state = build_quantum_quality_state(quality, next_actions)
        legal_ethical = build_legal_ethical_superstructure(quality, blocked_actions)
        return WorkOrderGovernanceRecord(
            record_id=make_record_id(work_order_id, str(quality.get("record_id", ""))),
            created_at=utc_now(),
            phase="phase23_ascended_work_order_governor",
            status="internal_work_order_governance_recorded",
            source_quality_record_id=str(quality.get("record_id", "")),
            work_order_id=work_order_id,
            opportunity_id=str(quality.get("opportunity_id", "")),
            proposal_id=str(quality.get("proposal_id", "")),
            title=title,
            employer=str(quality.get("employer", "")),
            source_platform=str(quality.get("source_platform", "")),
            source_url=str(quality.get("source_url", "")),
            mission=f"Govern the work order for {title} through v1 draft, ology self-audit, and ascended v2 readiness.",
            perfect_draft_v1=perfect_draft,
            ontological_self_audit=self_audit,
            ascended_output_v2=ascended,
            ology_matrix=ology_matrix,
            agent_orchestration=agent_orchestration,
            quantum_quality_state=quantum_state,
            legal_ethical_superstructure=legal_ethical,
            capability_procurements=[str(item) for item in config.get("capability_procurements", [])],
            required_next_actions=next_actions,
            blocked_actions=blocked_actions,
            approval_required_before_external_action=True,
            external_action_performed=False,
        )

    def signature_update(self, records: List[WorkOrderGovernanceRecord]) -> str:
        average_quality = round(
            sum(int(record.quantum_quality_state.get("quality_score", 0)) for record in records) / len(records),
            2,
        ) if records else 0
        average_uncertainty = round(
            sum(int(record.quantum_quality_state.get("uncertainty_score", 0)) for record in records) / len(records),
            2,
        ) if records else 0
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 23 - Ascended Work Order Governor",
            "Operational Identity:",
            "Internal Work-Order Quality Application Layer",
            "Action Performed:",
            "Generated internal work-order governance records with v1 draft, ology self-audit, and ascended v2 output.",
            "Safety Review:",
            "No literal quantum cognition claimed.",
            "No external action performed.",
            "No approvals granted.",
            "No customers contacted.",
            "No contracts accepted.",
            "No credentials used.",
            f"Work Order Governance Records Created: {len(records)}",
            f"Average Quality Score: {average_quality}",
            f"Average Uncertainty Score: {average_uncertainty}",
            "Approval Required:",
            "Yes, before any governed work order can become an external action.",
        ]).strip() + "\n"


def build_next_actions(
    quality_score: int,
    uncertainty_score: int,
    risk_flags: List[str],
    directives: List[str],
) -> List[str]:
    actions: List[str] = []
    if uncertainty_score >= 50:
        actions.append("Reduce uncertainty before external action by resolving approval, compliance, scope, and payment blockers.")
    if quality_score < 90:
        actions.append("Improve the work order until it meets ascended readiness or receives explicit operator acceptance of residual risk.")
    if "phase5_approval_pending" in risk_flags:
        actions.append("Resolve Phase 5 approval before any Phase 6 handoff.")
    if any(flag.startswith("compliance_") for flag in risk_flags):
        actions.append("Complete explicit compliance review before customer contact or delivery.")
    actions.extend(directives)
    if not actions:
        actions.append("Preserve current quality posture and proceed only to human approval review.")
    return unique(actions)


def build_perfect_draft_v1(title: str, quality: Dict[str, Any], next_actions: List[str]) -> Dict[str, Any]:
    return {
        "draft_type": "internal_work_order_readiness_blueprint",
        "work_order_title": title,
        "initial_quality_state": quality.get("quality_state", ""),
        "quality_score": quality.get("quality_score", 0),
        "uncertainty_score": quality.get("uncertainty_score", 0),
        "proposed_internal_execution_posture": "prepare_only_until_approval_gates_resolve",
        "initial_required_actions": next_actions[:5],
    }


def build_ontological_self_audit(
    quality: Dict[str, Any],
    ology_matrix: Dict[str, Any],
    risk_flags: List[str],
    next_actions: List[str],
) -> Dict[str, Any]:
    return {
        "audit_type": "structured_ology_self_audit",
        "ology_count": len(ology_matrix),
        "technical_correctness": "inherited_from_phase22_quality_kernel",
        "epistemic_validity": "bounded_by_available_governed_artifacts",
        "legal_ethical_compliance": quality.get("legal_ethical_boundary", {}).get("compliance_status", "missing"),
        "risk_flags": risk_flags,
        "weaknesses_or_missing_components": next_actions,
        "external_action_authorized": False,
    }


def build_ascended_output_v2(
    title: str,
    quality: Dict[str, Any],
    next_actions: List[str],
    blocked_actions: List[str],
) -> Dict[str, Any]:
    return {
        "output_type": "ascended_internal_work_order_governance",
        "work_order_title": title,
        "quality_state": quality.get("quality_state", ""),
        "application_standard": "highest_feasible_internal_quality_under_current_evidence_and_approval_boundaries",
        "governed_execution_blueprint": [
            "validate contracts",
            "preserve source traceability",
            "apply legal and ethical gate",
            "apply security and secret-isolation gate",
            "resolve required next actions",
            "wait for exact scoped human approval before external action",
        ],
        "required_next_actions": next_actions,
        "blocked_actions": blocked_actions,
        "external_action_authorized": False,
    }


def build_ology_matrix(config: Dict[str, Any], quality: Dict[str, Any], next_actions: List[str]) -> Dict[str, Any]:
    matrix: Dict[str, Any] = {}
    for ology in config.get("ology_matrix", []):
        name = str(ology)
        matrix[name] = {
            "status": "applied",
            "evidence": evidence_for_ology(name, quality),
            "next_action_count": len(next_actions),
        }
    return matrix


def evidence_for_ology(ology: str, quality: Dict[str, Any]) -> str:
    title = str(quality.get("title", "work order"))
    evidence = {
        "ontology": f"Work order object mapped as {title}.",
        "epistemology": "Knowledge is bounded by Phase 22 quality records and upstream governed artifacts.",
        "methodology": "The work order is forced through v1 draft, self-audit, and v2 output.",
        "praxeology": "Action is optimized by resolving blockers before execution.",
        "axiology": "Values prioritize legality, ethics, professionalism, quality, and auditability.",
        "teleology": "Goal is highest feasible work readiness without unsafe execution.",
        "cybernetics": "Feedback is applied through required next actions and quality-state uncertainty.",
        "systems_theory": "The work order integrates quality, compliance, approval, finance, and customer-fit subsystems.",
        "ethics": "External action remains blocked until ethical and approval gates are satisfied.",
        "jurisprudence": "Legal-sensitive movement remains operator-gated.",
        "risk_theory": f"Risk flags visible: {len(quality.get('risk_flags', []))}.",
    }
    return evidence.get(ology, "Applied as part of the Phase 23 ology capability matrix.")


def build_agent_orchestration(config: Dict[str, Any], quality: Dict[str, Any], next_actions: List[str]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for role in config.get("agent_orchestration", []):
        role_name = str(role)
        records.append({
            "role": role_name,
            "status": "internal_governance_only",
            "finding": finding_for_role(role_name, quality),
            "directive": next_actions[0] if next_actions else "Proceed only to human approval review.",
            "external_action_allowed": False,
        })
    return records


def finding_for_role(role: str, quality: Dict[str, Any]) -> str:
    quality_state = str(quality.get("quality_state", "unknown"))
    if "Meta" in role:
        return "Work-order self-awareness expressed as explicit quality state and uncertainty."
    if "Technical" in role:
        return f"Technical readiness inherits Phase 22 quality state: {quality_state}."
    if "Compliance" in role or "Ethics" in role:
        return "Legal and ethical gates remain active."
    if "Risk" in role:
        return f"Risk flags visible: {len(quality.get('risk_flags', []))}."
    return "Internal work-order governance applied."


def build_quantum_quality_state(quality: Dict[str, Any], next_actions: List[str]) -> Dict[str, Any]:
    quality_score = int(quality.get("quality_score", 0) or 0)
    uncertainty_score = int(quality.get("uncertainty_score", 100) or 100)
    return {
        "model_type": "deterministic_uncertainty_aware_work_order_quality_state",
        "literal_quantum_claim": False,
        "quality_score": quality_score,
        "uncertainty_score": uncertainty_score,
        "quality_probability": round(quality_score / 100, 4),
        "uncertainty_probability": round(uncertainty_score / 100, 4),
        "state_collapse_ready": uncertainty_score <= 25 and quality_score >= 90 and not next_actions,
        "collapse_conditions": [
            "contract validation passes",
            "secret scan passes",
            "required next actions resolved",
            "compliance gate clears",
            "Phase 5 exact approval exists before external action",
            "Phase 6 scope matches the approved action",
        ],
    }


def build_legal_ethical_superstructure(quality: Dict[str, Any], blocked_actions: List[str]) -> Dict[str, Any]:
    boundary = quality.get("legal_ethical_boundary", {})
    return {
        "external_action_blocked": True,
        "approval_gate_required": True,
        "phase5_approval_present": bool(boundary.get("phase5_approval_present", False)),
        "compliance_status": boundary.get("compliance_status", "missing"),
        "secrets_used": False,
        "privacy_preserved": True,
        "blocked_actions": blocked_actions,
    }


def make_record_id(work_order_id: str, quality_record_id: str) -> str:
    seed = f"{work_order_id}|{quality_record_id}|phase23"
    return "AIGC-WOG-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 23 ascended work-order governor.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase23_work_order_governor.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = AscendedWorkOrderGovernor(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nWork-order governance records exported: {args.project_root / 'data' / 'phase23_work_orders' / 'aigc_phase23_work_order_governance_records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
