from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PhaseDefinition:
    name: str
    display_name: str
    input_path: str
    output_path: str
    schema_name: str
    command: List[str]
    allowed_runtime_modes: List[str]
    external_action_risk: str


def build_phase_registry(root: Path = PROJECT_ROOT) -> Dict[str, PhaseDefinition]:
    py = sys.executable
    src = root / "src"
    return {
        "phase2": PhaseDefinition(
            name="phase2",
            display_name="Phase 2 - Opportunity Radar",
            input_path="config/phase2_sources.json",
            output_path="data/phase2_processed/aigc_phase2_opportunity_queue.json",
            schema_name="opportunity_record",
            command=[py, str(src / "phase2_radar.py")],
            allowed_runtime_modes=["read_only"],
            external_action_risk="none_read_only",
        ),
        "phase3": PhaseDefinition(
            name="phase3",
            display_name="Phase 3 - Ology Assessment",
            input_path="data/phase2_processed/aigc_phase2_opportunity_queue.json",
            output_path="data/phase3_processed/aigc_phase3_assessment_dossiers.json",
            schema_name="assessment_dossier",
            command=[py, str(src / "phase3_ology_assessment.py")],
            allowed_runtime_modes=["internal_only"],
            external_action_risk="none_internal_assessment",
        ),
        "phase4": PhaseDefinition(
            name="phase4",
            display_name="Phase 4 - Proposal Drafting",
            input_path="data/phase3_processed/aigc_phase3_assessment_dossiers.json",
            output_path="data/phase4_proposals/aigc_phase4_proposal_packages.json",
            schema_name="proposal_package",
            command=[py, str(src / "phase4_proposal_drafting.py")],
            allowed_runtime_modes=["internal_only"],
            external_action_risk="none_internal_draft",
        ),
        "phase5": PhaseDefinition(
            name="phase5",
            display_name="Phase 5 - Human Approval Gate",
            input_path="data/phase4_proposals/aigc_phase4_proposal_packages.json",
            output_path="data/phase5_authorizations/aigc_phase5_authorization_packets.json",
            schema_name="authorization_packet",
            command=[py, str(src / "phase5_human_approval_gate.py")],
            allowed_runtime_modes=["approval_gate"],
            external_action_risk="blocked_until_operator_approval",
        ),
        "phase6": PhaseDefinition(
            name="phase6",
            display_name="Phase 6 - Controlled Execution",
            input_path="data/phase5_authorizations/aigc_phase5_authorization_packets.json",
            output_path="data/phase6_execution/aigc_phase6_execution_receipts.json",
            schema_name="execution_receipt",
            command=[py, str(src / "phase6_controlled_execution.py")],
            allowed_runtime_modes=["manual_handoff_only"],
            external_action_risk="requires_phase5_approval",
        ),
        "phase7": PhaseDefinition(
            name="phase7",
            display_name="Phase 7 - Employer Audit Packet",
            input_path="data/phase6_execution/aigc_phase6_execution_receipts.json",
            output_path="data/phase7_audit_packets/aigc_phase7_employer_audit_packets.json",
            schema_name="employer_audit_packet",
            command=[py, str(src / "phase7_employer_audit_packet.py")],
            allowed_runtime_modes=["internal_draft_only"],
            external_action_risk="external_sharing_requires_approval",
        ),
        "phase8": PhaseDefinition(
            name="phase8",
            display_name="Phase 8 - Evolution Loop",
            input_path="data/phase7_audit_packets/aigc_phase7_employer_audit_packets.json",
            output_path="data/phase8_evolution/evolution_patches.jsonl",
            schema_name="evolution_patch",
            command=[py, str(src / "phase8_evolution_loop.py")],
            allowed_runtime_modes=["internal_evolution_only"],
            external_action_risk="behavior_changes_require_approval",
        ),
        "phase10": PhaseDefinition(
            name="phase10",
            display_name="Phase 10 - Connector / API Integration Layer",
            input_path="config/phase10_connector_registry.json",
            output_path="data/phase10_connectors/aigc_phase10_connector_registry.json",
            schema_name="connector_record",
            command=[py, str(src / "phase10_connector_registry.py")],
            allowed_runtime_modes=["read_only_connector_registry"],
            external_action_risk="no_live_write_connectors",
        ),
        "phase11": PhaseDefinition(
            name="phase11",
            display_name="Phase 11 - Security Vault",
            input_path="config/secret_manifest.json",
            output_path="data/reports/phase11_signature_update.md",
            schema_name="secret_manifest",
            command=[py, str(src / "phase11_security_vault.py"), "--fake-test"],
            allowed_runtime_modes=["internal_security_check"],
            external_action_risk="no_secret_value_logging",
        ),
        "phase12": PhaseDefinition(
            name="phase12",
            display_name="Phase 12 - Observability Dashboard",
            input_path="config/phase12_observability_dashboard.json",
            output_path="data/phase12_observability/system_snapshot.json",
            schema_name="runtime_event",
            command=[py, str(src / "phase12_observability_dashboard.py"), "--root", str(root), "--export"],
            allowed_runtime_modes=["internal_observability"],
            external_action_risk="none_internal_monitoring",
        ),
        "phase13": PhaseDefinition(
            name="phase13",
            display_name="Phase 13 - Simulation Arena",
            input_path="config/phase13_sandbox_arena.json",
            output_path="data/phase13_simulation/synthetic_simulation_result.json",
            schema_name="opportunity_record",
            command=[py, str(src / "phase13_simulation_arena.py"), "--root", str(root)],
            allowed_runtime_modes=["synthetic_sandbox", "real_data_read_only"],
            external_action_risk="none_read_only_or_synthetic",
        ),
        "phase14": PhaseDefinition(
            name="phase14",
            display_name="Phase 14 - Runtime Engine",
            input_path="config/phase14_runtime_engine.json",
            output_path="reports/phase14_runtime_preflight.md",
            schema_name="runtime_event",
            command=[py, str(src / "aigc.py"), "run", "phase14"],
            allowed_runtime_modes=["internal_preflight"],
            external_action_risk="none_preflight_only",
        ),
        "phase15": PhaseDefinition(
            name="phase15",
            display_name="Phase 15 - Finance, Contracts, and Asset Ledger",
            input_path="data/phase4_proposals/aigc_phase4_proposal_packages.json",
            output_path="data/phase15_finance/aigc_phase15_finance_ledger.json",
            schema_name="finance_ledger_record",
            command=[py, str(src / "phase15_finance_contracts_ledger.py")],
            allowed_runtime_modes=["internal_finance_tracking_only"],
            external_action_risk="none_internal_ledger_only",
        ),
        "phase16": PhaseDefinition(
            name="phase16",
            display_name="Phase 16 - Compliance and Legal Review",
            input_path="data/phase4_proposals/aigc_phase4_proposal_packages.json",
            output_path="data/phase16_compliance/aigc_phase16_compliance_reviews.json",
            schema_name="compliance_review",
            command=[py, str(src / "phase16_compliance_review.py")],
            allowed_runtime_modes=["internal_compliance_review_only"],
            external_action_risk="none_internal_review_only",
        ),
        "phase17": PhaseDefinition(
            name="phase17",
            display_name="Phase 17 - Incident Response and Recovery",
            input_path="config/phase17_incident_response.json",
            output_path="data/phase17_incidents/incident_reports.jsonl",
            schema_name="incident_report",
            command=[py, str(src / "phase17_incident_response.py")],
            allowed_runtime_modes=["internal_incident_response_only"],
            external_action_risk="none_internal_incident_reporting_only",
        ),
        "phase18": PhaseDefinition(
            name="phase18",
            display_name="Phase 18 - Scaling, Replication, and Productization",
            input_path="config/phase18_productization.json",
            output_path="data/phase18_productization/aigc_phase18_release_readiness.json",
            schema_name="productization_release_record",
            command=[py, str(src / "phase18_productization.py")],
            allowed_runtime_modes=["internal_release_readiness_only"],
            external_action_risk="deployment_and_public_release_require_approval",
        ),
        "phase19": PhaseDefinition(
            name="phase19",
            display_name="Phase 19 - Sub-Agent Generation Forge",
            input_path="data/phase4_proposals/aigc_phase4_proposal_packages.json",
            output_path="data/phase19_subagents/aigc_phase19_subagent_team_plans.json",
            schema_name="subagent_team_plan",
            command=[py, str(src / "phase19_subagent_forge.py")],
            allowed_runtime_modes=["internal_subagent_team_planning_only"],
            external_action_risk="subagents_cannot_execute_externally",
        ),
        "phase20": PhaseDefinition(
            name="phase20",
            display_name="Phase 20 - Fidelity Forge",
            input_path="data/phase19_subagents/aigc_phase19_subagent_team_plans.json",
            output_path="data/phase20_fidelity/aigc_phase20_fidelity_reviews.json",
            schema_name="fidelity_review",
            command=[py, str(src / "phase20_fidelity_forge.py")],
            allowed_runtime_modes=["internal_quality_review_only"],
            external_action_risk="none_internal_quality_review_only",
        ),
    }


def get_phase(name: str, root: Path = PROJECT_ROOT) -> PhaseDefinition:
    registry = build_phase_registry(root)
    if name not in registry:
        known = ", ".join(sorted(registry))
        raise KeyError(f"Unknown phase {name!r}. Known phases: {known}")
    return registry[name]
