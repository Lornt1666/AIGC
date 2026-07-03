from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.contract_validator import validate_artifact
from src.core.phase_registry import build_phase_registry
from src.phase30_omni_agent_cloud_intelligence import OmniAgentCloudIntelligenceArchitecture


def test_phase30_generates_contract_valid_architecture_records(tmp_path: Path) -> None:
    create_phase30_fixture(tmp_path)
    records = OmniAgentCloudIntelligenceArchitecture(tmp_path).run_from_config(
        tmp_path / "config" / "phase30_omni_agent_cloud_intelligence.json"
    )
    assert len(records) == 2
    payload = json.loads(
        (tmp_path / "data" / "phase30_omni_agent_cloud" / "aigc_phase30_omni_agent_architecture_records.json").read_text(
            encoding="utf-8"
        )
    )
    validate_artifact("omni_agent_architecture_record", payload[0])
    assert payload[0]["deployment_allowed"] is False
    assert payload[0]["live_connectors_allowed"] is False
    assert payload[0]["external_action_performed"] is False
    assert payload[0]["formal_ontology"]["entities"]
    assert payload[0]["cloud_topology"]["cloud_runtime_status"] == "not_deployed_internal_blueprint_only"


def test_phase30_records_pending_freshness_gaps(tmp_path: Path) -> None:
    create_phase30_fixture(tmp_path)
    OmniAgentCloudIntelligenceArchitecture(tmp_path).run_from_config(
        tmp_path / "config" / "phase30_omni_agent_cloud_intelligence.json"
    )
    payload = json.loads(
        (tmp_path / "data" / "phase30_omni_agent_cloud" / "aigc_phase30_omni_agent_architecture_records.json").read_text(
            encoding="utf-8"
        )
    )
    governance = next(item for item in payload if item["architecture_domain"] == "governance_policy_and_audit_layer")
    assert governance["status"] == "architecture_procurement_gaps_recorded"
    assert any("freshness reviews remain pending" in gap for gap in governance["gap_analysis"])
    assert governance["governance_controls"]["phase29_freshness_review_required_before_regeneration"] is True


def test_phase_registry_includes_phase30_omni_agent_cloud_intelligence() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase30"].schema_name == "omni_agent_architecture_record"
    assert registry["phase30"].external_action_risk == "none_internal_cloud_architecture_procurement_only"


def create_phase30_fixture(root: Path) -> None:
    for directory in [
        "config",
        "data/phase10_connectors",
        "data/phase16_compliance",
        "data/phase17_incidents",
        "data/phase18_productization",
        "data/phase19_subagents",
        "data/phase20_fidelity",
        "data/phase21_customer_satisfaction",
        "data/phase22_quality",
        "data/phase23_work_orders",
        "data/phase24_procurement",
        "data/phase25_intelligence",
        "data/phase26_capability_procurement",
        "data/phase27_renewal",
        "data/phase28_regeneration",
        "data/phase29_freshness_reviews",
    ]:
        (root / directory).mkdir(parents=True, exist_ok=True)
    write_json(root / "data/phase10_connectors/aigc_phase10_connector_registry.json", [{"connector_id": "c1"}])
    write_json(root / "data/phase16_compliance/aigc_phase16_compliance_reviews.json", [{"review_id": "r1"}])
    write_json(root / "data/phase17_incidents/incident_response_summary.json", {"summary_id": "i1"})
    write_json(root / "data/phase18_productization/aigc_phase18_release_readiness.json", {
        "release_id": "rel1",
        "deployment_performed": False,
        "public_release_allowed": False,
    })
    write_json(root / "data/phase19_subagents/aigc_phase19_subagent_team_plans.json", [{"team_id": "t1"}])
    write_json(root / "data/phase20_fidelity/aigc_phase20_fidelity_reviews.json", [{"review_id": "f1"}])
    write_json(root / "data/phase21_customer_satisfaction/aigc_phase21_customer_satisfaction_records.json", [{"record_id": "c1"}])
    write_json(root / "data/phase22_quality/aigc_phase22_quality_kernel_records.json", [{"record_id": "q1"}])
    write_json(root / "data/phase23_work_orders/aigc_phase23_work_order_governance_records.json", [{"record_id": "w1"}])
    write_json(root / "data/phase24_procurement/aigc_phase24_procurement_records.json", [{"record_id": "p1"}])
    write_json(root / "data/phase25_intelligence/aigc_phase25_intelligence_ingestion_records.json", [{"record_id": "n1"}])
    write_json(root / "data/phase26_capability_procurement/aigc_phase26_capability_procurement_records.json", [{"record_id": "cap1"}])
    write_json(root / "data/phase27_renewal/aigc_phase27_stale_artifact_renewal_records.json", [{"record_id": "s1"}])
    write_json(root / "data/phase28_regeneration/aigc_phase28_regeneration_candidates.json", [{"record_id": "g1", "regeneration_allowed": False}])
    write_json(root / "data/phase29_freshness_reviews/aigc_phase29_freshness_review_records.json", [{"record_id": "fr1", "decision": "pending"}])
    write_json(root / "config/phase30_omni_agent_cloud_intelligence.json", {
        "output_file": "data/phase30_omni_agent_cloud/aigc_phase30_omni_agent_architecture_records.json",
        "report_file": "data/reports/phase30_signature_update.md",
        "audit_log": "data/audit/aigc_phase30_audit.jsonl",
        "deployment_allowed": False,
        "live_connectors_allowed": False,
        "input_files": {
            "connector_registry": "data/phase10_connectors/aigc_phase10_connector_registry.json",
            "compliance_reviews": "data/phase16_compliance/aigc_phase16_compliance_reviews.json",
            "incident_summary": "data/phase17_incidents/incident_response_summary.json",
            "productization_release": "data/phase18_productization/aigc_phase18_release_readiness.json",
            "subagent_team_plans": "data/phase19_subagents/aigc_phase19_subagent_team_plans.json",
            "fidelity_reviews": "data/phase20_fidelity/aigc_phase20_fidelity_reviews.json",
            "customer_satisfaction_records": "data/phase21_customer_satisfaction/aigc_phase21_customer_satisfaction_records.json",
            "quality_kernel_records": "data/phase22_quality/aigc_phase22_quality_kernel_records.json",
            "work_order_governance_records": "data/phase23_work_orders/aigc_phase23_work_order_governance_records.json",
            "truth_first_procurement_records": "data/phase24_procurement/aigc_phase24_procurement_records.json",
            "intelligence_ingestion_records": "data/phase25_intelligence/aigc_phase25_intelligence_ingestion_records.json",
            "capability_procurement_records": "data/phase26_capability_procurement/aigc_phase26_capability_procurement_records.json",
            "stale_artifact_renewal_records": "data/phase27_renewal/aigc_phase27_stale_artifact_renewal_records.json",
            "regeneration_candidate_records": "data/phase28_regeneration/aigc_phase28_regeneration_candidates.json",
            "freshness_review_records": "data/phase29_freshness_reviews/aigc_phase29_freshness_review_records.json"
        },
        "ontology_entities": ["Agent", "Task", "Workflow", "Capability", "Tool", "Goal", "Policy", "Artifact"],
        "ontology_relationships": ["Agent performs Task", "Policy governs Task"],
        "methodology_steps": ["perception", "interpretation", "planning", "execution", "verification", "reflection"],
        "cloud_topology_layers": ["interface_layer", "governance_layer"],
        "agent_archetypes": ["Architect Agent", "Programming Agent", "Compliance Agent"],
        "everyday_work_domains": ["emails_reports_proposals_documentation", "code_refactor_test_deploy"],
        "architecture_procurements": [
            {
                "domain": "formal_ontology_and_methodology_kernel",
                "purpose": "test ontology",
                "source_aliases": ["quality_kernel_records", "work_order_governance_records"],
                "required_capabilities": ["formal_ontology_mapping"]
            },
            {
                "domain": "governance_policy_and_audit_layer",
                "purpose": "test governance",
                "source_aliases": [
                    "compliance_reviews",
                    "incident_summary",
                    "truth_first_procurement_records",
                    "intelligence_ingestion_records",
                    "stale_artifact_renewal_records",
                    "regeneration_candidate_records",
                    "freshness_review_records"
                ],
                "required_capabilities": ["legal_ethical_policy_gates"]
            }
        ],
        "blocked_actions": ["deploy_cloud_runtime_without_operator_approval", "enable_live_connectors"]
    })


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
