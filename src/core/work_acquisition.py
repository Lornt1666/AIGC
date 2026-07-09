from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.core.contract_validator import validate_artifact, validate_file


DOMAIN_REGISTRY_SCHEMA = "work_domain_registry"
ACQUISITION_PACKET_SCHEMA = "work_acquisition_packet"
PERFORMANCE_PACKET_SCHEMA = "work_performance_packet"

BLOCKED_ACTIONS = [
    "auto_apply",
    "auto_submit",
    "auto_accept",
    "auto_pay",
    "auto_purchase",
    "auto_deploy",
    "auto_bid",
    "auto_message",
    "credential_use_without_secret_broker",
    "secret_logging",
    "platform_rule_bypass",
    "self_approval",
    "fabricated_credentials",
]

SEARCH_STAGES = [
    "domain_registry_validation",
    "terms_and_allowed_mode_review",
    "read_only_search_plan",
    "opportunity_fit_scoring",
    "truthful_application_packet_drafting",
    "operator_review_queue",
    "manual_platform_commit_only",
]

PERFORMANCE_STANDARDS = [
    "clarify scope before work",
    "define acceptance criteria",
    "decompose into deliverables",
    "prepare evidence and source trail",
    "run quality gate before handoff",
    "surface uncertainty instead of pretending certainty",
    "operator review before external delivery",
]


class WorkAcquisitionError(ValueError):
    """Raised when work acquisition configuration violates AIGC governance."""


def run_work_acquisition(
    project_root: Path,
    registry_path: Path | None = None,
    profile_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    project_root = project_root.resolve()
    registry_path = resolve_project_path(project_root, registry_path or project_root / "config" / "work_domain_registry.json")
    profile_path = resolve_project_path(project_root, profile_path or project_root / "config" / "work_acquisition_profile.json")
    artifact_root = resolve_project_path(project_root, artifact_root or project_root / "reports" / "artifacts" / "work_acquisition")

    registry = load_json_dict(registry_path)
    profile = load_json_dict(profile_path)
    validate_artifact(DOMAIN_REGISTRY_SCHEMA, registry)
    validate_registry_constraints(registry)

    acquisition_packet = build_work_acquisition_packet(registry, profile)
    performance_packet = build_work_performance_packet(profile)

    run_root = artifact_root / safe_path_name(acquisition_packet["packet_id"])
    run_root.mkdir(parents=True, exist_ok=True)
    acquisition_path = run_root / "work_acquisition_packet.json"
    performance_path = run_root / "work_performance_packet.json"
    report_path = run_root / "work_acquisition_report.md"

    write_json(acquisition_path, acquisition_packet)
    write_json(performance_path, performance_packet)
    report_path.write_text(render_report(acquisition_packet, performance_packet), encoding="utf-8")

    validate_file(ACQUISITION_PACKET_SCHEMA, acquisition_path)
    validate_file(PERFORMANCE_PACKET_SCHEMA, performance_path)

    return {
        "acquisition_packet": acquisition_packet,
        "performance_packet": performance_packet,
        "acquisition_path": relative_to_root(project_root, acquisition_path),
        "performance_path": relative_to_root(project_root, performance_path),
        "report_path": relative_to_root(project_root, report_path),
        "external_action_performed": False,
    }


def build_work_acquisition_packet(registry: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    domains = list(registry.get("domains", []))
    search_domains = [build_domain_plan(domain, profile) for domain in domains]
    packet = {
        "packet_id": make_id("AIGC-WORK-ACQ", registry.get("registry_id", ""), profile.get("profile_id", ""), utc_now()),
        "created_at": utc_now(),
        "mode": "read_only_search_and_application_preparation_only",
        "domain_count": len(search_domains),
        "search_domains": search_domains,
        "application_prep_controls": {
            "truthful_profile_only": True,
            "draft_cover_letters": True,
            "draft_proposals": True,
            "draft_work_scopes": True,
            "draft_interview_notes": True,
            "operator_must_review_before_submit": True,
            "operator_must_click_apply_or_submit": True,
            "auto_submission_enabled": False,
        },
        "work_performance_controls": {
            "scope_first": True,
            "acceptance_criteria_required": True,
            "delivery_checklist_required": True,
            "quality_gate_required": True,
            "evidence_packet_required": True,
            "operator_review_before_delivery": True,
        },
        "blocked_actions": BLOCKED_ACTIONS,
        "external_action_performed": False,
    }
    validate_artifact(ACQUISITION_PACKET_SCHEMA, packet)
    return packet


def build_domain_plan(domain: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    allowed_actions = list(domain.get("allowed_actions", []))
    blocked_actions = list(dict.fromkeys(list(domain.get("blocked_actions", [])) + BLOCKED_ACTIONS))
    return {
        "domain_id": str(domain.get("domain_id", "unknown")),
        "name": str(domain.get("name", "Unknown domain")),
        "base_url": str(domain.get("base_url", "")),
        "source_mode": str(domain.get("source_mode", "manual_review_only")),
        "priority": int(domain.get("priority", 0) or 0),
        "search_stage_plan": SEARCH_STAGES,
        "target_work_types": list(profile.get("target_work_types", [])),
        "allowed_actions": allowed_actions,
        "blocked_actions": blocked_actions,
        "terms_review_required": bool(domain.get("terms_review_required", True)),
        "operator_commit_required": True,
        "external_action_performed": False,
    }


def build_work_performance_packet(profile: Dict[str, Any]) -> Dict[str, Any]:
    deliverables = []
    for index, work_type in enumerate(profile.get("target_work_types", []), start=1):
        deliverables.append({
            "deliverable_id": f"AIGC-DELIVERABLE-{index:03d}",
            "work_type": str(work_type),
            "scope_questions": [
                "What outcome does the client need?",
                "What files, links, constraints, and deadline define success?",
                "What does done mean in measurable terms?",
            ],
            "execution_steps": [
                "confirm scope",
                "create first-pass artifact",
                "self-audit against acceptance criteria",
                "revise for clarity and usefulness",
                "prepare evidence and handoff notes",
                "operator review before delivery",
            ],
            "quality_evidence": [
                "acceptance criteria checklist",
                "source or input trail",
                "known limitations",
                "revision log",
                "operator review status",
            ],
        })
    packet = {
        "packet_id": make_id("AIGC-WORK-PERF", profile.get("profile_id", ""), utc_now()),
        "created_at": utc_now(),
        "objective": "Help the operator execute paid work at a professional, reviewable, evidence-backed standard.",
        "role_profile": {
            "program_name": profile.get("program_name", "AIGC Operator Program"),
            "operator_name": profile.get("operator_name", "Operator"),
            "positioning": profile.get("positioning", "Governed AI operator workbench."),
            "skills": list(profile.get("skills", [])),
        },
        "execution_standards": PERFORMANCE_STANDARDS,
        "deliverable_workbench": deliverables,
        "quality_gates": [
            {"gate": "truthfulness", "required": True, "description": "Do not fabricate credentials, experience, sources, or completion state."},
            {"gate": "scope_fit", "required": True, "description": "Match deliverable to client need and acceptance criteria."},
            {"gate": "evidence", "required": True, "description": "Attach source trail, work notes, or verification evidence when applicable."},
            {"gate": "security", "required": True, "description": "No secrets, credentials, private data, or unauthorized access."},
            {"gate": "operator_review", "required": True, "description": "Operator reviews before external delivery."}
        ],
        "operator_review_required": True,
        "external_action_performed": False,
    }
    validate_artifact(PERFORMANCE_PACKET_SCHEMA, packet)
    return packet


def validate_registry_constraints(registry: Dict[str, Any]) -> None:
    constraints = dict(registry.get("global_constraints", {}))
    required_true = [
        "dry_run_by_default",
        "domain_allowlist_required",
        "no_login_by_default",
        "no_forms_by_default",
        "no_auto_apply",
        "no_auto_submit",
        "operator_review_required",
    ]
    for key in required_true:
        if not constraints.get(key, False):
            raise WorkAcquisitionError(f"Registry constraint must be true: {key}")
    if constraints.get("external_action_performed", True) is not False:
        raise WorkAcquisitionError("external_action_performed must remain false.")


def render_report(acquisition_packet: Dict[str, Any], performance_packet: Dict[str, Any]) -> str:
    lines = [
        "# AIGC Work Acquisition and Performance Packet",
        "",
        f"Generated At: {acquisition_packet['created_at']}",
        f"Acquisition Packet: {acquisition_packet['packet_id']}",
        f"Performance Packet: {performance_packet['packet_id']}",
        "External Action Performed: No",
        "",
        "## Domain Search Plan",
    ]
    for domain in sorted(acquisition_packet.get("search_domains", []), key=lambda item: item.get("priority", 0), reverse=True):
        lines.extend([
            f"### {domain['name']}",
            f"- Mode: {domain['source_mode']}",
            f"- Priority: {domain['priority']}",
            f"- Operator commit required: {domain['operator_commit_required']}",
            f"- Terms review required: {domain['terms_review_required']}",
            "",
        ])
    lines.extend([
        "## Application Preparation Controls",
        "- Draft applications, cover letters, proposals, scopes, and interview notes internally.",
        "- The operator manually applies/submits/sends on the official platform.",
        "- No fabricated credentials or experience.",
        "",
        "## Work Performance Controls",
    ])
    lines.extend(f"- {standard}" for standard in performance_packet.get("execution_standards", []))
    lines.extend([
        "",
        "## Blocked Actions",
    ])
    lines.extend(f"- {action}" for action in acquisition_packet.get("blocked_actions", []))
    return "\n".join(lines) + "\n"


def load_json_dict(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def relative_to_root(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def safe_path_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in str(value))[:96]


def make_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
