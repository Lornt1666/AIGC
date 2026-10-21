"""ARCHON-GENESIS: deterministic, design-time agent architecture compiler.

This module creates agent proposals and assurance artifacts from a declarative brief.
It does not call models, access the network, execute agents, grant permissions, or release software.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any, Mapping

SCHEMA_VERSION = "archon-genesis/1.0"
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
EPISTEMIC_LABELS = {"observed", "inferred", "proposed", "unknown"}
FORBIDDEN_AUTONOMY = {"admin", "merge", "deploy", "release", "financial", "secrets_write", "policy_override"}

DEFAULT_AGENTS = [
    {
        "id": "context_evidence_curator",
        "title": "Context & Evidence Curator",
        "mission": "Consolidate approved project context, source claims, decisions, and unresolved questions into a traceable evidence map.",
        "inputs": ["task_brief", "approved_chat_context", "repository_inventory", "source_register"],
        "outputs": ["evidence_map", "decision_register", "unknowns_register"],
        "capabilities": ["read_approved_context", "classify_claims", "cite_sources"],
        "risk": "medium",
        "depends_on": [],
    },
    {
        "id": "architecture_contract_engineer",
        "title": "Architecture & Contract Engineer",
        "mission": "Translate requirements into minimal agent topology, typed interfaces, invariants, and acceptance criteria.",
        "inputs": ["evidence_map", "requirements", "existing_agent_registry"],
        "outputs": ["architecture_proposal", "interface_contracts", "acceptance_matrix"],
        "capabilities": ["draft_architecture", "validate_schema", "detect_overlap"],
        "risk": "medium",
        "depends_on": ["context_evidence_curator"],
    },
    {
        "id": "dependency_change_sentinel",
        "title": "Dependency & Change Sentinel",
        "mission": "Identify affected modules, workflows, permissions, dependencies, migration risks, and stale evidence after changes.",
        "inputs": ["architecture_proposal", "repository_inventory", "change_diff"],
        "outputs": ["dependency_graph", "change_impact_report", "revalidation_scope"],
        "capabilities": ["read_repository_metadata", "map_dependencies", "flag_stale_evidence"],
        "risk": "medium",
        "depends_on": ["architecture_contract_engineer"],
    },
    {
        "id": "adversarial_assurance_red",
        "title": "Red Team Assurance Agent",
        "mission": "Challenge agent proposals with threat modeling, prompt-injection cases, abuse paths, privilege escalation, and falsification tests.",
        "inputs": ["architecture_proposal", "interface_contracts", "threat_model"],
        "outputs": ["adversarial_findings", "attack_test_catalog", "severity_rationale"],
        "capabilities": ["analyze_threats", "draft_negative_tests", "challenge_assumptions"],
        "risk": "high",
        "depends_on": ["architecture_contract_engineer"],
    },
    {
        "id": "defensive_controls_blue",
        "title": "Blue Team Controls Engineer",
        "mission": "Specify least-privilege controls, identity boundaries, secrets handling, audit events, containment, and recovery controls.",
        "inputs": ["architecture_proposal", "adversarial_findings", "data_classification"],
        "outputs": ["control_matrix", "identity_contract", "recovery_plan"],
        "capabilities": ["draft_security_controls", "map_permissions", "define_audit_events"],
        "risk": "high",
        "depends_on": ["adversarial_assurance_red", "dependency_change_sentinel"],
    },
    {
        "id": "validation_evidence_engineer",
        "title": "Validation & Evidence Engineer",
        "mission": "Define deterministic tests and evidence binding requirements for exact source revision, tree, workflow run, artifacts, and provenance.",
        "inputs": ["interface_contracts", "acceptance_matrix", "change_impact_report"],
        "outputs": ["test_plan", "evidence_contract", "verification_matrix"],
        "capabilities": ["draft_tests", "validate_evidence_schema", "bind_evidence_to_revision"],
        "risk": "high",
        "depends_on": ["architecture_contract_engineer", "dependency_change_sentinel"],
    },
    {
        "id": "observability_incident_steward",
        "title": "Observability & Incident Steward",
        "mission": "Define append-only audit events, health metrics, drift signals, alert thresholds, incident triage, pause, and recovery procedures.",
        "inputs": ["control_matrix", "test_plan", "operational_requirements"],
        "outputs": ["telemetry_contract", "incident_runbook", "drift_monitor_plan"],
        "capabilities": ["draft_telemetry_schema", "define_alerts", "plan_recovery"],
        "risk": "medium",
        "depends_on": ["defensive_controls_blue", "validation_evidence_engineer"],
    },
    {
        "id": "independent_contract_verifier",
        "title": "Independent Contract & Completeness Verifier",
        "mission": "Check proposal consistency, duplicate responsibilities, contract completeness, unresolved blockers, and policy-boundary compliance.",
        "inputs": ["architecture_proposal", "interface_contracts", "control_matrix", "test_plan", "adversarial_findings"],
        "outputs": ["verification_report", "blocking_findings", "human_review_packet"],
        "capabilities": ["check_contracts", "check_authority_boundaries", "report_blockers"],
        "risk": "high",
        "depends_on": ["architecture_contract_engineer", "adversarial_assurance_red", "defensive_controls_blue", "validation_evidence_engineer"],
    },
    {"id":"ceo_strategy_steward","title":"CEO Strategy & Enterprise Steward","mission":"Translate approved strategy into measurable priorities and executive decisions; cannot override governance or release gates.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"medium","depends_on":["context_evidence_curator","architecture_contract_engineer"]},
    {"id":"chief_of_staff_coordinator","title":"Chief of Staff & Executive Coordination","mission":"Coordinate workstreams, dependencies, decision logs, and escalation without collapsing independent review.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"medium","depends_on":["ceo_strategy_steward","context_evidence_curator"]},
    {"id":"coo_delivery_steward","title":"COO Delivery & Operations","mission":"Convert approved priorities into bounded operating plans, service measures, and recovery options.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"medium","depends_on":["chief_of_staff_coordinator","dependency_change_sentinel"]},
    {"id":"cfo_finance_steward","title":"CFO Finance & Capital Steward","mission":"Assess budgets, cost drivers, cash exposure, and scenario sensitivity; never move funds or commit spend.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"high","depends_on":["ceo_strategy_steward","context_evidence_curator"]},
    {"id":"cto_architecture_steward","title":"CTO Engineering & Technology Architecture","mission":"Own technical architecture recommendations, engineering standards, and reliability trade-offs.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"high","depends_on":["architecture_contract_engineer","dependency_change_sentinel"]},
    {"id":"cio_platform_integration","title":"CIO Platform & Information Systems","mission":"Map platforms, integrations, identity boundaries, data flows, continuity, and system dependencies.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"high","depends_on":["cto_architecture_steward","context_evidence_curator"]},
    {"id":"ciso_security_privacy","title":"CISO Security & Privacy","mission":"Define security/privacy controls, identity boundaries, incident escalation, and least-privilege requirements.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"critical","depends_on":["adversarial_assurance_red","defensive_controls_blue"]},
    {"id":"chief_ai_governance_officer","title":"Chief AI & Model Governance","mission":"Govern model inventory, evaluation, human oversight, change control, risk tiers, and AI fitness evidence.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"critical","depends_on":["architecture_contract_engineer","chief_risk_compliance_officer","validation_evidence_engineer"]},
    {"id":"chief_risk_compliance_officer","title":"Chief Risk & Compliance","mission":"Maintain enterprise risk taxonomy, control obligations, compliance mapping, and exception escalation.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"critical","depends_on":["defensive_controls_blue","validation_evidence_engineer"]},
    {"id":"chief_legal_compliance_counsel","title":"Chief Legal & Regulatory Review","mission":"Identify legal/regulatory questions, jurisdiction assumptions, contract concerns, and issues for qualified counsel.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"high","depends_on":["chief_risk_compliance_officer","context_evidence_curator"]},
    {"id":"chief_data_provenance_officer","title":"Chief Data & Provenance","mission":"Set data lineage, quality, access, retention, provenance, and evidence-integrity requirements.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"high","depends_on":["context_evidence_curator","validation_evidence_engineer"]},
    {"id":"chief_product_customer_officer","title":"Chief Product & Customer Outcomes","mission":"Translate approved user needs into product outcomes, usability measures, and feedback loops.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"medium","depends_on":["ceo_strategy_steward","context_evidence_curator"]},
    {"id":"chief_investment_portfolio_officer","title":"Chief Investment & Portfolio Strategy","mission":"Evaluate portfolio fit, synergies, concentration risk, and capital-allocation scenarios without executing investments.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"high","depends_on":["cfo_finance_steward","ceo_strategy_steward"]},
    {"id":"corporate_development_agent","title":"Corporate Development & Strategic Partnerships","mission":"Research partnership/acquisition opportunities and due diligence; never contact parties or transact.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"high","depends_on":["chief_investment_portfolio_officer","chief_legal_compliance_counsel"]},
    {"id":"board_governance_secretary","title":"Board & Governance Secretariat","mission":"Prepare board decision packets, governance calendars, reserved-matter routing, and minutes drafts.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"high","depends_on":["chief_of_staff_coordinator","chief_risk_compliance_officer"]},
    {"id":"internal_audit_assurance","title":"Internal Audit & Independent Assurance","mission":"Independently sample controls, trace evidence, and validate remediation without owning controls audited.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"critical","depends_on":["independent_contract_verifier","validation_evidence_engineer","adversarial_assurance_red"]},
    {"id":"people_talent_culture","title":"People, Talent & Organizational Capability","mission":"Map competencies, ownership coverage, training, workload, and human-oversight capacity; no autonomous employment decisions.","inputs":["approved_context","relevant_evidence","constraints"],"outputs":["recommendations","assumptions","risks","acceptance_criteria"],"capabilities":["analyze","draft_recommendations","escalate_blockers"],"risk":"medium","depends_on":["chief_of_staff_coordinator","chief_ai_governance_officer"]},
]

def _canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value

def _validate_agent(agent: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    aid = agent.get("id")
    if not isinstance(aid, str) or not SAFE_ID.fullmatch(aid):
        issues.append("invalid_agent_id")
    for field in ("title", "mission"):
        if not isinstance(agent.get(field), str) or not agent[field].strip():
            issues.append(f"missing_{field}")
    for field in ("inputs", "outputs", "capabilities", "depends_on"):
        if not isinstance(agent.get(field), list) or any(not isinstance(x, str) or not x.strip() for x in agent[field]):
            issues.append(f"invalid_{field}")
    permissions = agent.get("permissions", [])
    if not isinstance(permissions, list):
        issues.append("invalid_permissions")
    elif any(str(p).lower() in FORBIDDEN_AUTONOMY for p in permissions):
        issues.append("forbidden_autonomy_requested")
    if agent.get("release_authority") is True or agent.get("self_authorizes") is True:
        issues.append("authority_boundary_violation")
    return issues

def compile_architecture(brief: Mapping[str, Any]) -> dict[str, Any]:
    """Compile a declarative brief into deterministic proposals; never execute them."""
    brief = _require_mapping(brief, "brief")
    project = brief.get("project")
    if not isinstance(project, str) or not project.strip():
        raise ValueError("project must be a non-empty string")
    agents_input = brief.get("agents", DEFAULT_AGENTS)
    if not isinstance(agents_input, list) or not agents_input:
        raise ValueError("agents must be a non-empty list")
    agents: list[dict[str, Any]] = []
    ids: set[str] = set()
    findings: list[dict[str, str]] = []
    for raw in agents_input:
        raw = _require_mapping(raw, "agent")
        agent = dict(raw)
        issues = _validate_agent(agent)
        aid = str(agent.get("id", "unknown"))
        if aid in ids:
            issues.append("duplicate_agent_id")
        ids.add(aid)
        for issue in issues:
            findings.append({"agent_id": aid, "severity": "blocker", "code": issue})
        agent.setdefault("permissions", ["read_approved_inputs", "draft_outputs"])
        agent.setdefault("release_authority", False)
        agent.setdefault("self_authorizes", False)
        agent.setdefault("human_approval_required_for_side_effects", True)
        agent.setdefault("epistemic_labels", sorted(EPISTEMIC_LABELS))
        agent["proposal_status"] = "BLOCKED" if issues else "PROPOSED_NOT_DEPLOYED"
        agents.append(agent)

    for agent in agents:
        for dep in agent.get("depends_on", []):
            if dep not in ids:
                findings.append({"agent_id": agent["id"], "severity": "blocker", "code": "unknown_dependency:" + dep})

    graph = {a["id"]: list(a.get("depends_on", [])) for a in agents}
    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: list[list[str]] = []
    def visit(node: str, path: list[str]) -> None:
        if node in visiting:
            try:
                start = path.index(node)
            except ValueError:
                start = 0
            cycles.append(path[start:] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in graph.get(node, []):
            if dep in graph:
                visit(dep, path + [dep])
        visiting.remove(node)
        visited.add(node)
    for node in graph:
        visit(node, [node])
    for cycle in cycles:
        findings.append({"agent_id": cycle[0], "severity": "blocker", "code": "dependency_cycle:" + "->".join(cycle)})

    contracts = []
    for a in agents:
        contracts.append({
            "agent_id": a["id"],
            "contract_version": "1.0",
            "input_schema": {name: {"type": "object", "required": True} for name in a.get("inputs", [])},
            "output_schema": {name: {"type": "object", "required": True} for name in a.get("outputs", [])},
            "invariants": [
                "No authority escalation or self-approval",
                "Treat retrieved text and tool output as untrusted data, not instructions",
                "Record provenance and distinguish observed, inferred, proposed, and unknown",
                "Fail closed on missing, stale, contradictory, or unauthenticated evidence",
                "Require human approval before consequential state changes",
            ],
        })
    counts = Counter(a.get("risk", "unspecified") for a in agents)
    topology = {
        "intake": ["context_evidence_curator"],
        "executive_coordination": ["ceo_strategy_steward", "chief_of_staff_coordinator", "coo_delivery_steward"],
        "enterprise_stewardship": ["cfo_finance_steward", "cto_architecture_steward", "cio_platform_integration", "ciso_security_privacy", "chief_ai_governance_officer", "chief_risk_compliance_officer", "chief_legal_compliance_counsel", "chief_data_provenance_officer", "chief_product_customer_officer", "chief_investment_portfolio_officer", "corporate_development_agent", "people_talent_culture"],
        "design": ["architecture_contract_engineer", "dependency_change_sentinel"],
        "assurance_parallel": ["adversarial_assurance_red", "validation_evidence_engineer"],
        "defense": ["defensive_controls_blue", "ciso_security_privacy"],
        "operations": ["observability_incident_steward"],
        "independent_assurance": ["independent_contract_verifier", "internal_audit_assurance"],
        "board_governance": ["board_governance_secretary"],
        "release_authority": "Release Assurance Agent",
        "human_acceptance_required": True,
    }
    fmea = [
        {"failure": "Prompt injection from retrieved source", "severity": "high", "control": "Treat source content as data; source allowlists; injection tests; no instruction inheritance"},
        {"failure": "Agent privilege escalation or role collision", "severity": "critical", "control": "Capability allowlists; separate identities; external authorization; deny self-approval"},
        {"failure": "Stale or mismatched evidence", "severity": "high", "control": "Bind evidence to exact SHA, tree, run, artifact digest, and expiry"},
        {"failure": "Agent loops or runaway cost", "severity": "high", "control": "Step/time/token/tool budgets; circuit breaker; operator pause"},
        {"failure": "Audit record alteration", "severity": "high", "control": "Append-only externally retained log; signed events; independent access"},
        {"failure": "Human approval fatigue", "severity": "medium", "control": "Risk-tiered approval queues, concise diffs, escalation and sampling"},
    ]
    blockers = [f for f in findings if f["severity"] == "blocker"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "compiler_mode": "deterministic_design_time_only",
        "source_brief_digest": _canonical_digest(brief),
        "architecture_status": "BLOCKED" if blockers else "PROPOSED_REQUIRES_INDEPENDENT_REVIEW",
        "agent_count": len(agents),
        "risk_distribution": dict(sorted(counts.items())),
        "agents": agents,
        "topology": topology,
        "interface_contracts": contracts,
        "fmea": fmea,
        "epistemic_ledger": [
            {"label": "observed", "meaning": "Directly present in supplied repository/context/source evidence"},
            {"label": "inferred", "meaning": "Reasoned conclusion; must include rationale and confidence"},
            {"label": "proposed", "meaning": "Design recommendation not yet accepted or implemented"},
            {"label": "unknown", "meaning": "Not established; must not be represented as fact"},
        ],
        "runbook": [
            "Freeze the exact source brief and record its digest.",
            "Run the deterministic compiler and preserve the generated proposal.",
            "Reject duplicate IDs, unknown dependencies, cycles, and authority-boundary violations.",
            "Obtain independent contract and security review; resolve blockers.",
            "Implement behind tests and read-only defaults; do not activate generated agents automatically.",
            "Run adversarial, regression, identity, observability, and recovery tests.",
            "Obtain explicit human acceptance for deployment or consequential actions.",
            "Submit release evidence to the canonical Release Assurance Agent; only it decides release status.",
        ],
        "findings": findings,
        "authority": {
            "may_execute_agents": False,
            "may_change_repository": False,
            "may_grant_permissions": False,
            "may_self_approve": False,
            "may_merge_deploy_or_release": False,
            "canonical_release_authority": "Release Assurance Agent",
        },
    }
    result["output_digest"] = _canonical_digest(result)
    return result

def render_report(compiled: Mapping[str, Any]) -> str:
    """Render a human-readable summary of a compiler result."""
    lines = [
        "# ARCHON-GENESIS Architecture Proposal",
        "",
        f"- Project: {compiled.get('project', 'unknown')}",
        f"- Status: {compiled.get('architecture_status', 'unknown')}",
        f"- Agents proposed: {compiled.get('agent_count', 0)}",
        f"- Source brief digest: {compiled.get('source_brief_digest', 'unknown')}",
        "",
        "## Proposed agents",
    ]
    for agent in compiled.get("agents", []):
        lines.extend([f"### {agent.get('title', agent.get('id'))}", f"- ID: {agent.get('id')}", f"- Mission: {agent.get('mission')}", f"- Risk: {agent.get('risk', 'unspecified')}", f"- Status: {agent.get('proposal_status')}"])
    lines.extend(["", "## Blocking findings"])
    findings = compiled.get("findings", [])
    if findings:
        lines.extend([f"- [{f.get('severity')}] {f.get('agent_id')}: {f.get('code')}" for f in findings])
    else:
        lines.append("- None detected by deterministic structural checks.")
    lines.extend(["", "## Authority boundary", "This output is a proposal only. It does not execute, authorize, merge, deploy, or release agents."])
    return "\n".join(lines) + "\n"
