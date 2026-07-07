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

from src.core.algorithmic_capabilities import capabilities_for_role  # noqa: E402


@dataclass
class SubAgentMember:
    agent_id: str
    role: str
    purpose: str
    input_contract: Dict[str, Any]
    output_contract: Dict[str, Any]
    allowed_actions: List[str]
    forbidden_actions: List[str]
    quality_criteria: List[str]
    algorithmic_capabilities: List[Dict[str, Any]]
    handoff_target: str
    approval_required: bool
    external_action_allowed: bool = False


@dataclass
class SubAgentTeamPlan:
    team_id: str
    created_at: str
    phase: str
    status: str
    opportunity_id: str
    proposal_id: str
    dossier_id: str
    title: str
    employer: str
    source_platform: str
    source_url: str
    readiness_decision: str
    taxonomy: List[str]
    team_members: List[SubAgentMember]
    handoff_sequence: List[str]
    required_approval_gates: List[str]
    forbidden_team_behaviors: List[str]
    quality_bar: List[str]
    approval_required_before_external_action: bool = True
    external_action_performed: bool = False


class Phase19AuditLedger:
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


class SubAgentForge:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[SubAgentTeamPlan]:
        config = load_json_dict(config_path)
        inputs = config.get("input_files", {})
        assessments = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("assessments", "")))
        proposals = load_json_list_if_exists(resolve_project_path(self.project_root, inputs.get("proposals", "")))
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase19_subagents/aigc_phase19_subagent_team_plans.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase19_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase19_audit.jsonl"),
        )
        plans = self.build_plans(config, assessments, proposals)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([plan_to_dict(plan) for plan in plans], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        Phase19AuditLedger(audit_path).record("phase19_subagent_team_plans_exported", {
            "path": str(output_path),
            "plans": len(plans),
            "external_action_performed": False,
        })
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(plans), encoding="utf-8")
        return plans

    def build_plans(
        self,
        config: Dict[str, Any],
        assessments: List[Dict[str, Any]],
        proposals: List[Dict[str, Any]],
    ) -> List[SubAgentTeamPlan]:
        eligible = set(str(item) for item in config.get("eligible_readiness_decisions", []))
        max_plans = int(config.get("max_team_plans", 25))
        assessments_by_id = {str(item.get("opportunity_id", "")): item for item in assessments}
        plans: List[SubAgentTeamPlan] = []
        for proposal in proposals:
            if eligible and str(proposal.get("readiness_decision", "")) not in eligible:
                continue
            opportunity_id = str(proposal.get("opportunity_id", ""))
            assessment = assessments_by_id.get(opportunity_id, {})
            plans.append(self._build_plan(config, proposal, assessment))
            if len(plans) >= max_plans:
                break
        return plans

    def _build_plan(
        self,
        config: Dict[str, Any],
        proposal: Dict[str, Any],
        assessment: Dict[str, Any],
    ) -> SubAgentTeamPlan:
        proposal_id = str(proposal.get("proposal_id", ""))
        opportunity_id = str(proposal.get("opportunity_id", ""))
        title = str(proposal.get("title") or assessment.get("title") or "")
        employer = str(proposal.get("employer") or assessment.get("employer") or "")
        taxonomy = [str(item) for item in assessment.get("discovered_taxonomy", [])]
        team_id = make_team_id(proposal_id, opportunity_id, title)
        role_templates = config.get("default_role_templates", [])
        members = [
            self._build_member(
                team_id=team_id,
                template=template,
                taxonomy=taxonomy,
                allowed_actions=[str(item) for item in config.get("allowed_internal_actions", [])],
                forbidden_actions=[str(item) for item in config.get("forbidden_team_behaviors", [])],
                quality_bar=[str(item) for item in config.get("quality_bar", [])],
            )
            for template in role_templates
            if isinstance(template, dict)
        ]
        return SubAgentTeamPlan(
            team_id=team_id,
            created_at=utc_now(),
            phase="phase19_subagent_generation_forge",
            status="internal_plan_only",
            opportunity_id=opportunity_id,
            proposal_id=proposal_id,
            dossier_id=str(proposal.get("dossier_id") or assessment.get("dossier_id") or ""),
            title=title,
            employer=employer,
            source_platform=str(proposal.get("source_platform") or assessment.get("source_platform") or ""),
            source_url=str(proposal.get("source_url") or assessment.get("source_url") or ""),
            readiness_decision=str(proposal.get("readiness_decision", "")),
            taxonomy=taxonomy,
            team_members=members,
            handoff_sequence=[member.role for member in members],
            required_approval_gates=[str(item) for item in config.get("required_approval_gates", [])],
            forbidden_team_behaviors=[str(item) for item in config.get("forbidden_team_behaviors", [])],
            quality_bar=[str(item) for item in config.get("quality_bar", [])],
            approval_required_before_external_action=True,
            external_action_performed=False,
        )

    def _build_member(
        self,
        team_id: str,
        template: Dict[str, Any],
        taxonomy: List[str],
        allowed_actions: List[str],
        forbidden_actions: List[str],
        quality_bar: List[str],
    ) -> SubAgentMember:
        role = str(template.get("role", "Sub-Agent"))
        output_artifact = str(template.get("output_artifact", "internal_notes"))
        return SubAgentMember(
            agent_id=make_agent_id(team_id, role),
            role=role,
            purpose=str(template.get("purpose", "")),
            input_contract={
                "sources": ["phase3_assessment_dossier", "phase4_proposal_package"],
                "required_fields": ["opportunity_id", "proposal_id", "title", "employer", "source_url"],
                "taxonomy_context": taxonomy,
            },
            output_contract={
                "artifact_type": output_artifact,
                "format": "json_or_markdown_internal_note",
                "schema_required_before_downstream_use": True,
            },
            allowed_actions=allowed_actions,
            forbidden_actions=forbidden_actions,
            quality_criteria=quality_bar,
            algorithmic_capabilities=capabilities_for_role(role, taxonomy),
            handoff_target=str(template.get("handoff_target", "")),
            approval_required=True,
            external_action_allowed=False,
        )

    def signature_update(self, plans: List[SubAgentTeamPlan]) -> str:
        member_count = sum(len(plan.team_members) for plan in plans)
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 19 - Sub-Agent Generation Forge",
            "Operational Identity:",
            "Internal Specialist Team Planning Layer",
            "Action Performed:",
            "Generated governed internal sub-agent team plans from proposal and assessment artifacts.",
            "Safety Review:",
            "No external action performed.",
            "No sub-agent may contact employers, submit work, use credentials, or bypass approval gates.",
            "All generated sub-agents are internal planning roles only.",
            f"Team Plans Created: {len(plans)}",
            f"Sub-Agent Role Records Created: {member_count}",
            "Approval Required:",
            "Yes, before any generated sub-agent output can become an external action.",
        ]).strip() + "\n"


def make_team_id(proposal_id: str, opportunity_id: str, title: str) -> str:
    seed = f"{proposal_id}|{opportunity_id}|{title}|phase19"
    return "AIGC-TEAM-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def make_agent_id(team_id: str, role: str) -> str:
    seed = f"{team_id}|{role}"
    return "AIGC-SUB-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()


def plan_to_dict(plan: SubAgentTeamPlan) -> Dict[str, Any]:
    payload = asdict(plan)
    payload["team_members"] = [asdict(member) for member in plan.team_members]
    return payload


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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 19 sub-agent generation forge.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase19_subagent_forge.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = SubAgentForge(project_root=args.project_root)
    plans = phase.run_from_config(args.config)
    print(phase.signature_update(plans))
    print(f"\nSub-agent team plans exported: {args.project_root / 'data' / 'phase19_subagents' / 'aigc_phase19_subagent_team_plans.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
