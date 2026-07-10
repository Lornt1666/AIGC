from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.core.contract_validator import validate_artifact, validate_file


PROFILE_SCHEMA = "sentinel_security_profile"
REPORT_SCHEMA = "sentinel_security_report"


class SentinelSecurityError(ValueError):
    """Raised when the Sentinel profile would weaken security or privacy."""


def load_profile(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SentinelSecurityError(f"Expected JSON object at {path}")
    validate_artifact(PROFILE_SCHEMA, payload)
    validate_profile(payload)
    return payload


def validate_profile(profile: Dict[str, Any]) -> None:
    disclosure = dict(profile.get("authorized_disclosure_boundary", {}))
    required_true = [
        "no_backdoor",
        "operator_review_required",
        "jurisdiction_review_required",
        "share_minimum_necessary",
        "audit_receipt_required",
    ]
    for key in required_true:
        if disclosure.get(key) is not True:
            raise SentinelSecurityError(f"authorized_disclosure_boundary.{key} must be true")
    blocked = set(profile.get("blocked_capabilities", []))
    required_blocks = {
        "offensive_exploit_generation",
        "malware_or_credential_theft",
        "backdoor_or_unrestricted_government_access",
        "silent_external_sharing",
        "raw_secret_logging",
        "raw_chatlog_share_by_default",
        "agent_self_approval",
    }
    missing = sorted(required_blocks - blocked)
    if missing:
        raise SentinelSecurityError(f"Missing required blocked capabilities: {missing}")
    assignment = dict(profile.get("repo_assignment", {}))
    assignment_true = [
        "all_security_sensitive_outputs_require_schema",
        "all_external_actions_require_operator_approval",
        "all_counterparty_visibility_requires_redaction_review",
        "all_future_secret_access_requires_secret_broker",
        "all_prs_require_CI_before_merge",
    ]
    for key in assignment_true:
        if assignment.get(key) is not True:
            raise SentinelSecurityError(f"repo_assignment.{key} must be true")


def build_sentinel_report(profile: Dict[str, Any]) -> Dict[str, Any]:
    validate_profile(profile)
    controls: List[Dict[str, Any]] = list(profile.get("control_families", []))
    layers: List[Dict[str, Any]] = list(profile.get("layer_model", []))
    report = {
        "report_id": make_id("AIGC-SENTINEL-REPORT", profile.get("profile_id", ""), utc_now()),
        "generated_at": utc_now(),
        "profile_id": profile.get("profile_id", ""),
        "overall_status": "defensive_profile_ready_for_operator_review",
        "layer_count": len(layers),
        "control_count": sum(len(item.get("controls", [])) for item in controls if isinstance(item, dict)),
        "repo_assignment": profile.get("repo_assignment", {}),
        "blocked_capabilities": profile.get("blocked_capabilities", []),
        "authorized_disclosure_boundary": profile.get("authorized_disclosure_boundary", {}),
    }
    validate_artifact(REPORT_SCHEMA, report)
    return report


def run_sentinel_security_profile(
    project_root: Path,
    profile_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    root = project_root.resolve()
    profile_path = profile_path or root / "config" / "sentinel_security_profile.json"
    artifact_root = artifact_root or root / "reports" / "artifacts" / "sentinel_security"
    profile = load_profile(profile_path)
    report = build_sentinel_report(profile)
    output_root = artifact_root / safe_path_name(report["report_id"])
    output_root.mkdir(parents=True, exist_ok=True)
    profile_copy_path = output_root / "sentinel_security_profile.json"
    report_path = output_root / "sentinel_security_report.json"
    markdown_path = output_root / "sentinel_security_report.md"
    write_json(profile_copy_path, profile)
    write_json(report_path, report)
    validate_file(PROFILE_SCHEMA, profile_copy_path)
    validate_file(REPORT_SCHEMA, report_path)
    markdown_path.write_text(render_report(profile, report), encoding="utf-8")
    return {
        "profile": profile,
        "report": report,
        "profile_path": relative_to_root(root, profile_copy_path),
        "report_path": relative_to_root(root, report_path),
        "markdown_path": relative_to_root(root, markdown_path),
        "external_action_performed": False,
    }


def render_report(profile: Dict[str, Any], report: Dict[str, Any]) -> str:
    lines = [
        "# AIGC Sentinel Security Profile Report",
        "",
        f"Report ID: {report['report_id']}",
        f"Generated At: {report['generated_at']}",
        f"Profile ID: {report['profile_id']}",
        f"Status: {report['overall_status']}",
        "",
        "## Layer Model",
    ]
    for layer in profile.get("layer_model", []):
        lines.extend([
            f"### {layer.get('name', layer.get('layer_id', 'layer'))}",
            f"- Purpose: {layer.get('purpose', '')}",
            "- Controls:",
            *[f"  - {control}" for control in layer.get("controls", [])],
            "",
        ])
    lines.extend([
        "## Authorized Disclosure Boundary",
        "- No unrestricted backdoor access.",
        "- Evidence export only after operator and jurisdiction review.",
        "- Share the minimum necessary information.",
        "- Write an audit receipt for every disclosure packet.",
        "",
        "## Blocked Capabilities",
    ])
    lines.extend(f"- {item}" for item in report.get("blocked_capabilities", []))
    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
