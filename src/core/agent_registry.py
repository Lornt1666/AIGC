from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class AgentDefinition:
    agent_id: str
    display_name: str
    purpose: str
    kind: str
    phase: Optional[str]
    workflow_path: Optional[str]
    autonomy: str
    external_actions: bool = False
    approval_required: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# Runtime agents are deliberately adapters over existing governed phases. They do
# not gain permissions beyond the phase they invoke.
_PHASE_AGENTS = [
    ("opportunity_radar", "Opportunity Radar Agent", "Discover and normalize configured opportunities.", "phase2", "read_only"),
    ("assessment", "Assessment Agent", "Assess queued opportunities using the existing assessment phase.", "phase3", "internal_only"),
    ("proposal_drafting", "Proposal Drafting Agent", "Prepare internal proposal drafts.", "phase4", "internal_only"),
    ("human_approval_gate", "Human Approval Gate Agent", "Prepare scoped authorization packets; cannot self-approve.", "phase5", "approval_gate"),
    ("controlled_execution", "Controlled Execution Agent", "Process only the existing approved Phase 5 execution path.", "phase6", "manual_handoff_only"),
    ("employer_audit", "Employer Audit Agent", "Prepare internal audit packet drafts.", "phase7", "internal_draft_only"),
    ("evolution", "Evolution Agent", "Record outcomes and propose governed changes.", "phase8", "internal_evolution_only"),
    ("connector_governance", "Connector Governance Agent", "Inspect connector capability configuration without enabling live writes.", "phase10", "read_only_connector_registry"),
    ("secrets_vault", "Secrets Vault Agent", "Validate secret references and run the configured fake-secret check.", "phase11", "internal_security_check"),
    ("observability", "Observability Agent", "Refresh internal runtime observability.", "phase12", "internal_observability"),
    ("simulation", "Simulation Agent", "Run synthetic simulation or configured read-only replay.", "phase13", "synthetic_or_read_only"),
    ("runtime_preflight", "Runtime Preflight Agent", "Run Phase 14 readiness checks; never authorizes external actions.", "phase14", "internal_preflight"),
    ("finance_contracts", "Finance and Contracts Agent", "Prepare internal finance and contract records.", "phase15", "internal_only"),
    ("compliance_review", "Compliance Review Agent", "Prepare internal compliance reviews.", "phase16", "internal_only"),
    ("incident_response", "Incident Response Agent", "Create and track internal incident response artifacts.", "phase17", "internal_only"),
    ("productization", "Productization Agent", "Evaluate internal release-readiness artifacts.", "phase18", "internal_only"),
    ("subagent_forge", "Sub-Agent Forge", "Generate internal sub-agent team plans, not autonomous permissions.", "phase19", "planning_only"),
    ("fidelity_review", "Fidelity Review Agent", "Review quality and fidelity artifacts internally.", "phase20", "internal_only"),
    ("customer_satisfaction", "Customer Satisfaction Agent", "Score internal customer-fit/satisfaction artifacts.", "phase21", "internal_only"),
    ("quality_kernel", "Quality Kernel Agent", "Produce deterministic quality-state modeling artifacts.", "phase22", "internal_only"),
    ("work_order_governor", "Work Order Governance Agent", "Govern work-order state and approval gates.", "phase23", "internal_only"),
    ("business_pipeline", "Business Pipeline Agent", "Prepare internal business pipeline readiness artifacts.", "phase24", "internal_only"),
    ("constellation_fabric", "Constellation Fabric Agent", "Map repository constellation; proposal-only, no file moves.", "phase25", "proposal_only"),
    ("constellation_refactor_planner", "Constellation Refactor Planner", "Prepare refactor plans; does not edit or move files.", "phase26", "proposal_only"),
]

_PROJECT_WORKFLOWS = [
    ("aigc_architecture", "AIGC Architecture Agent", "Map AIGC contracts, task lifecycle, orchestration, evidence, and governance gaps.", "AIGC architecture and governed runtime"),
    ("job_enquiry_application", "Job Enquiry and Application Agent", "Prepare job research and application drafts while preserving consent and human approval.", "Job enquiry and application workflow"),
    ("mobile_gateway", "Mobile Gateway Agent", "Plan mobile-to-cloud request routing, authentication, idempotency, and observability.", "Mobile gateway and execution adapters"),
    ("cloud_orchestration", "Cloud Orchestration Agent", "Compare durable orchestration, queues, workers, MCP, telemetry, and cloud deployment options.", "Clouded Tech Stack and Archi-Engine"),
    ("google_execution_adapter", "Google Execution Adapter Agent", "Plan Google Cloud execution integration without accessing credentials or triggering live operations.", "Google Cloud execution adapter"),
    ("regenexcalibur_envelope", "Regenerative Envelope Research Agent", "Assess façade, BIPV, grid-aware envelope, materials, embodied carbon, and evidence requirements.", "RegenExcalibur regenerative building envelope"),
    ("carbon_capture_mrv", "Carbon Capture MRV Agent", "Define measurement, reporting, verification, baseline, leakage, permanence, and uncertainty requirements.", "Carbon capture and MRV"),
    ("fabrication_safety", "Fabrication Safety Review Agent", "Check design maturity, validation evidence, hazards, tolerances, QA, and human sign-off before fabrication.", "ASTRAFABRION and fabrication safety"),
    ("protocol_governance", "1JGM Protocol Governance Agent", "Map protocol responsibilities, interfaces, ownership, evidence ledger, and authorization boundaries.", "1JGM protocol and orchestration governance"),
    ("security_privacy", "Security and Privacy Agent", "Review identity, least privilege, secrets, redaction, tenant isolation, threat models, and recovery.", "Security and privacy engineering"),
    ("release_assurance", "Release Assurance Agent", "Plan exact-SHA CI, dependency reconciliation, staging evidence, rollback, and release gates.", "Release assurance and production hardening"),
    ("gemini_xprize", "Gemini XPRIZE Integration Agent", "Map competition requirements to product scope, evidence, deliverables, and review gates.", "Gemini XPRIZE and AIGC product integration"),
    ("data_analytics", "Data Analytics Agent", "Define metric grain, data quality checks, drivers, uncertainty, and decision-ready reporting.", "Data analytics and KPI reporting"),
    ("ci_diagnostics", "CI Diagnostics Agent", "Trace workflow failures to exact jobs, steps, logs, SHA, and minimal reproducible causes.", "CI diagnosis and adversarial debugging"),
]

_ENGINEERING_WORKFLOWS = [
    ("root_cause", "Root-Cause Debugging Agent", "Diagnose failures, rank evidence-backed hypotheses, and specify regression proof.", "1. Root-cause analysis / adversarial debugging"),
    ("zero_regression_refactor", "Zero-Regression Refactoring Agent", "Characterize contracts and plan a minimal behavior-preserving refactor.", "2. Zero-regression refactoring and optimization"),
    ("adversarial_testing", "Adversarial Testing Agent", "Design boundary, invariant, property-based, and failure-injection tests.", "3. Adversarial / property-based testing"),
    ("contract_synthesis", "Schema and API Contract Agent", "Plan typed models, runtime validation, compatibility, and round-trip tests.", "4. Schema / API contract synthesis"),
    ("architecture_tradeoff", "Architecture Trade-Off Agent", "Prepare evidence-labeled options, trade-offs, and proof-of-concept criteria.", "5. Architecture trade-off matrix"),
    ("legacy_reverse_engineering", "Legacy Reverse-Engineering Agent", "Map control flow, state, side effects, and safe characterization seams.", "6. Legacy reverse engineering / AST-level breakdown"),
    ("red_team_review", "Senior Red-Team Review Agent", "Review diffs for evidence-backed security, resilience, contract, and test risks.", "7. Senior PR review / red-team audit"),
]


def build_agent_registry() -> Dict[str, AgentDefinition]:
    agents: Dict[str, AgentDefinition] = {}
    for agent_id, display_name, purpose, phase, autonomy in _PHASE_AGENTS:
        agents[agent_id] = AgentDefinition(
            agent_id=agent_id,
            display_name=display_name,
            purpose=purpose,
            kind="phase_adapter",
            phase=phase,
            workflow_path=None,
            autonomy=autonomy,
            external_actions=False,
            approval_required=phase in {"phase5", "phase6", "phase7", "phase8", "phase18"},
        )
    for agent_id, display_name, purpose, workflow_path in _ENGINEERING_WORKFLOWS + _PROJECT_WORKFLOWS:
        agents[agent_id] = AgentDefinition(
            agent_id=agent_id,
            display_name=display_name,
            purpose=purpose,
            kind="workflow_planner",
            phase=None,
            workflow_path=workflow_path,
            autonomy="plan_only_no_model_execution",
            external_actions=False,
            approval_required=False,
        )
    return agents


def get_agent(agent_id: str) -> AgentDefinition:
    registry = build_agent_registry()
    try:
        return registry[agent_id]
    except KeyError as exc:
        raise KeyError(f"Unknown agent {agent_id!r}. Known agents: {', '.join(sorted(registry))}") from exc


def build_workflow_plan(agent: AgentDefinition, task: str) -> dict:
    if agent.kind != "workflow_planner" or not agent.workflow_path:
        raise ValueError(f"Agent {agent.agent_id} is not a workflow planner.")
    clean_task = task.strip()
    if not clean_task:
        raise ValueError("A non-empty task is required.")
    return {
        "agent_id": agent.agent_id,
        "agent_name": agent.display_name,
        "kind": agent.kind,
        "status": "plan_created",
        "task": clean_task,
        "workflow": agent.workflow_path,
        "purpose": agent.purpose,
        "execution_mode": "deterministic_workflow_plan_only",
        "steps": [
            "Inspect the exact repository revision and relevant evidence.",
            "Separate observed facts, deductions, hypotheses, and unknowns.",
            "State scope, contracts, invariants, and authorization boundaries.",
            "Produce the workflow-specific analysis and concrete verification plan.",
            "Review risks adversarially and record unresolved blockers.",
        ],
        "safety_constraints": {
            "external_actions_allowed": False,
            "repository_mutations_allowed": False,
            "secrets_access_allowed": False,
            "human_approval_bypass_allowed": False,
        },
        "limitations": [
            "This registry creates a structured plan; it does not invoke an LLM or claim to have completed the engineering task.",
            "A future model-backed adapter must be explicitly configured, independently permission-checked, and tested before it can execute writes.",
        ],
    }
