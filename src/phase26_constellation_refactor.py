from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/phase26_constellation_refactor.json"
PHASE_NAME = "phase26_constellation_refactor"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_config(root: Path, config_path: str | None) -> Dict[str, Any]:
    if not config_path:
        return default_config()

    path = resolve_path(root, config_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Explicit Phase 26 configuration was not found: {path}"
        )
    return load_json(path)


def default_config() -> Dict[str, Any]:
    return {
        "input_manifest": "data/phase25_constellation/aigc_phase25_constellation_manifest.json",
        "output_plan": "data/phase26_constellation_refactor/aigc_phase26_refactor_plan.json",
        "output_report": "reports/phase26_constellation_refactor_report.md",
        "audit_log": "data/audit/aigc_phase26_audit.jsonl",
        "target_root": "constellation",
        "safety_doctrine": {
            "external_action_allowed": False,
            "physical_file_moves_allowed": False,
            "source_rewrite_allowed": False,
            "workflow_rewrite_allowed": False,
            "default_mode": "proposal_only",
        },
        "zone_target_paths": {},
        "retain_in_place_zones": ["01_CLOUD_TRIGGER_INGRESS", "06_DATA_MEMORY_LEDGER", "07_REPORTING_OBSERVABILITY"],
        "high_risk_prefixes": [".github/", "src/", "config/secret", "memory/", "data/", "reports/"],
        "import_sensitive_extensions": [".py"],
        "documentation_sensitive_extensions": [".md", ".rst", ".txt"],
        "workflow_sensitive_paths": [".github/workflows/"],
        "planning_agents": [],
        "promotion_rule": "Separate human-reviewed PR required for physical movement.",
    }


def build_plan(root: Path, config: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
    source_files = manifest.get("files", [])
    if not isinstance(source_files, list):
        source_files = []

    proposals = [build_proposal(item, config) for item in source_files if isinstance(item, dict)]
    status = "completed_proposal_only"
    action_counts = Counter(proposal["proposed_action"] for proposal in proposals)
    risk_counts = Counter(proposal["risk_level"] for proposal in proposals)
    zone_counts = Counter(proposal["constellation_zone"] for proposal in proposals)
    blocker_counts = Counter(blocker for proposal in proposals for blocker in proposal.get("blockers", []))

    physical_move_candidates = [
        proposal for proposal in proposals if proposal["proposed_action"] == "move_candidate_after_review"
    ]
    blocked_or_retained = [
        proposal for proposal in proposals if proposal["proposed_action"] != "move_candidate_after_review"
    ]

    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": status,
        "input_manifest_path": config.get("input_manifest", ""),
        "input_manifest_generated_at": manifest.get("generated_at", ""),
        "input_manifest_status": manifest.get("status", ""),
        "safety_doctrine": config.get("safety_doctrine", {}),
        "promotion_rule": config.get("promotion_rule", "Separate human-reviewed PR required."),
        "summary": {
            "source_files_reviewed": len(source_files),
            "proposals_created": len(proposals),
            "physical_moves_performed": False,
            "source_rewrites_performed": False,
            "workflow_rewrites_performed": False,
            "external_action_performed": False,
            "raw_secret_values_accessed": False,
            "move_candidates_after_review": len(physical_move_candidates),
            "blocked_or_retained": len(blocked_or_retained),
            "action_counts": dict(sorted(action_counts.items())),
            "risk_counts": dict(sorted(risk_counts.items())),
            "zone_counts": dict(sorted(zone_counts.items())),
            "blocker_counts": dict(sorted(blocker_counts.items())),
        },
        "planning_agents": config.get("planning_agents", []),
        "proposals": proposals,
    }


def build_proposal(file_record: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    source_path = str(file_record.get("path", ""))
    extension = str(file_record.get("extension", ""))
    zone = str(file_record.get("constellation_zone", "99_UNCLASSIFIED_SUPPORT"))
    zone_targets = config.get("zone_target_paths", {})
    zone_root = zone_targets.get(zone, f"{config.get('target_root', 'constellation')}/{zone.lower()}")
    proposed_target_path = f"{zone_root}/{source_path}".replace("//", "/")

    retain_zones = set(config.get("retain_in_place_zones", []))
    high_risk_prefixes = [str(value) for value in config.get("high_risk_prefixes", [])]
    workflow_prefixes = [str(value) for value in config.get("workflow_sensitive_paths", [])]
    import_sensitive_extensions = set(config.get("import_sensitive_extensions", []))
    documentation_sensitive_extensions = set(config.get("documentation_sensitive_extensions", []))

    workflow_sensitive = any(source_path.startswith(prefix) for prefix in workflow_prefixes)
    high_risk_prefix = next((prefix for prefix in high_risk_prefixes if source_path.startswith(prefix)), "")
    import_sensitive = extension in import_sensitive_extensions
    documentation_sensitive = extension in documentation_sensitive_extensions
    secret_adjacent = any(token in source_path.lower() for token in ["secret", "credential", "token", "key"])
    generated_artifact = source_path.startswith("data/") or source_path.startswith("reports/") or source_path.startswith("memory/")

    blockers: List[str] = []
    if workflow_sensitive:
        blockers.append("workflow_path_rewrite_required")
    if import_sensitive:
        blockers.append("python_import_rewrite_required")
    if documentation_sensitive:
        blockers.append("documentation_link_review_required")
    if secret_adjacent:
        blockers.append("secret_or_token_adjacent_manual_review_required")
    if generated_artifact:
        blockers.append("generated_artifact_lineage_review_required")
    if zone in retain_zones:
        blockers.append("zone_configured_retain_in_place")
    if high_risk_prefix:
        blockers.append(f"high_risk_prefix:{high_risk_prefix}")
    if zone == "99_UNCLASSIFIED_SUPPORT":
        blockers.append("unclassified_zone_manual_review_required")

    if zone in retain_zones or generated_artifact or workflow_sensitive:
        proposed_action = "retain_in_place_with_constellation_metadata"
    elif blockers:
        proposed_action = "blocked_until_dependency_review"
    else:
        proposed_action = "move_candidate_after_review"

    risk_level = "low"
    if workflow_sensitive or secret_adjacent:
        risk_level = "critical"
    elif import_sensitive or source_path.startswith("src/") or source_path.startswith("config/"):
        risk_level = "high"
    elif generated_artifact or documentation_sensitive or blockers:
        risk_level = "medium"

    return {
        "proposal_id": f"AIGC-P26-{stable_id(source_path)}",
        "source_path": source_path,
        "proposed_target_path": proposed_target_path,
        "constellation_zone": zone,
        "ontology": file_record.get("ontology", ""),
        "taxonomy": file_record.get("taxonomy", ""),
        "methodology": file_record.get("methodology", ""),
        "agent_lane": file_record.get("agent_lane", ""),
        "risk_class": file_record.get("risk_class", ""),
        "risk_level": risk_level,
        "proposed_action": proposed_action,
        "blockers": blockers,
        "requires_human_approval": True,
        "requires_import_review": import_sensitive,
        "requires_workflow_review": workflow_sensitive,
        "requires_documentation_review": documentation_sensitive,
        "requires_secret_boundary_review": secret_adjacent,
        "physical_move_performed": False,
    }


def render_report(plan: Dict[str, Any]) -> str:
    summary = plan["summary"]
    action_lines = render_counter(summary.get("action_counts", {}))
    risk_lines = render_counter(summary.get("risk_counts", {}))
    zone_lines = render_counter(summary.get("zone_counts", {}))
    blocker_lines = render_counter(summary.get("blocker_counts", {}))
    agent_lines = "\n".join(
        f"- `{agent.get('id', 'unknown')}`: {agent.get('responsibility', '')}"
        for agent in plan.get("planning_agents", [])
        if isinstance(agent, dict)
    ) or "- None"

    return f"""# AIGC Phase 26 Constellation Refactor Plan

Generated At: {plan['generated_at']}

Status: {plan['status']}

Input Manifest Generated At: {plan.get('input_manifest_generated_at', '')}

External Action Performed: No

Physical File Moves Performed: No

Source Rewrites Performed: No

Workflow Rewrites Performed: No

## Purpose

Phase 26 converts the Phase 25 constellation map into a responsible refactor proposal. It does not move files. It identifies what could move, what should remain in place, and what requires dependency, workflow, documentation, or security review first.

## Summary

- Source files reviewed: {summary['source_files_reviewed']}
- Proposals created: {summary['proposals_created']}
- Move candidates after review: {summary['move_candidates_after_review']}
- Blocked or retained: {summary['blocked_or_retained']}

## Action Counts

{action_lines}

## Risk Counts

{risk_lines}

## Zone Counts

{zone_lines}

## Blocker Counts

{blocker_lines}

## Planning Agents

{agent_lines}

## Promotion Rule

{plan.get('promotion_rule', 'Separate human-reviewed PR required for physical movement.')}

## Safety Boundary

This run is proposal-only. It writes `data/phase26_constellation_refactor/aigc_phase26_refactor_plan.json`, `reports/phase26_constellation_refactor_report.md`, and `data/audit/aigc_phase26_audit.jsonl` only. It does not move files, rewrite imports, edit workflows, commit generated outputs, use credentials, contact services, or bypass approval gates.
"""


def render_counter(counter: Dict[str, int]) -> str:
    if not counter:
        return "- None"
    return "\n".join(f"- `{key}`: {value}" for key, value in sorted(counter.items()))


def write_outputs(root: Path, config: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    plan_path = resolve_path(root, config.get("output_plan", "data/phase26_constellation_refactor/aigc_phase26_refactor_plan.json"))
    report_path = resolve_path(root, config.get("output_report", "reports/phase26_constellation_refactor_report.md"))
    audit_path = resolve_path(root, config.get("audit_log", "data/audit/aigc_phase26_audit.jsonl"))

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(plan), encoding="utf-8")

    audit_record = {
        "event_id": f"AIGC-P26-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": plan["generated_at"],
        "phase": PHASE_NAME,
        "status": plan["status"],
        "source_files_reviewed": plan["summary"]["source_files_reviewed"],
        "proposals_created": plan["summary"]["proposals_created"],
        "physical_moves_performed": False,
        "external_action_performed": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_record, ensure_ascii=False) + "\n")

    return plan_path, report_path, audit_path


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC Phase 26 constellation refactor planner.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--manifest", default="")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()

    try:
        config = load_config(root, args.config)
    except FileNotFoundError as exc:
        print(json.dumps({
            "phase": PHASE_NAME,
            "status": "blocked_missing_explicit_configuration",
            "missing_config_path": str(resolve_path(root, args.config)),
            "error": str(exc),
            "physical_moves_performed": False,
            "external_action_performed": False,
        }, indent=2))
        return 2

    manifest_path = resolve_path(root, args.manifest or config.get("input_manifest", ""))

    if not manifest_path.exists():
        print(json.dumps({
            "phase": PHASE_NAME,
            "status": "blocked_missing_phase25_manifest",
            "missing_manifest_path": str(manifest_path),
            "next_action": "Run `python .\\src\\aigc.py run phase25` first, then rerun phase26.",
            "physical_moves_performed": False,
            "external_action_performed": False,
        }, indent=2))
        return 2

    manifest = load_json(manifest_path)
    plan = build_plan(root, config, manifest)
    plan_path, report_path, audit_path = write_outputs(root, config, plan)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": plan["status"],
        "source_files_reviewed": plan["summary"]["source_files_reviewed"],
        "proposals_created": plan["summary"]["proposals_created"],
        "plan_path": str(plan_path),
        "report_path": str(report_path),
        "audit_path": str(audit_path),
        "physical_moves_performed": False,
        "external_action_performed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
