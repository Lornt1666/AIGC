from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List


FORBIDDEN_USES = [
    "hidden_human_impersonation",
    "credential_abuse",
    "platform_rule_bypass",
    "automatic_contract_acceptance",
    "automatic_payment_request",
    "unchecked_outward_action",
    "secret_exfiltration",
]

METHODOLOGY_LENSES = [
    "ontology",
    "epistemology",
    "methodology",
    "praxeology",
    "axiology",
    "teleology",
    "semiotics",
    "cybernetics",
    "systems_theory",
    "ethics",
    "legal_review",
    "security_review",
    "operations",
    "customer_success",
    "risk_theory",
    "quality_engineering",
]


@dataclass(frozen=True)
class AlgorithmicCapability:
    capability_id: str
    name: str
    applies_to: List[str]
    algorithm_family: str
    methodology_lenses: List[str]
    ontology_targets: List[str]
    input_contracts: List[str]
    output_contracts: List[str]
    allowed_uses: List[str]
    forbidden_uses: List[str]
    risk_controls: List[str]
    tests_required: List[str]
    requires_human_review: bool = True
    external_action_allowed: bool = False


def build_algorithmic_capability_manifest() -> Dict[str, Any]:
    capabilities = [asdict(item) for item in default_capabilities()]
    return {
        "manifest_id": "AIGC-ALGO-CAPABILITY-FABRIC-v1",
        "status": "internal_governed_capability_registry",
        "capability_count": len(capabilities),
        "methodology_lenses": METHODOLOGY_LENSES,
        "capabilities": capabilities,
        "forbidden_uses": FORBIDDEN_USES,
        "approval_boundary": {
            "human_review_required_before_external_action": True,
            "self_approval_allowed": False,
            "external_action_default": False,
        },
        "external_action_performed": False,
    }


def default_capabilities() -> List[AlgorithmicCapability]:
    return [
        AlgorithmicCapability(
            capability_id="cap_opportunity_ranking",
            name="Opportunity ranking and fit scoring",
            applies_to=["phase2", "Opportunity Scout", "Business Strategist"],
            algorithm_family="weighted_multi_criteria_scoring",
            methodology_lenses=["ontology", "axiology", "systems_theory", "risk_theory"],
            ontology_targets=["opportunity", "source", "buyer_fit", "risk"],
            input_contracts=["opportunity_record", "source_trace"],
            output_contracts=["ranked_opportunity_queue", "risk_flags"],
            allowed_uses=["rank_read_only_sources", "surface_uncertainty", "prepare_reviewable_queue"],
            forbidden_uses=FORBIDDEN_USES,
            risk_controls=["source_allowlist", "no_application_submission", "no_credentials", "audit_source_trace"],
            tests_required=["stage_order", "schema_validation", "no_external_action"],
        ),
        AlgorithmicCapability(
            capability_id="cap_job_ingestion_normalization",
            name="Job ingestion and contract normalization",
            applies_to=["phase3", "Job Intake Analyst"],
            algorithm_family="schema_first_information_extraction",
            methodology_lenses=["ontology", "epistemology", "semiotics", "legal_review"],
            ontology_targets=["job_requirements", "deliverables", "constraints", "evidence"],
            input_contracts=["opportunity_record"],
            output_contracts=["assessment_dossier"],
            allowed_uses=["normalize_public_job_data", "extract_requirements", "flag_missing_facts"],
            forbidden_uses=FORBIDDEN_USES,
            risk_controls=["source_trace_required", "uncertainty_disclosure", "no_identity_claims"],
            tests_required=["schema_validation", "redaction", "uncertainty_present"],
        ),
        AlgorithmicCapability(
            capability_id="cap_best_practice_synthesis",
            name="Best-practice synthesis",
            applies_to=["phase3", "phase4", "Best-Practice Synthesist", "Domain Researcher"],
            algorithm_family="evidence_weighted_synthesis",
            methodology_lenses=["epistemology", "methodology", "ethics", "customer_success"],
            ontology_targets=["best_practice", "evidence", "quality_bar", "assumptions"],
            input_contracts=["assessment_dossier", "proposal_package"],
            output_contracts=["best_practice_dossier", "review_packet_notes"],
            allowed_uses=["summarize_sources", "compare_methods", "record_assumptions"],
            forbidden_uses=FORBIDDEN_USES,
            risk_controls=["citation_required", "no_copying_unlicensed_code", "human_review_before_reuse"],
            tests_required=["source_traceability", "forbidden_capability_blocking"],
        ),
        AlgorithmicCapability(
            capability_id="cap_deep_work_decomposition",
            name="Deep work decomposition",
            applies_to=["phase19", "phase23", "Technical Deep-Dive Agent", "Implementation Planner"],
            algorithm_family="task_graph_decomposition",
            methodology_lenses=["methodology", "praxeology", "systems_theory", "operations"],
            ontology_targets=["task", "dependency", "acceptance_test", "failure_mode"],
            input_contracts=["proposal_package", "work_order_governance_record"],
            output_contracts=["work_decomposition_plan", "agent_plan"],
            allowed_uses=["decompose_internal_work", "map_dependencies", "define_acceptance_tests"],
            forbidden_uses=FORBIDDEN_USES,
            risk_controls=["approval_gate_before_handoff", "artifact_hash_locking", "blocked_action_list"],
            tests_required=["dependency_integrity", "artifact_hash_mismatch_blocking"],
        ),
        AlgorithmicCapability(
            capability_id="cap_learning_measures",
            name="Learning measures and outcome feedback",
            applies_to=["phase8", "phase21", "phase24", "Learning Measures Agent", "Evolution Architect"],
            algorithm_family="feedback_loop_metrics",
            methodology_lenses=["cybernetics", "customer_success", "axiology", "teleology"],
            ontology_targets=["quality_delta", "customer_fit", "outcome", "evolution_patch"],
            input_contracts=["customer_satisfaction_record", "outcome_record", "autonomic_business_pipeline_record"],
            output_contracts=["learning_measures_record", "evolution_patch"],
            allowed_uses=["measure_quality_delta", "propose_internal_improvements", "track_outcomes"],
            forbidden_uses=FORBIDDEN_USES,
            risk_controls=["patch_review_required", "no_self_modifying_release", "audit_event_required"],
            tests_required=["evolution_patch_requires_review", "audit_log_creation"],
        ),
        AlgorithmicCapability(
            capability_id="cap_agent_team_design",
            name="Governed agent-team design",
            applies_to=["phase19", "phase24", "Execution Coordinator", "Audit Archivist"],
            algorithm_family="role_assignment_and_handoff_graph",
            methodology_lenses=["systems_theory", "operations", "ethics", "security_review"],
            ontology_targets=["agent", "role", "handoff", "tool_permission"],
            input_contracts=["assessment_dossier", "proposal_package", "authorization_packet"],
            output_contracts=["subagent_team_plan", "autonomic_business_pipeline_record"],
            allowed_uses=["assign_internal_roles", "define_handoffs", "bind_tool_limits"],
            forbidden_uses=FORBIDDEN_USES,
            risk_controls=["tool_permission_manifest", "external_action_default_false", "no_self_approval"],
            tests_required=["agent_external_action_false", "approval_gate_required"],
        ),
        AlgorithmicCapability(
            capability_id="cap_policy_risk_gate",
            name="Policy and risk gate",
            applies_to=["phase5", "phase16", "Compliance and Ethics Agent", "Security Agent", "Finance and Contract Review Agent"],
            algorithm_family="deterministic_policy_rule_engine",
            methodology_lenses=["ethics", "legal_review", "security_review", "risk_theory"],
            ontology_targets=["approval", "contract", "payment", "credential", "external_action"],
            input_contracts=["authorization_packet", "compliance_review", "finance_ledger_record"],
            output_contracts=["approval_decision", "blocked_actions", "audit_event"],
            allowed_uses=["block_expired_approval", "block_unapproved_outward_action", "flag_payment_or_contract_risk"],
            forbidden_uses=FORBIDDEN_USES,
            risk_controls=["exact_phrase_approval", "expiry_check", "emergency_stop", "redaction_scan"],
            tests_required=["expired_approval_blocking", "no_outward_action_without_approval", "redaction"],
        ),
        AlgorithmicCapability(
            capability_id="cap_uncertainty_quality_kernel",
            name="Uncertainty-aware quality kernel",
            applies_to=["phase22", "QA and Test Agent", "Technical Deep-Dive Agent"],
            algorithm_family="deterministic_uncertainty_weighted_quality_state",
            methodology_lenses=["epistemology", "ontology", "cybernetics", "quality_engineering"],
            ontology_targets=["quality_state", "uncertainty", "test_evidence", "risk_flags"],
            input_contracts=["fidelity_review", "customer_satisfaction_record", "compliance_review"],
            output_contracts=["quality_kernel_record", "improvement_directives"],
            allowed_uses=["score_quality", "surface_uncertainty", "require_repair_before_handoff"],
            forbidden_uses=FORBIDDEN_USES,
            risk_controls=["literal_quantum_claim_false", "human_review_required", "test_evidence_required"],
            tests_required=["quality_state_contract", "literal_quantum_claim_blocked"],
        ),
    ]


def capabilities_for_role(role: str, taxonomy: List[str] | None = None) -> List[Dict[str, Any]]:
    role_value = role.lower()
    taxonomy_value = " ".join(taxonomy or []).lower()
    matches: List[AlgorithmicCapability] = []
    for capability in default_capabilities():
        applies = " ".join(capability.applies_to).lower()
        if role_value in applies or any(token in applies for token in role_value.split()):
            matches.append(capability)
        elif "documentation" in taxonomy_value and capability.capability_id in {
            "cap_best_practice_synthesis",
            "cap_deep_work_decomposition",
        }:
            matches.append(capability)
    if not matches:
        matches = [capability_by_id("cap_policy_risk_gate")]
    return [capability_summary(item) for item in unique_capabilities(matches)]


def capability_by_id(capability_id: str) -> AlgorithmicCapability:
    for capability in default_capabilities():
        if capability.capability_id == capability_id:
            return capability
    raise KeyError(f"Unknown algorithmic capability: {capability_id}")


def capability_summary(capability: AlgorithmicCapability) -> Dict[str, Any]:
    return {
        "capability_id": capability.capability_id,
        "name": capability.name,
        "algorithm_family": capability.algorithm_family,
        "methodology_lenses": capability.methodology_lenses,
        "allowed_uses": capability.allowed_uses,
        "forbidden_uses": capability.forbidden_uses,
        "risk_controls": capability.risk_controls,
        "requires_human_review": capability.requires_human_review,
        "external_action_allowed": capability.external_action_allowed,
    }


def assert_algorithmic_manifest_safe(manifest: Dict[str, Any]) -> Dict[str, Any]:
    capabilities = manifest.get("capabilities", [])
    if not capabilities:
        raise ValueError("Algorithmic capability manifest must include capabilities.")
    for capability in capabilities:
        if capability.get("external_action_allowed") is not False:
            raise ValueError(f"{capability.get('capability_id')} must not allow external action by default.")
        if capability.get("requires_human_review") is not True:
            raise ValueError(f"{capability.get('capability_id')} must require human review.")
        forbidden = set(capability.get("forbidden_uses", []))
        missing = set(FORBIDDEN_USES) - forbidden
        if missing:
            raise ValueError(f"{capability.get('capability_id')} missing forbidden uses: {sorted(missing)}")
    boundary = manifest.get("approval_boundary", {})
    if boundary.get("self_approval_allowed") is not False:
        raise ValueError("Self-approval must be disabled.")
    if manifest.get("external_action_performed") is not False:
        raise ValueError("Capability manifest cannot record an external action.")
    return manifest


def unique_capabilities(capabilities: List[AlgorithmicCapability]) -> List[AlgorithmicCapability]:
    seen: set[str] = set()
    output: List[AlgorithmicCapability] = []
    for capability in capabilities:
        if capability.capability_id not in seen:
            seen.add(capability.capability_id)
            output.append(capability)
    return output
