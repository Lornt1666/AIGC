from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_google_workspace_secret_manager_procurement.json"
PHASE_NAME = "google_workspace_secret_manager_procurement"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_packet(config: Dict[str, Any]) -> Dict[str, Any]:
    secret_refs = config.get("secret_references", [])
    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "completed_secret_manager_procurement_plan",
        "trigger": config.get("trigger", {}),
        "google_workspace_identity": config.get("google_workspace_identity", {}),
        "secret_manager_project": config.get("secret_manager_project", {}),
        "gmail_api_scopes": config.get("gmail_api_scopes", {}),
        "secret_references": secret_refs,
        "command_plan": config.get("command_plan", []),
        "safety_doctrine": config.get("safety_doctrine", {}),
        "summary": {
            "secret_references_planned": len(secret_refs),
            "raw_secret_values_written": False,
            "raw_secret_values_logged": False,
            "credential_use_performed": False,
            "google_cloud_mutation_performed": False,
            "external_action_performed": False,
            "human_review_required_before_submission": True,
        },
    }


def render_report(packet: Dict[str, Any]) -> str:
    secret_lines = "\n".join(
        f"- `{item.get('name')}`: {item.get('purpose')}"
        for item in packet.get("secret_references", [])
    ) or "- None"
    command_lines = "\n".join(f"- `{cmd}`" for cmd in packet.get("command_plan", [])) or "- None"
    scopes = packet.get("gmail_api_scopes", {})
    scope_lines = "\n".join(f"- `{scope}`" for scope in scopes.get("minimum_initial_scopes", [])) or "- None"
    return f"""# AIGC Google Workspace Secret Manager Procurement Report

Generated At: {packet['generated_at']}

Status: {packet['status']}

## Purpose

This stage prepares a Google Workspace and Google Secret Manager credential control plane for AIGC. It writes references, command plans, and audit metadata only. It does not create secrets, reveal secrets, use credentials, or mutate Google Cloud from this environment.

## Planned Secret References

{secret_lines}

## Minimum Gmail Scopes

{scope_lines}

## Command Plan

{command_lines}

## Safety Result

- Raw secret values written: `false`
- Raw secret values logged: `false`
- Credential use performed: `false`
- Google Cloud mutation performed: `false`
- External action performed: `false`

## Operating Rule

Store secrets in Google Secret Manager. Store only `gcp_secret://...` references in AIGC artifacts. Use least privilege, secret-level IAM where possible, audit logging, and rotation.
"""


def write_outputs(root: Path, config: Dict[str, Any], packet: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("outputs", {})
    packet_path = resolve_path(root, outputs.get("packet", "data/google_workspace_secret_manager/aigc_google_workspace_secret_manager_procurement_packet.json"))
    report_path = resolve_path(root, outputs.get("report", "reports/google_workspace_secret_manager_procurement_report.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_google_workspace_secret_manager_procurement_audit.jsonl"))
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(packet), encoding="utf-8")
    audit = {
        "event_id": f"AIGC-GOOGLE-SECRETS-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": packet["generated_at"],
        "phase": PHASE_NAME,
        "status": packet["status"],
        "secret_references_planned": packet["summary"]["secret_references_planned"],
        "raw_secret_values_logged": False,
        "credential_use_performed": False,
        "google_cloud_mutation_performed": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit, ensure_ascii=False) + "\n")
    return packet_path, report_path, audit_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC Google Workspace Secret Manager procurement stage.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config = load_json(resolve_path(root, args.config))
    packet = build_packet(config)
    packet_path, report_path, audit_path = write_outputs(root, config, packet)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": packet["status"],
        "packet_path": str(packet_path),
        "report_path": str(report_path),
        "audit_path": str(audit_path),
        "raw_secret_values_logged": False,
        "credential_use_performed": False,
        "google_cloud_mutation_performed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
