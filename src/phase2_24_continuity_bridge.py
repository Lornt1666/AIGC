from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_phase2_24_continuity.json"
PHASE_NAME = "phase2_24_continuity_bridge"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_json_if_exists(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(root: Path, config_path: str) -> Dict[str, Any]:
    path = resolve_path(root, config_path)
    return load_json_if_exists(path, default_config())


def default_config() -> Dict[str, Any]:
    return {
        "input_router_config": "config/aigc_cognitive_phase_router.json",
        "input_phase1_plan": "data/phase1_cognitive_router/aigc_phase1_cognitive_plan.json",
        "output_plan": "data/phase2_24_continuity/aigc_phase2_24_continuity_plan.json",
        "output_report": "reports/phase2_24_continuity_report.md",
        "audit_log": "data/audit/aigc_phase2_24_continuity_audit.jsonl",
        "phase_range": {"start": 2, "end": 24},
        "safety_doctrine": {
            "external_action_allowed": False,
            "physical_file_moves_allowed": False,
            "source_rewrite_allowed": False,
            "workflow_rewrite_allowed": False,
            "credential_use_allowed": False,
            "secret_value_logging_allowed": False,
            "approval_required_for_future_write_back": True,
        },
        "phase_dependency_classes": {},
    }


def build_continuity_plan(root: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    router_config_path = resolve_path(root, config.get("input_router_config", "config/aigc_cognitive_phase_router.json"))
    phase1_plan_path = resolve_path(root, config.get("input_phase1_plan", "data/phase1_cognitive_router/aigc_phase1_cognitive_plan.json"))
    router_config = load_json_if_exists(router_config_path, {})
    phase1_plan = load_json_if_exists(phase1_plan_path, {})

    phase_range = config.get("phase_range", {"start": 2, "end": 24})
    start = int(phase_range.get("start", 2))
    end = int(phase_range.get("end", 24))
    dependency_classes = config.get("phase_dependency_classes", {})
    phase_slots = [
        slot for slot in router_config.get("phase_slots", [])
        if isinstance(slot, dict) and start <= int(slot.get("slot", -1)) <= end
    ]
    selected_sequence = extract_selected_sequence(phase1_plan)
    selected_set = set(selected_sequence)

    phase_records = []
    for index, slot in enumerate(sorted(phase_slots, key=lambda item: int(item.get("slot", 0))), start=1):
        phase_id = str(slot.get("id", f"phase{slot.get('slot', '')}"))
        class_record = dependency_classes.get(phase_id, {})
        configured_state = str(class_record.get("state", slot.get("status", "planned_gated")))
        selected = phase_id in selected_set
        artifact_paths = infer_artifact_paths(root, phase_id)
        missing_artifacts = [item for item in artifact_paths if not (root / item).exists()]
        readiness = determine_readiness(
            phase_id=phase_id,
            configured_state=configured_state,
            selected=selected,
            missing_artifacts=missing_artifacts,
        )
        phase_records.append({
            "continuity_order": index,
            "slot": slot.get("slot"),
            "phase_id": phase_id,
            "phase_name": slot.get("name", ""),
            "category": slot.get("category", ""),
            "selected_by_phase1_router": selected,
            "configured_state": configured_state,
            "readiness_state": readiness,
            "autonomous_execution_allowed_by_router_config": bool(slot.get("autonomous_execution_allowed", False)),
            "requires": class_record.get("requires", []),
            "known_or_expected_artifacts": artifact_paths,
            "missing_artifacts": missing_artifacts,
            "reason": class_record.get("reason", "No explicit dependency reason configured."),
            "effective_external_action_allowed": False,
            "physical_file_moves_performed": False,
            "source_rewrites_performed": False,
            "workflow_rewrites_performed": False,
            "credential_use_performed": False,
            "secret_values_logged": False,
        })

    readiness_counts = Counter(record["readiness_state"] for record in phase_records)
    configured_counts = Counter(record["configured_state"] for record in phase_records)
    selected_count = sum(1 for record in phase_records if record["selected_by_phase1_router"])

    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "completed_continuity_ledger",
        "phase_range": {"start": start, "end": end},
        "input_router_config_found": router_config_path.exists(),
        "input_phase1_plan_found": phase1_plan_path.exists(),
        "phase1_plan_status": phase1_plan.get("status", "missing_or_unavailable"),
        "selected_sequence_from_phase1": selected_sequence,
        "safety_doctrine": config.get("safety_doctrine", {}),
        "summary": {
            "phases_reviewed": len(phase_records),
            "selected_by_phase1_router": selected_count,
            "readiness_counts": dict(sorted(readiness_counts.items())),
            "configured_state_counts": dict(sorted(configured_counts.items())),
            "external_action_performed": False,
            "physical_file_moves_performed": False,
            "source_rewrites_performed": False,
            "workflow_rewrites_performed": False,
            "credential_use_performed": False,
            "secret_values_logged": False,
        },
        "phase_records": phase_records,
    }


def extract_selected_sequence(phase1_plan: Dict[str, Any]) -> List[str]:
    for key in ["selected_sequence", "planned_sequence", "recommended_sequence", "execution_sequence"]:
        value = phase1_plan.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
    plan = phase1_plan.get("plan")
    if isinstance(plan, dict):
        value = plan.get("selected_sequence") or plan.get("planned_sequence") or plan.get("recommended_sequence")
        if isinstance(value, list):
            return [str(item) for item in value]
    return []


def infer_artifact_paths(root: Path, phase_id: str) -> List[str]:
    mapping = {
        "phase2": ["data/phase2_processed/aigc_phase2_opportunity_queue.json"],
        "phase3": ["data/phase3_processed/aigc_phase3_assessment_dossiers.json"],
        "phase4": ["data/phase4_proposals/aigc_phase4_proposal_packages.json"],
        "phase5": ["data/phase5_authorizations/aigc_phase5_authorization_packets.json"],
        "phase6": ["data/phase6_execution/aigc_phase6_execution_receipts.json"],
        "phase7": ["data/phase7_audit_packets/aigc_phase7_employer_audit_packets.json"],
        "phase8": ["data/phase8_evolution/evolution_patches.jsonl"],
        "phase9": [],
        "phase10": ["data/phase10_connectors/aigc_phase10_connector_registry.json"],
        "phase11": ["data/reports/phase11_signature_update.md"],
        "phase12": ["data/phase12_observability/system_snapshot.json"],
        "phase13": ["data/phase13_simulation/synthetic_simulation_result.json"],
        "phase14": ["reports/phase14_runtime_preflight.md"],
        "phase15": ["data/phase15_finance/aigc_phase15_finance_ledger.json"],
        "phase16": ["data/phase16_compliance/aigc_phase16_compliance_reviews.json"],
        "phase17": ["data/phase17_incidents/incident_reports.jsonl"],
        "phase18": ["data/phase18_productization/aigc_phase18_release_readiness.json"],
        "phase19": ["data/phase19_subagents/aigc_phase19_subagent_team_plans.json"],
        "phase20": ["data/phase20_fidelity/aigc_phase20_fidelity_reviews.json"],
        "phase21": ["data/phase21_customer_satisfaction/aigc_phase21_customer_satisfaction_records.json"],
        "phase22": ["data/phase22_quality/aigc_phase22_quality_kernel_records.json"],
        "phase23": ["data/phase23_work_orders/aigc_phase23_work_order_governance_records.json"],
        "phase24": ["data/phase24_business_pipeline/aigc_phase24_business_pipeline_records.json"],
    }
    return mapping.get(phase_id, [])


def determine_readiness(phase_id: str, configured_state: str, selected: bool, missing_artifacts: List[str]) -> str:
    if configured_state == "reserved_planned_slot":
        return "reserved_not_executable"
    if "approval" in configured_state:
        return "approval_required"
    if configured_state in {"read_only_candidate", "internal_governance_candidate", "security_check_candidate", "observability_candidate", "simulation_candidate", "preflight_candidate", "internal_release_readiness_candidate", "operator_event_candidate"}:
        return "explicit_run_candidate"
    if selected and missing_artifacts:
        return "selected_but_dependency_missing"
    if selected:
        return "selected_dependency_available_or_not_required"
    if missing_artifacts:
        return "not_selected_dependency_missing"
    return "not_selected_dependency_available"


def render_report(plan: Dict[str, Any]) -> str:
    summary = plan["summary"]
    readiness_lines = render_counter(summary.get("readiness_counts", {}))
    configured_lines = render_counter(summary.get("configured_state_counts", {}))
    records_lines = "\n".join(
        f"- `{record['phase_id']}` / slot {record['slot']}: {record['readiness_state']} — {record['reason']}"
        for record in plan.get("phase_records", [])
    ) or "- None"
    selected_lines = render_list(plan.get("selected_sequence_from_phase1", []))

    return f"""# AIGC Phase 2-24 Continuity Report

Generated At: {plan['generated_at']}

Status: {plan['status']}

Input Router Config Found: {plan['input_router_config_found']}

Input Phase 1 Plan Found: {plan['input_phase1_plan_found']}

## Purpose

This report fills the middle of the AIGC pipeline. It makes phases 2 through 24 visible, ordered, and dependency-aware before Phase 25 and Phase 26 run.

## Summary

- Phases reviewed: {summary['phases_reviewed']}
- Selected by Phase 1 router: {summary['selected_by_phase1_router']}
- External action performed: No
- Physical file moves performed: No
- Source rewrites performed: No
- Workflow rewrites performed: No
- Credential use performed: No
- Secret values logged: No

## Phase 1 Selected Sequence

{selected_lines}

## Readiness Counts

{readiness_lines}

## Configured State Counts

{configured_lines}

## Phase Records

{records_lines}

## Operating Rule

The continuity bridge does not execute phases 2-24. It decides and records whether each phase is ready, dependency-gated, approval-gated, reserved, or explicit-run candidate. Execution remains controlled by future reviewed pipeline stages.
"""


def render_counter(counter: Dict[str, int]) -> str:
    if not counter:
        return "- None"
    return "\n".join(f"- `{key}`: {value}" for key, value in sorted(counter.items()))


def render_list(items: List[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- `{item}`" for item in items)


def write_outputs(root: Path, config: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    plan_path = resolve_path(root, config.get("output_plan", "data/phase2_24_continuity/aigc_phase2_24_continuity_plan.json"))
    report_path = resolve_path(root, config.get("output_report", "reports/phase2_24_continuity_report.md"))
    audit_path = resolve_path(root, config.get("audit_log", "data/audit/aigc_phase2_24_continuity_audit.jsonl"))

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(plan), encoding="utf-8")

    audit_record = {
        "event_id": f"AIGC-P2-24-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": plan["generated_at"],
        "phase": PHASE_NAME,
        "status": plan["status"],
        "phases_reviewed": plan["summary"]["phases_reviewed"],
        "external_action_performed": False,
        "physical_file_moves_performed": False,
        "source_rewrites_performed": False,
        "workflow_rewrites_performed": False,
        "credential_use_performed": False,
        "secret_values_logged": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_record, ensure_ascii=False) + "\n")

    return plan_path, report_path, audit_path


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC Phase 2-24 cognitive continuity bridge.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config = load_config(root, args.config)
    plan = build_continuity_plan(root, config)
    plan_path, report_path, audit_path = write_outputs(root, config, plan)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": plan["status"],
        "phases_reviewed": plan["summary"]["phases_reviewed"],
        "plan_path": str(plan_path),
        "report_path": str(report_path),
        "audit_path": str(audit_path),
        "external_action_performed": False,
        "physical_file_moves_performed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
