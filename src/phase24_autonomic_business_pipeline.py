from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class AutonomicBusinessRecord:
    record_id: str
    created_at: str
    phase: str
    status: str
    action_id: str
    authorization_id: str
    proposal_id: str
    opportunity_id: str
    recipient: str
    platform: str
    work_order_title: str
    business_pipeline: List[Dict[str, Any]]
    neural_microcycle: Dict[str, Any]
    business_agent_team: List[Dict[str, Any]]
    ology_review: Dict[str, Any]
    learning_measures: Dict[str, Any]
    approval_state: Dict[str, Any]
    blocked_reasons: List[str]
    blocked_behaviors: List[str]
    governed_next_action: str
    external_action_performed: bool = False
    audit_event_ids: List[str] = field(default_factory=list)


class Phase24AuditLedger:
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


class AutonomicBusinessPipeline:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[AutonomicBusinessRecord]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        authorizations = load_json_list_if_exists(
            resolve_project_path(self.project_root, inputs.get("phase5_authorizations", ""))
        )
        work_orders = load_json_list_if_exists(
            resolve_project_path(self.project_root, inputs.get("phase23_work_orders", ""))
        )
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase24_business_pipeline/aigc_phase24_business_pipeline_records.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase24_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase24_audit.jsonl"),
        )
        work_order_index = index_work_orders_by_proposal(work_orders)
        records = [
            self.build_record(config, authorization, work_order_index.get(str(authorization.get("proposal_id", ""))))
            for authorization in authorizations[: int(config.get("max_records", 25))]
        ]
        event_id = Phase24AuditLedger(audit_path).record(
            "phase24_autonomic_business_pipeline_exported",
            {
                "path": str(output_path),
                "records": len(records),
                "external_action_performed": False,
            },
        )
        for record in records:
            record.audit_event_ids.append(event_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(config, records), encoding="utf-8")
        return records

    def build_record(
        self,
        config: Dict[str, Any],
        authorization: Dict[str, Any],
        work_order: Dict[str, Any] | None,
    ) -> AutonomicBusinessRecord:
        work_order = work_order or {}
        action_id = str(authorization.get("action_id", ""))
        authorization_id = str(authorization.get("authorization_id", ""))
        proposal_id = str(authorization.get("proposal_id", ""))
        title = str(work_order.get("title") or authorization.get("proposed_external_action") or "governed business work")
        approval = authorization.get("approval", {}) or {}
        phase6 = authorization.get("phase6_status", {}) or {}
        decision = str(authorization.get("decision", "pending"))
        expired = authorization_expired(str(authorization.get("expires_at", "")))
        quality_state = work_order_quality_state(work_order)
        blocked = blocked_reasons(authorization, expired, quality_state)
        status = status_from(decision, expired, blocked)
        return AutonomicBusinessRecord(
            record_id=make_record_id(action_id, authorization_id),
            created_at=utc_now(),
            phase="phase24_autonomic_business_pipeline",
            status=status,
            action_id=action_id,
            authorization_id=authorization_id,
            proposal_id=proposal_id,
            opportunity_id=str(authorization.get("opportunity_id", "")),
            recipient=str(authorization.get("recipient", "")),
            platform=str(authorization.get("platform", "")),
            work_order_title=title,
            business_pipeline=business_pipeline(title),
            neural_microcycle=neural_microcycle(action_id, title, blocked),
            business_agent_team=business_agents(title, quality_state),
            ology_review=ology_review(config, title),
            learning_measures=learning_measures(authorization, work_order, blocked),
            approval_state={
                "decision": decision,
                "approved": bool(approval.get("approved", False)),
                "authorized_for_phase6": bool(phase6.get("authorized_for_phase6", False)),
                "expires_at": str(authorization.get("expires_at", "")),
                "expired": expired,
            },
            blocked_reasons=blocked,
            blocked_behaviors=[str(item) for item in config.get("blocked_behaviors", [])],
            governed_next_action=governed_next_action(status),
            external_action_performed=False,
        )

    def signature_update(self, config: Dict[str, Any], records: List[AutonomicBusinessRecord]) -> str:
        approved = [record for record in records if record.status == "approved_for_handoff_readiness"]
        pending = [record for record in records if record.status == "waiting_for_human_review"]
        blocked = [record for record in records if record.blocked_reasons]
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            str((config.get("identity_policy", {}) or {}).get("operator_name", "Justice Gray Maciocha")),
            "Phase:",
            "Phase 24 - Autonomic Business Pipeline",
            "Operational Identity:",
            "Transparent authorized business operator with neural-style microfunctions and multidisciplinary business agents.",
            "Action Performed:",
            "Generated start-to-finished-project business pipeline records: find work, ingest job, research job, best practices, deep-dive work scope, learning measures, agent design, internal agent use, and governed handoff readiness.",
            "Safety Review:",
            "No outward action performed by this phase.",
            "No hidden identity claim added.",
            "No credentials used.",
            "No contracts accepted.",
            "No payment requested.",
            f"Business Pipeline Records Created: {len(records)}",
            f"Approved For Handoff Readiness: {len(approved)}",
            f"Waiting For Human Review: {len(pending)}",
            f"Blocked Or Needs Revision: {len(blocked)}",
        ]).strip() + "\n"


def business_pipeline(title: str) -> List[Dict[str, Any]]:
    stages = [
        ("find_work", "Discover approved sources and rank viable work by value, fit, safety, and legality."),
        ("ingest_job", f"Convert the opportunity into a structured work order: {title}."),
        ("research_job", "Research customer, role, domain, constraints, context, and success criteria."),
        ("find_best_practices", "Synthesize standards across business, technology, communication, compliance, and delivery."),
        ("deep_dive_into_work", "Map hidden requirements, assumptions, risks, proof artifacts, and implementation plan."),
        ("instantiate_learning_measures", "Define quality deltas, uncertainty reduction, customer-fit score, and outcome learning."),
        ("design_appropriate_agents", "Choose specialist agents and bind each to role, inputs, outputs, checks, and limits."),
        ("use_agents", "Use agents to prepare internal drafts, implementation plans, reviews, and audit-ready handoffs."),
        ("governed_handoff", "Move only visible, approved, non-expired artifacts into manual handoff readiness."),
        ("evolve_structure", "Feed outcomes into memory, metrics, and next-cycle improvement patches."),
    ]
    return [
        {
            "stage": name,
            "purpose": purpose,
            "external_action_performed": False,
        }
        for name, purpose in stages
    ]


def neural_microcycle(action_id: str, title: str, blocked: List[str]) -> Dict[str, Any]:
    return {
        "model": "deterministic_neural_style_business_microcycle",
        "sensory_intake": "Read opportunity, source, work order, authorization, risk, quality, and artifact state.",
        "attention": "Prioritize blockers, deadlines, customer value, compliance, proof quality, and uncertainty.",
        "working_memory": {
            "action_id": action_id,
            "work_order": title,
            "blocked_reason_count": len(blocked),
        },
        "valuation": "Estimate business value, delivery feasibility, trust impact, and strategic fit.",
        "planning": "Select next safe step: revise, deny, research deeper, prepare handoff, or wait for review.",
        "motor_gate": "No outward movement unless approval and governance are already satisfied.",
        "feedback": "Write reports, audit events, quality metrics, learning measures, and evolution directives.",
    }


def business_agents(title: str, quality_state: str) -> List[Dict[str, Any]]:
    roles = [
        ("Opportunity Scout", "Find work from approved sources and avoid prohibited collection."),
        ("Job Intake Analyst", "Normalize the job into requirements, deliverables, scope, and constraints."),
        ("Research Strategist", "Build domain context, client understanding, and success criteria."),
        ("Best-Practice Synthesist", "Fuse standards from every relevant business and technical discipline."),
        ("Technical Deep-Dive Agent", "Plan implementation, dependencies, testing, and evidence."),
        ("Learning Measures Agent", "Track uncertainty, quality deltas, satisfaction, and feedback loops."),
        ("Business Operator", "Align value proposition, scope, pricing assumptions, and customer communication."),
        ("Compliance and Ethics Officer", "Preserve rules, privacy, transparency, safety, and auditability."),
        ("Execution Coordinator", "Coordinate internal artifacts and handoff readiness."),
    ]
    return [
        {
            "role": role,
            "mission": mission,
            "work_order": title,
            "quality_state": quality_state,
            "governance_required": True,
            "external_action_allowed": False,
        }
        for role, mission in roles
    ]


def ology_review(config: Dict[str, Any], title: str) -> Dict[str, Any]:
    return {
        str(name): {
            "status": "applied",
            "evidence": f"{name} lens applied to business work order: {title}.",
        }
        for name in config.get("business_ologies", [])
    }


def learning_measures(
    authorization: Dict[str, Any],
    work_order: Dict[str, Any],
    blocked: List[str],
) -> Dict[str, Any]:
    quality_state = work_order_quality_state(work_order)
    return {
        "quality_state": quality_state,
        "blocked_reason_count": len(blocked),
        "customer_fit_proxy": "inherit_phase21_customer_satisfaction_when_available",
        "uncertainty_reduction_target": "resolve approval, scope, compliance, payment, and artifact-readiness blockers",
        "proof_of_work_target": "produce visible artifact hash, review notes, assumptions, test evidence, and handoff receipt",
        "next_cycle_signal": "record outcome and revise agent prompts, scoring, and work-order procedure",
        "action_id": authorization.get("action_id", ""),
    }


def blocked_reasons(authorization: Dict[str, Any], expired: bool, quality_state: str) -> List[str]:
    reasons: List[str] = []
    decision = str(authorization.get("decision", "pending"))
    phase6 = authorization.get("phase6_status", {}) or {}
    approval = authorization.get("approval", {}) or {}
    artifact = authorization.get("artifact", {}) or {}
    if decision != "approved_for_phase_6":
        reasons.append("Phase 5 decision is not approved_for_phase_6.")
    if expired:
        reasons.append("Authorization is expired.")
    if not approval.get("approved", False):
        reasons.append("Approval object does not record approved=true.")
    if not phase6.get("authorized_for_phase6", False):
        reasons.append("Phase 6 authorization flag is not true.")
    if phase6.get("external_action_performed", False):
        reasons.append("A prior external action is already recorded for this packet.")
    if not artifact.get("artifact_hash"):
        reasons.append("Artifact hash is missing.")
    if "improvement_required" in quality_state:
        reasons.append("Work-order quality state requires improvement before handoff readiness.")
    return unique(reasons)


def status_from(decision: str, expired: bool, blocked: List[str]) -> str:
    if expired:
        return "blocked_expired_authorization"
    if decision == "pending":
        return "waiting_for_human_review"
    if decision == "denied":
        return "blocked_denied"
    if decision == "revision_required":
        return "blocked_revision_required"
    if blocked:
        return "blocked_or_needs_revision"
    return "approved_for_handoff_readiness"


def governed_next_action(status: str) -> str:
    if status == "approved_for_handoff_readiness":
        return "Create Phase 6 manual handoff or dry-run receipt; operator remains final actor for outward completion."
    if status == "waiting_for_human_review":
        return "Review the visible packet, then accept, deny, or revise."
    if status == "blocked_expired_authorization":
        return "Regenerate Phase 5 packet before further movement."
    return "Resolve blockers or return to research, drafting, compliance, and quality improvement."


def work_order_quality_state(work_order: Dict[str, Any]) -> str:
    ascended = work_order.get("ascended_output_v2", {}) or {}
    return str(ascended.get("quality_state") or work_order.get("status") or "not_available")


def index_work_orders_by_proposal(work_orders: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}
    for item in work_orders:
        proposal_id = str(item.get("proposal_id") or item.get("work_order_id") or "")
        if proposal_id:
            indexed[proposal_id] = item
    return indexed


def authorization_expired(value: str) -> bool:
    parsed = parse_datetime(value)
    if parsed is None:
        return True
    return datetime.now(timezone.utc) > parsed


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def make_record_id(action_id: str, authorization_id: str) -> str:
    digest = hashlib.sha256(f"{action_id}:{authorization_id}".encode("utf-8")).hexdigest()[:16].upper()
    return f"AIGC-BIZ-{digest}"


def load_json_dict(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_list_if_exists(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return [item for item in payload if isinstance(item, dict)]


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def unique(items: List[str]) -> List[str]:
    seen: set[str] = set()
    output: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AIGC Phase 24 autonomic business pipeline.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "phase24_autonomic_business_pipeline.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pipeline = AutonomicBusinessPipeline(project_root=args.project_root)
    records = pipeline.run_from_config(args.config)
    print(pipeline.signature_update(load_json_dict(args.config), records))
    print(f"Records exported: {args.project_root / 'data' / 'phase24_business_pipeline' / 'aigc_phase24_business_pipeline_records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
