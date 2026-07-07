from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.core.public_research_procurement import FORBIDDEN_PROCUREMENT_TARGETS


REQUESTED_LAYER_IDS = [
    "ai_rmf_control_plane",
    "guardrail_mesh",
    "human_interrupt_resume",
    "durable_workflow_readiness",
    "evidence_workflow_observability",
    "supply_chain_provenance",
    "prompt_injection_red_team",
    "privacy_retention_classification",
    "cost_rate_limit_guard",
    "post_quantum_provider_plan",
    "buyer_tenant_isolation",
]


@dataclass(frozen=True)
class ProcuredControlLayer:
    layer_id: str
    name: str
    status: str
    source_ids: List[str]
    control_objective: str
    formations_procured: List[str]
    schemas_to_create: List[str]
    modules_to_create: List[str]
    tests_to_create: List[str]
    controls: List[str]
    acceptance_tests: List[str]
    blocked_failure_modes: List[str]
    implementation_boundary: str
    human_review_required: bool = True
    external_action_performed: bool = False


@dataclass(frozen=True)
class ProcuredSafeCommand:
    command_id: str
    command: str
    purpose: str
    prerequisites: List[str]
    forbidden_side_effects: List[str]
    verification_after_command: List[str]
    human_review_required: bool = True
    external_action_performed: bool = False


def build_procured_control_layers_catalog() -> Dict[str, Any]:
    layers = [asdict(layer) for layer in procured_layers()]
    safe_commands = [asdict(command) for command in procured_safe_commands()]
    catalog = {
        "catalog_id": "AIGC-PROCURED-CONTROL-LAYERS-v1",
        "created_at": utc_now(),
        "status": "procured_as_local_contracts",
        "requested_layer_ids": REQUESTED_LAYER_IDS,
        "procured_layers": layers,
        "procured_safe_commands": safe_commands,
        "procurement_boundary": {
            "external_services_installed": False,
            "accounts_configured": False,
            "credentials_read": False,
            "live_actions_executed": False,
            "push_command_executed_by_catalog": False,
            "merge_or_deploy_authorized": False,
        },
        "forbidden_procurement_targets": FORBIDDEN_PROCUREMENT_TARGETS,
        "external_action_performed": False,
    }
    return validate_procured_control_layers_catalog(catalog)


def procured_layers() -> List[ProcuredControlLayer]:
    return [
        ProcuredControlLayer(
            layer_id="ai_rmf_control_plane",
            name="AI RMF Govern/Map/Measure/Manage control plane",
            status="procured_as_governance_contract",
            source_ids=["src_nist_ai_rmf"],
            control_objective="Map every AIGC AI capability to Govern, Map, Measure, and Manage outcomes.",
            formations_procured=["risk_owner_matrix", "trustworthiness_metrics", "risk_response_register"],
            schemas_to_create=["ai_rmf_control_record"],
            modules_to_create=["ai_rmf_control_plane"],
            tests_to_create=["test_ai_rmf_control_plane"],
            controls=["risk_owner_required", "measurement_required", "management_response_required"],
            acceptance_tests=["all_four_ai_rmf_functions_present", "risk_controls_have_owners", "measurements_have_evidence"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Local governance mapping only; no external AI action authority.",
        ),
        ProcuredControlLayer(
            layer_id="guardrail_mesh",
            name="Input/tool/output guardrail mesh",
            status="procured_as_tool_guardrail_contract",
            source_ids=["src_openai_agents_sdk", "src_owasp_llm_top10"],
            control_objective="Require input, tool-call, and output guardrails around every agent or connector action.",
            formations_procured=["input_guardrail", "tool_guardrail", "output_guardrail", "tripwire_policy"],
            schemas_to_create=["guardrail_mesh_record"],
            modules_to_create=["guardrail_mesh"],
            tests_to_create=["test_guardrail_mesh"],
            controls=["blocking_guardrail_before_tool", "tripwire_audit_event", "tool_permission_manifest"],
            acceptance_tests=["prompt_injection_blocks_tool_call", "forbidden_action_tripwire_blocks", "output_guardrail_requires_review"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Local policy evaluation only; no live connector execution.",
        ),
        ProcuredControlLayer(
            layer_id="human_interrupt_resume",
            name="Human interrupt and resumable approval state",
            status="procured_as_interrupt_contract",
            source_ids=["src_langgraph_interrupts", "src_openai_agents_sdk"],
            control_objective="Pause before external action and require permit revalidation before resume.",
            formations_procured=["interrupt_record", "resume_token_reference", "permit_revalidation"],
            schemas_to_create=["human_interrupt_record"],
            modules_to_create=["human_interrupts"],
            tests_to_create=["test_human_interrupt_resume"],
            controls=["interrupt_before_external_action", "resume_requires_current_permit", "artifact_hash_recheck"],
            acceptance_tests=["external_action_creates_interrupt", "expired_permit_blocks_resume", "hash_mismatch_blocks_resume"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Checkpoint metadata only; no workflow engine dependency enabled.",
        ),
        ProcuredControlLayer(
            layer_id="durable_workflow_readiness",
            name="Durable workflow readiness",
            status="procured_as_temporal_ready_contract",
            source_ids=["src_temporal_workflow_execution"],
            control_objective="Prepare durable execution records with event history, retry boundaries, signals, and timers.",
            formations_procured=["workflow_event_history", "retry_policy_boundary", "signal_contract", "timer_contract"],
            schemas_to_create=["durable_workflow_readiness_record"],
            modules_to_create=["durable_workflow_readiness"],
            tests_to_create=["test_durable_workflow_readiness"],
            controls=["no_retry_for_unapproved_external_action", "event_history_required", "signal_revalidates_gate"],
            acceptance_tests=["event_history_present", "unapproved_external_retry_disabled", "timer_does_not_bypass_approval"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Temporal-ready design only; Temporal is not installed or connected.",
        ),
        ProcuredControlLayer(
            layer_id="evidence_workflow_observability",
            name="Evidence and data workflow observability",
            status="procured_as_prefect_ready_contract",
            source_ids=["src_prefect_docs"],
            control_objective="Track evidence refresh and reporting flows without confusing observability with approval.",
            formations_procured=["flow_state_record", "evidence_lineage", "task_log_summary"],
            schemas_to_create=["evidence_workflow_observability_record"],
            modules_to_create=["evidence_observability"],
            tests_to_create=["test_evidence_workflow_observability"],
            controls=["flow_state_required", "lineage_required", "approval_status_separate_from_observability"],
            acceptance_tests=["flow_record_has_lineage", "observability_never_sets_approval", "report_refresh_has_evidence_ids"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Prefect-ready metadata only; no Prefect service configured.",
        ),
        ProcuredControlLayer(
            layer_id="supply_chain_provenance",
            name="Supply-chain provenance, SBOM, and release attestation",
            status="procured_as_release_integrity_contract",
            source_ids=["src_slsa_requirements", "src_nist_ssdf"],
            control_objective="Require release provenance, SBOM path, artifact digest, and attestation plan before buyer export.",
            formations_procured=["release_provenance_record", "sbom_reference", "attestation_plan"],
            schemas_to_create=["supply_chain_provenance_record"],
            modules_to_create=["supply_chain_provenance"],
            tests_to_create=["test_supply_chain_provenance"],
            controls=["commit_digest_required", "build_command_recorded", "sbom_path_declared", "signature_plan_declared"],
            acceptance_tests=["release_has_provenance", "sbom_reference_present", "unsigned_release_marked_not_final"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Release-integrity metadata only; no signing key or release publication.",
        ),
        ProcuredControlLayer(
            layer_id="prompt_injection_red_team",
            name="Prompt-injection and excessive-agency red-team harness",
            status="procured_as_adversarial_test_contract",
            source_ids=["src_owasp_llm_top10"],
            control_objective="Continuously test that malicious prompts cannot cause forbidden tool use or outward action.",
            formations_procured=["adversarial_fixture_library", "excessive_agency_tripwire", "blocked_action_audit"],
            schemas_to_create=["red_team_fixture_record"],
            modules_to_create=["red_team_harness"],
            tests_to_create=["test_prompt_injection_red_team"],
            controls=["fixture_category_required", "expected_block_required", "tripwire_reason_required"],
            acceptance_tests=["impersonation_fixture_blocked", "credential_fixture_blocked", "payment_fixture_blocked"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Local fixtures and policy simulation only; no hostile web interaction.",
        ),
        ProcuredControlLayer(
            layer_id="privacy_retention_classification",
            name="Privacy, retention, and data-classification layer",
            status="procured_as_data_governance_contract",
            source_ids=["src_owasp_llm_top10", "src_nist_ai_rmf"],
            control_objective="Classify artifacts by data sensitivity, retention, exportability, and buyer boundary.",
            formations_procured=["data_classification_record", "retention_policy", "export_filter"],
            schemas_to_create=["privacy_retention_record"],
            modules_to_create=["privacy_retention"],
            tests_to_create=["test_privacy_retention"],
            controls=["data_class_required", "retention_period_required", "export_policy_required"],
            acceptance_tests=["client_data_not_exportable_by_default", "retention_class_present", "private_artifact_blocked_from_sellable_folder"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Classification metadata only; no deletion or external export performed.",
        ),
        ProcuredControlLayer(
            layer_id="cost_rate_limit_guard",
            name="Cost, rate-limit, and unbounded-consumption guard",
            status="procured_as_budget_guard_contract",
            source_ids=["src_owasp_llm_top10", "src_openai_agents_sdk"],
            control_objective="Bound agent loops, tool calls, tokens, retries, and spend before execution.",
            formations_procured=["run_budget", "rate_limit_policy", "loop_tripwire", "cost_guard"],
            schemas_to_create=["budget_rate_limit_record"],
            modules_to_create=["budget_rate_limit_guard"],
            tests_to_create=["test_budget_rate_limit_guard"],
            controls=["max_steps_required", "max_tool_calls_required", "max_estimated_cost_required", "operator_override_required"],
            acceptance_tests=["missing_budget_blocks_run", "step_limit_blocks_loop", "cost_ceiling_blocks_expansion"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Budget policy metadata only; no provider billing API access.",
        ),
        ProcuredControlLayer(
            layer_id="post_quantum_provider_plan",
            name="Vetted post-quantum crypto provider plan",
            status="procured_as_provider_selection_contract",
            source_ids=["src_nist_pqc"],
            control_objective="Select a future vetted provider path for ML-KEM and ML-DSA/SLH-DSA without custom crypto.",
            formations_procured=["provider_selection_criteria", "key_management_boundary", "crypto_claim_rules"],
            schemas_to_create=["post_quantum_provider_plan"],
            modules_to_create=["post_quantum_provider_plan"],
            tests_to_create=["test_post_quantum_provider_plan"],
            controls=["no_custom_crypto", "no_literal_quantum_claim", "kms_or_vetted_library_required"],
            acceptance_tests=["provider_plan_requires_vetted_source", "secret_material_absent", "real_encryption_claim_false_until_provider"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Provider-selection plan only; no cryptographic provider installed or configured.",
        ),
        ProcuredControlLayer(
            layer_id="buyer_tenant_isolation",
            name="Buyer tenant isolation and workspace boundary",
            status="procured_as_tenant_boundary_contract",
            source_ids=["src_nist_ai_rmf", "src_nist_ssdf"],
            control_objective="Separate buyer workspaces, exports, secrets, audit logs, and generated artifacts.",
            formations_procured=["tenant_boundary_record", "workspace_partition", "cross_tenant_block"],
            schemas_to_create=["tenant_isolation_record"],
            modules_to_create=["tenant_isolation"],
            tests_to_create=["test_tenant_isolation"],
            controls=["tenant_id_required", "workspace_root_required", "cross_tenant_path_blocked", "secret_scope_per_tenant"],
            acceptance_tests=["tenant_id_required", "cross_tenant_path_rejected", "export_manifest_filters_private_data"],
            blocked_failure_modes=FORBIDDEN_PROCUREMENT_TARGETS,
            implementation_boundary="Tenant-boundary policy only; no multi-tenant service deployed.",
        ),
    ]


def procured_safe_commands() -> List[ProcuredSafeCommand]:
    return [
        ProcuredSafeCommand(
            command_id="next_safe_push_pr12",
            command="git push -u origin codex/operator-cockpit-run-accept",
            purpose="Update draft PR #12 with locally verified procurement commits.",
            prerequisites=[
                "git status shows only intended committed changes",
                "python .\\src\\aigc.py validate passes",
                "redaction scanner passes",
                "git diff --check passes",
                "python -m pytest -q passes",
                "branch remains codex/operator-cockpit-run-accept",
            ],
            forbidden_side_effects=[
                "merge_pull_request",
                "deploy_service",
                "publish_release",
                "procure_paid_service",
                "read_secrets",
                "execute_live_connectors",
            ],
            verification_after_command=[
                "git status -sb --untracked-files=all",
                "git log -1 --oneline",
                "gh pr view 12 --json number,isDraft,headRefOid,mergeStateStatus,url",
                "gh pr checks 12",
            ],
            human_review_required=True,
            external_action_performed=False,
        )
    ]


def validate_procured_control_layers_catalog(catalog: Dict[str, Any]) -> Dict[str, Any]:
    if catalog.get("external_action_performed") is not False:
        raise ValueError("Procured control layers catalog must not perform external action.")
    requested = set(catalog.get("requested_layer_ids", []))
    procured = {layer.get("layer_id") for layer in catalog.get("procured_layers", [])}
    missing = requested - procured
    if missing:
        raise ValueError(f"Missing requested procured layers: {sorted(missing)}")
    for layer in catalog.get("procured_layers", []):
        if layer.get("status", "").startswith("planned"):
            raise ValueError(f"{layer.get('layer_id')} is still planned, not procured.")
        if layer.get("human_review_required") is not True:
            raise ValueError(f"{layer.get('layer_id')} must require human review.")
        if layer.get("external_action_performed") is not False:
            raise ValueError(f"{layer.get('layer_id')} must not perform external action.")
        if not layer.get("source_ids"):
            raise ValueError(f"{layer.get('layer_id')} must reference public research sources.")
        if not layer.get("acceptance_tests"):
            raise ValueError(f"{layer.get('layer_id')} must define acceptance tests.")
        if not layer.get("controls"):
            raise ValueError(f"{layer.get('layer_id')} must define controls.")
        missing_forbidden = set(FORBIDDEN_PROCUREMENT_TARGETS) - set(layer.get("blocked_failure_modes", []))
        if missing_forbidden:
            raise ValueError(f"{layer.get('layer_id')} missing forbidden failure modes: {sorted(missing_forbidden)}")
    for command in catalog.get("procured_safe_commands", []):
        if command.get("external_action_performed") is not False:
            raise ValueError(f"{command.get('command_id')} must not be marked executed by the catalog.")
        if command.get("human_review_required") is not True:
            raise ValueError(f"{command.get('command_id')} must require human review.")
        if "git push -u origin codex/operator-cockpit-run-accept" not in command.get("command", ""):
            raise ValueError("Expected PR branch push command was not procured.")
    boundary = catalog.get("procurement_boundary", {})
    for key in [
        "external_services_installed",
        "accounts_configured",
        "credentials_read",
        "live_actions_executed",
        "push_command_executed_by_catalog",
        "merge_or_deploy_authorized",
    ]:
        if boundary.get(key) is not False:
            raise ValueError(f"Procurement boundary must keep {key}=false.")
    return catalog


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
