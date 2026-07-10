from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.core.contract_validator import validate_artifact, validate_file


DOCTRINE_SCHEMA = "agent_operating_doctrine"
REPORT_SCHEMA = "agent_operating_doctrine_report"

REQUIRED_HARD_BLOCKS = {
    "raw_secret_logging",
    "raw_chatlog_sharing_by_default",
    "whole_account_access",
    "backend_access",
    "self_approval",
    "fabricated_credentials",
    "platform_rule_bypass",
    "unverified_observer_access",
    "unreviewed_external_delivery",
    "live_external_execution_without_future_connector_pr",
}

REQUIRED_AGENT_ROLES = {"researcher", "communicator", "reasoner", "sentinel", "operator_cockpit"}


class AgentOperatingDoctrineError(ValueError):
    """Raised when the agent doctrine would weaken AIGC governance."""


def load_doctrine(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AgentOperatingDoctrineError(f"Expected JSON object doctrine at {path}")
    validate_artifact(DOCTRINE_SCHEMA, payload)
    validate_doctrine(payload)
    return payload


def validate_doctrine(doctrine: Dict[str, Any]) -> None:
    if doctrine.get("external_action_performed") is not False:
        raise AgentOperatingDoctrineError("external_action_performed must remain false in doctrine.")

    dependency_policy = dict(doctrine.get("dependency_policy", {}))
    if dependency_policy.get("operator_runs_installation") is not True:
        raise AgentOperatingDoctrineError("dependency_policy.operator_runs_installation must be true.")
    if dependency_policy.get("no_runtime_dependency_download_inside_agents") is not True:
        raise AgentOperatingDoctrineError("agents must not download dependencies at runtime.")

    gate = dict(doctrine.get("mandatory_gate", {}))
    if gate.get("external_action_performed_default") is not False:
        raise AgentOperatingDoctrineError("mandatory gate must default external_action_performed to false.")
    if gate.get("receipt_required") is not True:
        raise AgentOperatingDoctrineError("mandatory gate must require receipts.")
    if "security_privacy_wiring_cli.py" not in str(gate.get("cli", "")):
        raise AgentOperatingDoctrineError("mandatory gate must reference the Security & Privacy Wiring Gate CLI.")

    role_ids = {str(role.get("role_id", "")) for role in doctrine.get("agent_roles", []) if isinstance(role, dict)}
    missing_roles = sorted(REQUIRED_AGENT_ROLES - role_ids)
    if missing_roles:
        raise AgentOperatingDoctrineError(f"Missing required agent roles: {missing_roles}")

    hard_blocks = {str(item) for item in doctrine.get("hard_blocks", [])}
    missing_blocks = sorted(REQUIRED_HARD_BLOCKS - hard_blocks)
    if missing_blocks:
        raise AgentOperatingDoctrineError(f"Missing required hard blocks: {missing_blocks}")

    for role in doctrine.get("agent_roles", []):
        if not isinstance(role, dict):
            raise AgentOperatingDoctrineError("agent_roles entries must be objects.")
        for key in ["role_id", "name", "mission", "must_do", "must_not_do"]:
            if role.get(key) in (None, "", [], {}):
                raise AgentOperatingDoctrineError(f"agent role {role.get('role_id', '<unknown>')} missing {key}")


def build_agent_doctrine_report(doctrine: Dict[str, Any]) -> Dict[str, Any]:
    validate_doctrine(doctrine)
    job_cards: List[Dict[str, Any]] = []
    for role in doctrine.get("agent_roles", []):
        job_cards.append(
            {
                "role_id": role.get("role_id", ""),
                "name": role.get("name", ""),
                "mission": role.get("mission", ""),
                "must_do": list(role.get("must_do", [])),
                "must_not_do": list(role.get("must_not_do", [])),
                "mandatory_gate": doctrine.get("mandatory_gate", {}).get("name", "Security & Privacy Wiring Gate"),
                "external_action_performed": False,
            }
        )

    report = {
        "report_id": make_id("AIGC-AGENT-DOCTRINE", doctrine.get("doctrine_id", ""), utc_now()),
        "created_at": utc_now(),
        "doctrine_id": doctrine.get("doctrine_id", ""),
        "decision_state": "agent_doctrine_ready_for_operator_review",
        "dependency_install_command": doctrine.get("dependency_policy", {}).get("primary_install_command", "python -m pip install -r requirements.txt"),
        "mandatory_gate": doctrine.get("mandatory_gate", {}),
        "agent_job_cards": job_cards,
        "disabled_capabilities": list(doctrine.get("hard_blocks", [])),
        "reports_written": [],
        "external_action_performed": False,
    }
    validate_artifact(REPORT_SCHEMA, report)
    return report


def run_agent_operating_doctrine(
    project_root: Path,
    doctrine_path: Path | None = None,
    artifact_root: Path | None = None,
) -> Dict[str, Any]:
    root = project_root.resolve()
    doctrine_path = doctrine_path or root / "config" / "agent_operating_doctrine.json"
    artifact_root = artifact_root or root / "reports" / "artifacts" / "agent_operating_doctrine"

    doctrine = load_doctrine(doctrine_path)
    validate_file(DOCTRINE_SCHEMA, doctrine_path)
    report = build_agent_doctrine_report(doctrine)

    run_root = artifact_root / safe_path_name(report["report_id"])
    run_root.mkdir(parents=True, exist_ok=True)
    report_json = run_root / "agent_operating_doctrine_report.json"
    report_md = run_root / "agent_operating_doctrine_report.md"
    write_json(report_json, report)
    report["reports_written"] = [relative_to_root(root, report_json), relative_to_root(root, report_md)]
    write_json(report_json, report)
    validate_file(REPORT_SCHEMA, report_json)
    report_md.write_text(render_report(report), encoding="utf-8")

    return {
        "report": report,
        "report_path": relative_to_root(root, report_json),
        "markdown_report_path": relative_to_root(root, report_md),
        "external_action_performed": False,
    }


def render_report(report: Dict[str, Any]) -> str:
    lines = [
        "# AIGC Agent Operating Doctrine Report",
        "",
        f"Report ID: {report['report_id']}",
        f"Created At: {report['created_at']}",
        f"Decision State: {report['decision_state']}",
        f"Dependency Install Command: `{report['dependency_install_command']}`",
        "External Action Performed: No",
        "",
        "## Mandatory Gate",
        f"- Name: {report.get('mandatory_gate', {}).get('name', '')}",
        f"- CLI: `{report.get('mandatory_gate', {}).get('cli', '')}`",
        f"- Receipt required: {report.get('mandatory_gate', {}).get('receipt_required')}",
        "",
        "## Agent Job Cards",
    ]
    for card in report.get("agent_job_cards", []):
        lines.extend([
            f"### {card.get('name', '')}",
            f"Role ID: `{card.get('role_id', '')}`",
            "",
            f"Mission: {card.get('mission', '')}",
            "",
            "Must do:",
            *[f"- {item}" for item in card.get("must_do", [])],
            "",
            "Must not do:",
            *[f"- {item}" for item in card.get("must_not_do", [])],
            "",
        ])
    lines.extend([
        "## Disabled Capabilities",
        *[f"- {item}" for item in report.get("disabled_capabilities", [])],
        "",
        "## Operator Rule",
        "Agents assist, prepare, validate, and report. They do not self-approve or execute external actions.",
    ])
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
