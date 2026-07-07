from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


FORBIDDEN_PROCUREMENT_TARGETS = [
    "hidden_human_impersonation",
    "credential_abuse",
    "platform_rule_bypass",
    "automatic_contract_acceptance",
    "automatic_payment_request",
    "unchecked_outward_action",
]


@dataclass(frozen=True)
class PublicResearchSource:
    source_id: str
    title: str
    source_type: str
    url: str
    freshness: str
    credibility_score: int
    applicability_score: int
    safe_borrow: List[str]
    avoid: List[str]


@dataclass(frozen=True)
class ProcuredLayer:
    layer_id: str
    name: str
    status: str
    priority: str
    source_ids: List[str]
    missing_reason: str
    procurement_action: str
    acceptance_tests: List[str]
    risk_controls: List[str]
    forbidden_targets_blocked: List[str]
    human_review_required: bool = True
    external_action_performed: bool = False


def build_public_research_procurement_catalog() -> Dict[str, Any]:
    sources = [asdict(source) for source in public_research_sources()]
    layers = [asdict(layer) for layer in procured_layers()]
    catalog = {
        "catalog_id": "AIGC-PUBLIC-RESEARCH-PROCUREMENT-CATALOG-v1",
        "created_at": utc_now(),
        "status": "researched_public_domain_procurement_plan",
        "research_scope": [
            "official_ai_governance_frameworks",
            "official_secure_development_frameworks",
            "official_agent_runtime_documentation",
            "official_workflow_orchestration_documentation",
            "official_post_quantum_cryptography_standards",
            "software_supply_chain_provenance_standards",
        ],
        "sources": sources,
        "procured_layers": layers,
        "forbidden_procurement_targets": FORBIDDEN_PROCUREMENT_TARGETS,
        "procurement_boundary": {
            "external_services_installed": False,
            "accounts_configured": False,
            "credentials_read": False,
            "live_actions_executed": False,
            "human_review_required_before_implementation": True,
        },
        "external_action_performed": False,
    }
    return validate_public_research_procurement_catalog(catalog)


def public_research_sources() -> List[PublicResearchSource]:
    return [
        PublicResearchSource(
            source_id="src_nist_ai_rmf",
            title="NIST AI Risk Management Framework",
            source_type="official_standard",
            url="https://airc.nist.gov/airmf-resources/airmf/5-sec-core/",
            freshness="current_foundational_ai_risk_framework",
            credibility_score=5,
            applicability_score=5,
            safe_borrow=["govern_map_measure_manage", "trustworthiness_characteristics", "risk_lifecycle"],
            avoid=["treating_framework_as_one_time_checklist"],
        ),
        PublicResearchSource(
            source_id="src_nist_ssdf",
            title="NIST Secure Software Development Framework SP 800-218",
            source_type="official_standard",
            url="https://csrc.nist.gov/pubs/sp/800/218/final",
            freshness="current_secure_development_framework",
            credibility_score=5,
            applicability_score=5,
            safe_borrow=["secure_development_practices", "vulnerability_response", "software_integrity_controls"],
            avoid=["shipping_without_security_requirements_or_review"],
        ),
        PublicResearchSource(
            source_id="src_owasp_llm_top10",
            title="OWASP Top 10 for LLMs and Gen AI Apps 2025",
            source_type="official_security_project",
            url="https://genai.owasp.org/llm-top-10/",
            freshness="2025_genai_risk_baseline",
            credibility_score=5,
            applicability_score=5,
            safe_borrow=["prompt_injection_controls", "sensitive_information_controls", "excessive_agency_controls"],
            avoid=["relying_on_prompt_text_as_the_only_security_boundary"],
        ),
        PublicResearchSource(
            source_id="src_openai_agents_sdk",
            title="OpenAI Agents SDK Documentation",
            source_type="official_product_documentation",
            url="https://developers.openai.com/api/docs/guides/agents",
            freshness="current_agent_runtime_guidance",
            credibility_score=5,
            applicability_score=4,
            safe_borrow=["agent_handoffs", "guardrails", "sessions", "tracing", "resumable_approval_flows"],
            avoid=["tool_execution_without_tool_guardrails"],
        ),
        PublicResearchSource(
            source_id="src_langgraph_interrupts",
            title="LangGraph Interrupts Documentation",
            source_type="official_product_documentation",
            url="https://docs.langchain.com/oss/python/langgraph/interrupts",
            freshness="current_human_in_the_loop_pattern",
            credibility_score=4,
            applicability_score=4,
            safe_borrow=["pause_resume_state", "human_in_the_loop_interrupts", "checkpointed_review"],
            avoid=["resuming_external_action_without_revalidating_permit"],
        ),
        PublicResearchSource(
            source_id="src_temporal_workflow_execution",
            title="Temporal Workflow Execution Documentation",
            source_type="official_product_documentation",
            url="https://docs.temporal.io/workflow-execution",
            freshness="current_durable_execution_pattern",
            credibility_score=4,
            applicability_score=4,
            safe_borrow=["durable_execution", "event_history", "retries", "signals", "timers"],
            avoid=["using_durable_retries_for_unapproved_external_actions"],
        ),
        PublicResearchSource(
            source_id="src_prefect_docs",
            title="Prefect Workflow Orchestration Documentation",
            source_type="official_product_documentation",
            url="https://docs.prefect.io/v3/get-started",
            freshness="current_data_workflow_orchestration_pattern",
            credibility_score=4,
            applicability_score=3,
            safe_borrow=["flow_monitoring", "task_retries", "state_tracking", "data_pipeline_observability"],
            avoid=["treating_observability_as_approval"],
        ),
        PublicResearchSource(
            source_id="src_slsa_requirements",
            title="SLSA Requirements",
            source_type="official_supply_chain_framework",
            url="https://slsa.dev/spec/v1.0/requirements",
            freshness="current_supply_chain_provenance_framework",
            credibility_score=5,
            applicability_score=4,
            safe_borrow=["provenance_attestation", "tamper_resistance", "artifact_authenticity"],
            avoid=["release_without_verifiable_provenance"],
        ),
        PublicResearchSource(
            source_id="src_nist_pqc",
            title="NIST Post-Quantum Cryptography Standards",
            source_type="official_cryptographic_standard",
            url="https://csrc.nist.gov/projects/post-quantum-cryptography",
            freshness="2024_principal_pqc_standards",
            credibility_score=5,
            applicability_score=4,
            safe_borrow=["ML-KEM", "ML-DSA", "SLH-DSA", "post_quantum_migration_targets"],
            avoid=["inventing_custom_cryptography", "claiming_quantum_encryption_without_infrastructure"],
        ),
    ]


def procured_layers() -> List[ProcuredLayer]:
    return [
        ProcuredLayer(
            layer_id="layer_public_research_provenance",
            name="Public research provenance matrix",
            status="procured_as_catalog",
            priority="P0",
            source_ids=["src_nist_ai_rmf", "src_nist_ssdf", "src_owasp_llm_top10"],
            missing_reason="AIGC had architecture docs but no first-class record proving which public sources justified new layers.",
            procurement_action="Instantiate a source-ranked procurement catalog before future layer implementation.",
            acceptance_tests=["catalog_has_sources", "each_layer_has_source_ids", "no_external_action"],
            risk_controls=["source_url_required", "credibility_score_required", "avoidance_notes_required"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_ai_rmf_govern_map_measure_manage",
            name="AI RMF Govern/Map/Measure/Manage control plane",
            status="planned_for_mvp_plus",
            priority="P0",
            source_ids=["src_nist_ai_rmf"],
            missing_reason="Current gates are strong, but AI risk controls are not grouped under a formal AI RMF lifecycle.",
            procurement_action="Add an AI risk-control mapping document, schema, and tests before expanded agent execution.",
            acceptance_tests=["ai_rmf_functions_present", "risk_owner_present", "measurements_present"],
            risk_controls=["governance_owner", "risk_register", "measurement_evidence", "management_response"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_tool_guardrail_mesh",
            name="Input/tool/output guardrail mesh",
            status="planned_for_mvp_plus",
            priority="P0",
            source_ids=["src_openai_agents_sdk", "src_owasp_llm_top10"],
            missing_reason="AIGC has approval gates, but tool-level guardrails need a dedicated contract for every function/tool invocation.",
            procurement_action="Define tool guardrail policies for inputs, tool calls, outputs, and model-produced action requests.",
            acceptance_tests=["tool_guardrails_cover_all_connectors", "prompt_injection_blocks_tool_use"],
            risk_controls=["blocking_guardrails_before_tools", "output_validation", "tool_permission_manifest"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_human_interrupt_resume",
            name="Human interrupt and resumable approval state",
            status="planned_for_mvp_plus",
            priority="P0",
            source_ids=["src_langgraph_interrupts", "src_openai_agents_sdk"],
            missing_reason="Approval exists, but resumable state and interrupt records are not yet first-class workflow contracts.",
            procurement_action="Add interrupt records that pause before external action and require revalidation on resume.",
            acceptance_tests=["interrupt_before_external_action", "resume_requires_current_permit"],
            risk_controls=["checkpointed_state", "permit_revalidation", "expiry_check", "artifact_hash_check"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_durable_workflow_readiness",
            name="Durable workflow execution readiness",
            status="planned_for_mvp_double_plus",
            priority="P1",
            source_ids=["src_temporal_workflow_execution"],
            missing_reason="Long-running business cycles are still subprocess-first and lack durable event-history semantics.",
            procurement_action="Design Temporal-ready workflow records without enabling Temporal deployment yet.",
            acceptance_tests=["workflow_event_history_recorded", "retry_policy_never_retries_unapproved_external_action"],
            risk_controls=["durable_event_history", "signals", "timers", "retry_policy_boundary"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_data_workflow_observability",
            name="Data workflow and evidence observability",
            status="planned_for_mvp_double_plus",
            priority="P1",
            source_ids=["src_prefect_docs"],
            missing_reason="Evidence pack refresh and reporting flows need richer task state and observability contracts.",
            procurement_action="Add Prefect-ready flow records for evidence refresh and reporting without installing services.",
            acceptance_tests=["flow_state_recorded", "evidence_refresh_has_lineage", "observability_not_approval"],
            risk_controls=["flow_state_tracking", "task_logs", "data_lineage", "human_gate_separate"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_supply_chain_provenance",
            name="Supply-chain provenance and release attestation",
            status="planned_for_mvp_double_plus",
            priority="P0",
            source_ids=["src_slsa_requirements", "src_nist_ssdf"],
            missing_reason="PR CI exists, but signed provenance, SBOM, and release attestation are not yet first-class.",
            procurement_action="Add release provenance schema, SBOM guidance, signing plan, and provenance validation tests.",
            acceptance_tests=["release_manifest_has_commit", "provenance_attestation_required", "sbom_path_declared"],
            risk_controls=["tamper_evident_release", "dependency_inventory", "build_provenance"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_prompt_injection_red_team",
            name="Prompt-injection and excessive-agency red-team harness",
            status="planned_for_mvp_plus",
            priority="P0",
            source_ids=["src_owasp_llm_top10"],
            missing_reason="Static redaction tests exist, but adversarial prompt/tool-use fixtures are not yet a dedicated suite.",
            procurement_action="Create fixtures that try to force impersonation, credential use, platform bypass, payment, and unchecked outward action.",
            acceptance_tests=["prompt_injection_fixture_blocked", "excessive_agency_fixture_blocked"],
            risk_controls=["adversarial_fixture_library", "guardrail_tripwire", "blocked_action_audit"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_privacy_retention_classification",
            name="Privacy, retention, and data-classification layer",
            status="planned_for_mvp_plus",
            priority="P0",
            source_ids=["src_owasp_llm_top10", "src_nist_ai_rmf"],
            missing_reason="Redaction scanning exists, but retention class, data minimization, and buyer data boundaries need explicit contracts.",
            procurement_action="Add data classification and retention schemas for artifacts, prompts, logs, and exports.",
            acceptance_tests=["artifact_has_data_class", "retention_policy_declared", "client_data_not_in_probe_payload"],
            risk_controls=["data_minimization", "retention_expiry", "buyer_workspace_boundary", "export_filtering"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_cost_rate_limit_budget",
            name="Cost, rate-limit, and unbounded-consumption guard",
            status="planned_for_mvp_plus",
            priority="P1",
            source_ids=["src_owasp_llm_top10", "src_openai_agents_sdk"],
            missing_reason="AIGC has safety gates, but no dedicated cost budget and rate-limit contract for agent/tool loops.",
            procurement_action="Add budget envelopes, max-step limits, max-token limits, and per-run rate controls.",
            acceptance_tests=["run_has_budget", "agent_loop_has_step_limit", "tool_call_rate_limit_present"],
            risk_controls=["bounded_compute", "budget_tripwire", "operator_override_required"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_post_quantum_crypto_provider",
            name="Vetted post-quantum crypto provider integration plan",
            status="partially_procured_as_onion_envelope",
            priority="P1",
            source_ids=["src_nist_pqc"],
            missing_reason="AIGC now has a post-quantum-ready envelope, but not a vetted provider-backed encryption/signature implementation.",
            procurement_action="Keep envelope planning in repo; require vetted library, KMS/HSM, or provider integration before real encryption claims.",
            acceptance_tests=["no_literal_quantum_claim", "no_secret_material_in_repo", "provider_required_for_real_encryption"],
            risk_controls=["ML_KEM_migration_target", "ML_DSA_or_SLH_DSA_signature_target", "secret_manager_boundary"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
        ProcuredLayer(
            layer_id="layer_buyer_tenant_isolation",
            name="Buyer tenant isolation and workspace boundary",
            status="planned_for_mvp_triple_plus",
            priority="P1",
            source_ids=["src_nist_ai_rmf", "src_nist_ssdf"],
            missing_reason="Sellable-folder posture exists, but multi-buyer isolation is not yet an enforceable runtime contract.",
            procurement_action="Design tenant workspace IDs, storage partitions, export filters, and per-buyer audit boundaries.",
            acceptance_tests=["tenant_id_required", "cross_tenant_path_blocked", "export_filters_private_data"],
            risk_controls=["tenant_storage_boundary", "path_sandbox", "audit_partition", "secret_scope_per_tenant"],
            forbidden_targets_blocked=FORBIDDEN_PROCUREMENT_TARGETS,
        ),
    ]


def validate_public_research_procurement_catalog(catalog: Dict[str, Any]) -> Dict[str, Any]:
    if catalog.get("external_action_performed") is not False:
        raise ValueError("Public research procurement catalog must not perform external action.")
    source_ids = {source.get("source_id") for source in catalog.get("sources", [])}
    if not source_ids:
        raise ValueError("Public research procurement catalog requires sources.")
    for source in catalog.get("sources", []):
        if not source.get("url", "").startswith("https://"):
            raise ValueError(f"{source.get('source_id')} must use an HTTPS source URL.")
        if int(source.get("credibility_score", 0)) < 4:
            raise ValueError(f"{source.get('source_id')} credibility score is too low for procurement basis.")
    for layer in catalog.get("procured_layers", []):
        if layer.get("external_action_performed") is not False:
            raise ValueError(f"{layer.get('layer_id')} must not perform external action.")
        if layer.get("human_review_required") is not True:
            raise ValueError(f"{layer.get('layer_id')} must require human review.")
        if not set(layer.get("source_ids", [])).issubset(source_ids):
            raise ValueError(f"{layer.get('layer_id')} references unknown sources.")
        missing_forbidden = set(FORBIDDEN_PROCUREMENT_TARGETS) - set(layer.get("forbidden_targets_blocked", []))
        if missing_forbidden:
            raise ValueError(f"{layer.get('layer_id')} missing forbidden target blocks: {sorted(missing_forbidden)}")
    boundary = catalog.get("procurement_boundary", {})
    for key in ["external_services_installed", "accounts_configured", "credentials_read", "live_actions_executed"]:
        if boundary.get(key) is not False:
            raise ValueError(f"Procurement boundary must keep {key}=false.")
    return catalog


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
