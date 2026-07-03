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
class OmniAgentArchitectureRecord:
    record_id: str
    created_at: str
    phase: str
    status: str
    architecture_domain: str
    architecture_purpose: str
    source_record_counts: Dict[str, int]
    formal_ontology: Dict[str, Any]
    methodology: Dict[str, Any]
    cloud_topology: Dict[str, Any]
    agent_procurement: Dict[str, Any]
    everyday_work_capability_map: Dict[str, Any]
    governance_controls: Dict[str, Any]
    integration_contract: Dict[str, Any]
    gap_analysis: List[str]
    readiness_assessment: Dict[str, Any]
    recommended_actions: List[str]
    blocked_actions: List[str]
    deployment_allowed: bool = False
    live_connectors_allowed: bool = False
    approval_required_before_external_action: bool = True
    external_action_performed: bool = False


class Phase30AuditLedger:
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


class OmniAgentCloudIntelligenceArchitecture:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[OmniAgentArchitectureRecord]:
        config = load_json_dict(config_path)
        input_files = config.get("input_files", {})
        records_by_alias = {
            alias: load_records(resolve_project_path(self.project_root, str(path)))
            for alias, path in input_files.items()
        }
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase30_omni_agent_cloud/aigc_phase30_omni_agent_architecture_records.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase30_signature_update.md"),
        )
        audit_path = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase30_audit.jsonl"),
        )
        records = self.build_records(config, input_files, records_by_alias)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        Phase30AuditLedger(audit_path).record("phase30_omni_agent_architecture_records_exported", {
            "path": str(output_path),
            "records": len(records),
            "records_with_gaps": sum(1 for record in records if record.gap_analysis),
            "deployment_allowed": False,
            "live_connectors_allowed": False,
            "external_action_performed": False,
        })
        return records

    def build_records(
        self,
        config: Dict[str, Any],
        input_files: Dict[str, Any],
        records_by_alias: Dict[str, List[Dict[str, Any]]],
    ) -> List[OmniAgentArchitectureRecord]:
        records: List[OmniAgentArchitectureRecord] = []
        for procurement in config.get("architecture_procurements", []):
            records.append(self._build_record(config, input_files, records_by_alias, procurement))
        return records

    def _build_record(
        self,
        config: Dict[str, Any],
        input_files: Dict[str, Any],
        records_by_alias: Dict[str, List[Dict[str, Any]]],
        procurement: Dict[str, Any],
    ) -> OmniAgentArchitectureRecord:
        domain = str(procurement.get("domain", "unknown_omni_agent_domain"))
        aliases = [str(item) for item in procurement.get("source_aliases", [])]
        selected = {alias: records_by_alias.get(alias, []) for alias in aliases}
        counts = {alias: len(records) for alias, records in selected.items()}
        gaps = build_gap_analysis(domain, counts, selected)
        readiness = build_readiness_assessment(domain, gaps, selected, config)
        status = "internal_omni_agent_architecture_procured" if not gaps else "architecture_procurement_gaps_recorded"
        return OmniAgentArchitectureRecord(
            record_id=make_record_id(domain),
            created_at=utc_now(),
            phase="phase30_omni_agent_cloud_intelligence_architecture_procurement",
            status=status,
            architecture_domain=domain,
            architecture_purpose=str(procurement.get("purpose", "")),
            source_record_counts=counts,
            formal_ontology=build_formal_ontology(config, domain),
            methodology=build_methodology(config, domain),
            cloud_topology=build_cloud_topology(config, domain),
            agent_procurement=build_agent_procurement(config, procurement, selected),
            everyday_work_capability_map=build_everyday_work_capability_map(config, procurement),
            governance_controls=build_governance_controls(config, selected),
            integration_contract=build_integration_contract(config, domain, input_files, aliases),
            gap_analysis=gaps,
            readiness_assessment=readiness,
            recommended_actions=recommended_actions_for(domain, gaps),
            blocked_actions=[str(item) for item in config.get("blocked_actions", [])],
            deployment_allowed=False,
            live_connectors_allowed=False,
            approval_required_before_external_action=True,
            external_action_performed=False,
        )

    def signature_update(self, records: List[OmniAgentArchitectureRecord]) -> str:
        gap_records = sum(1 for record in records if record.gap_analysis)
        average_score = round(
            sum(int(record.readiness_assessment.get("readiness_score", 0)) for record in records) / len(records),
            2,
        ) if records else 0
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 30 - Omni-Agent Cloud Intelligence Architecture Procurement",
            "Operational Identity:",
            "Internal Cloud-Agent Architecture Procurement Layer",
            "Action Performed:",
            "Converted the Omni-Agent Cloud Intelligence prompt/spec block into contract-valid architecture procurement records.",
            "Safety Review:",
            "No cloud deployment performed.",
            "No live connectors enabled.",
            "No credentials used.",
            "No external action performed.",
            "No external parties contacted.",
            f"Architecture Records Created: {len(records)}",
            f"Records With Gaps: {gap_records}",
            f"Average Readiness Score: {average_score}",
            "Approval Required:",
            "Yes, before deployment, live connector activation, external work execution, external messaging, or customer/employer contact.",
        ]).strip() + "\n"


def build_gap_analysis(
    domain: str,
    counts: Dict[str, int],
    selected: Dict[str, List[Dict[str, Any]]],
) -> List[str]:
    gaps: List[str] = []
    for alias, count in counts.items():
        if count == 0:
            gaps.append(f"{domain}: required evidence source {alias} has no records.")
    freshness_records = selected.get("freshness_review_records", [])
    if freshness_records:
        approved = sum(1 for record in freshness_records if record.get("decision") == "approved_for_phase28_regeneration")
        pending = sum(1 for record in freshness_records if record.get("decision") == "pending")
        if pending > 0:
            gaps.append(f"{domain}: {pending} freshness reviews remain pending and cannot authorize regeneration.")
        if approved == 0:
            gaps.append(f"{domain}: no Phase 29 freshness reviews are approved.")
    regeneration_records = selected.get("regeneration_candidate_records", [])
    if regeneration_records:
        allowed = sum(1 for record in regeneration_records if record.get("regeneration_allowed") is True)
        if allowed == 0:
            gaps.append(f"{domain}: no Phase 28 regeneration candidates are currently allowed.")
    productization_records = selected.get("productization_release", [])
    for record in productization_records:
        if record.get("deployment_performed") is True or record.get("public_release_allowed") is True:
            gaps.append(f"{domain}: productization evidence indicates deployment or public release authority; incident review required.")
    for alias, records in selected.items():
        if any(record.get("external_action_performed") is True for record in records):
            gaps.append(f"{domain}: evidence source {alias} indicates external action occurred.")
    return unique(gaps)


def build_readiness_assessment(
    domain: str,
    gaps: List[str],
    selected: Dict[str, List[Dict[str, Any]]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    source_count = sum(len(records) for records in selected.values())
    score = 100 - (len(gaps) * 12)
    if not source_count:
        score -= 20
    if not bool(config.get("deployment_allowed", False)):
        deployment_state = "architecture_blueprint_only_no_deployment"
    else:
        deployment_state = "deployment_flag_present_requires_operator_review"
        score -= 25
    return {
        "readiness_state": "ready_for_internal_architecture_use" if not gaps else "blocked_until_architecture_gaps_reviewed",
        "readiness_score": max(0, min(100, score)),
        "domain": domain,
        "source_evidence_records": source_count,
        "deployment_state": deployment_state,
        "live_connector_state": "blocked" if not bool(config.get("live_connectors_allowed", False)) else "requires_incident_review",
        "external_action_state": "blocked",
        "cloud_readiness_claim": "design_and_contract_readiness_only",
    }


def build_formal_ontology(config: Dict[str, Any], domain: str) -> Dict[str, Any]:
    return {
        "domain": domain,
        "entities": [str(item) for item in config.get("ontology_entities", [])],
        "relationships": [str(item) for item in config.get("ontology_relationships", [])],
        "contract_rule": "All planning and execution must map context to Task, Workflow, Capability, Tool, Goal, Policy, and Artifact before action.",
        "truth_boundary": "Generated architecture language is an internal artifact, not source truth or approval authority.",
    }


def build_methodology(config: Dict[str, Any], domain: str) -> Dict[str, Any]:
    steps = [str(item) for item in config.get("methodology_steps", [])]
    return {
        "domain": domain,
        "steps": steps,
        "execution_rule": "Every step must produce internal evidence before downstream use.",
        "verification_rule": "Contract validation, freshness review, quality review, compliance review, and operator gates control promotion.",
        "reflection_rule": "Reflection creates internal update records only; behavior-changing changes require approval.",
    }


def build_cloud_topology(config: Dict[str, Any], domain: str) -> Dict[str, Any]:
    layers = {}
    for layer in config.get("cloud_topology_layers", []):
        layer_name = str(layer)
        layers[layer_name] = {
            "status": "blueprint_procured",
            "deployment_allowed": False,
            "implementation_boundary": topology_boundary(layer_name),
        }
    return {
        "domain": domain,
        "layers": layers,
        "deployment_allowed": False,
        "live_connectors_allowed": False,
        "cloud_runtime_status": "not_deployed_internal_blueprint_only",
    }


def topology_boundary(layer: str) -> str:
    boundaries = {
        "interface_layer": "May describe APIs, dashboards, and chat surfaces; may not expose a public service.",
        "orchestration_layer": "May route internal phase records; may not run unsupervised external workflows.",
        "agent_runtime_layer": "May define container/serverless contracts; may not launch infrastructure.",
        "knowledge_layer": "May define vector, graph, and ontology stores; may not ingest private data without approval.",
        "tool_integration_layer": "May define connector contracts; live write connectors remain disabled.",
        "governance_layer": "Must enforce policy, audit logs, metrics, approvals, freshness review, and incident response.",
    }
    return boundaries.get(layer, "Internal blueprint only.")


def build_agent_procurement(
    config: Dict[str, Any],
    procurement: Dict[str, Any],
    selected: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    archetypes = [str(item) for item in config.get("agent_archetypes", [])]
    required = [str(item) for item in procurement.get("required_capabilities", [])]
    subagent_count = len(selected.get("subagent_team_plans", []))
    return {
        "archetypes": archetypes,
        "required_capabilities": required,
        "existing_internal_subagent_team_plan_count": subagent_count,
        "agent_action_boundary": "All agents are internal planning, review, routing, and artifact-generation roles until separately authorized.",
        "auto_design_allowed": True,
        "auto_execution_external_allowed": False,
    }


def build_everyday_work_capability_map(
    config: Dict[str, Any],
    procurement: Dict[str, Any],
) -> Dict[str, Any]:
    domains: Dict[str, Any] = {}
    for domain in config.get("everyday_work_domains", []):
        domain_name = str(domain)
        domains[domain_name] = {
            "status": "mapped_for_internal_workflow_design",
            "required_capabilities": [str(item) for item in procurement.get("required_capabilities", [])],
            "external_execution_allowed": False,
            "promotion_gate": "Phase 5 approval, compliance review, and applicable freshness review required before external action.",
        }
    return {
        "domains": domains,
        "work_decomposition_rule": "Every everyday work request must decompose into Task, Workflow, Capability, Tool, Goal, Policy, and Artifact.",
    }


def build_governance_controls(
    config: Dict[str, Any],
    selected: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    return {
        "constitution_subordination": True,
        "contract_validation_required": True,
        "phase5_approval_required_before_external_action": True,
        "phase29_freshness_review_required_before_regeneration": True,
        "emergency_stop_respected": True,
        "deployment_allowed": bool(config.get("deployment_allowed", False)),
        "live_connectors_allowed": bool(config.get("live_connectors_allowed", False)),
        "compliance_evidence_records": len(selected.get("compliance_reviews", [])),
        "incident_evidence_records": len(selected.get("incident_summary", [])),
        "truth_first_evidence_records": len(selected.get("truth_first_procurement_records", [])),
    }


def build_integration_contract(
    config: Dict[str, Any],
    domain: str,
    input_files: Dict[str, Any],
    aliases: List[str],
) -> Dict[str, Any]:
    return {
        "identity": "Omni-Agent Cloud Intelligence",
        "mythos": "RegenExcalibur OS",
        "domain": domain,
        "integration_status": "internal_architecture_specification_only",
        "source_paths": {alias: str(input_files.get(alias, "")) for alias in aliases},
        "subordinate_to": [
            "AGENTS.md",
            "OMEGA_X_CONSTITUTION.md",
            "AIGC_MASTER_PROMPT.md",
            "contract_validator",
            "phase5_human_approval_gate",
            "phase29_operator_freshness_review_procurement",
            "emergency_stop",
        ],
        "forbidden_override": [str(item) for item in config.get("blocked_actions", [])],
    }


def recommended_actions_for(domain: str, gaps: List[str]) -> List[str]:
    if not gaps:
        return [f"Use {domain} as an internal architecture procurement record for future design work."]
    actions = [f"Resolve recorded gaps before treating {domain} as implementation-ready."]
    if any("freshness reviews remain pending" in gap or "no Phase 29" in gap for gap in gaps):
        actions.append("Review Phase 29 freshness packets before allowing Phase 28 regeneration.")
    if any("regeneration candidates" in gap for gap in gaps):
        actions.append("Rerun Phase 28 after at least one exact-phrase-approved Phase 29 review exists.")
    if any("no records" in gap for gap in gaps):
        actions.append("Regenerate missing evidence sources before productizing this architecture layer.")
    return unique(actions)


def load_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        records: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    records.append(payload)
        return records
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def make_record_id(domain: str) -> str:
    seed = f"{domain}|phase30"
    return "AIGC-OMNI-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


def load_json_dict(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
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
    parser = argparse.ArgumentParser(description="Run AIGC Phase 30 Omni-Agent Cloud Intelligence architecture procurement.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase30_omni_agent_cloud_intelligence.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = OmniAgentCloudIntelligenceArchitecture(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nOmni-agent architecture records exported: {args.project_root / 'data' / 'phase30_omni_agent_cloud' / 'aigc_phase30_omni_agent_architecture_records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
