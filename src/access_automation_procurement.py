from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_access_automation_procurement.json"
PHASE_NAME = "access_automation_procurement"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_domain_records(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = []
    for domain in config.get("hiring_and_work_source_domains", []):
        category = domain.get("category", "unknown")
        mode = domain.get("default_access_mode", "manual_review_required")
        requires_human = "submission" in domain.get("automation_status", "") or "manual" in mode or "account" in mode
        records.append(
            {
                "category": category,
                "purpose": domain.get("purpose", ""),
                "examples": domain.get("examples", []),
                "default_access_mode": mode,
                "automation_status": domain.get("automation_status", ""),
                "read_only_discovery_allowed": True,
                "credential_use_requires_secret_broker": True,
                "submission_requires_operator_proceed": True,
                "human_review_required": requires_human,
                "raw_secret_value_logging_allowed": False,
            }
        )
    return records


def build_packet(config: Dict[str, Any]) -> Dict[str, Any]:
    requested = config.get("human_in_loop_requested_capability_state", {})
    effective = config.get("effective_safety_parameters", {})
    domains = build_domain_records(config)
    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "completed_human_in_loop_access_procurement_plan",
        "trigger": config.get("trigger", {}),
        "human_in_loop_requested_capability_state": requested,
        "effective_safety_parameters": effective,
        "access_procurement_gates": config.get("access_procurement_gates", []),
        "domain_records": domains,
        "submission_activation_requirements": config.get("submission_activation_requirements", {}),
        "summary": {
            "requested_external_action_allowed": requested.get("external_action_allowed") is True,
            "requested_auto_submit_to_employer": requested.get("auto_submit_to_employer") is True,
            "requested_credential_use_allowed": requested.get("credential_use_allowed") is True,
            "requested_secret_value_logging_allowed": requested.get("secret_value_logging_allowed") is True,
            "requested_human_review_required_before_submission": requested.get("human_review_required_before_submission") is True,
            "requested_proceed_records_handoff_only": requested.get("proceed_records_handoff_only") is True,
            "domain_categories": len(domains),
            "domain_examples": sum(len(record.get("examples", [])) for record in domains),
            "raw_secret_value_logging_allowed": False,
            "credential_exfiltration_allowed": False,
            "unapproved_external_submission_allowed": False,
            "external_action_performed": False,
            "credential_use_performed": False,
            "secret_values_logged": False,
        },
    }


def render_report(packet: Dict[str, Any]) -> str:
    requested = packet.get("human_in_loop_requested_capability_state", {})
    effective = packet.get("effective_safety_parameters", {})
    domains = packet.get("domain_records", [])
    requested_lines = "\n".join(f"- `{k}`: `{str(v).lower()}`" for k, v in sorted(requested.items())) or "- None"
    effective_lines = "\n".join(f"- `{k}`: {v}" for k, v in sorted(effective.items())) or "- None"
    domain_lines = "\n".join(
        f"- `{record['category']}`: {record['default_access_mode']} — {record['automation_status']}"
        for record in domains
    ) or "- None"
    gate_lines = "\n".join(f"- {gate}" for gate in packet.get("access_procurement_gates", [])) or "- None"
    return f"""# AIGC Access Automation Procurement Report

Generated At: {packet['generated_at']}

Status: {packet['status']}

## Human-in-Loop Requested Capability State

{requested_lines}

## Effective Safety Parameters

{effective_lines}

## Hiring and Work Source Domains

{domain_lines}

## Access Procurement Gates

{gate_lines}

## Safety Result

- Raw secret value logging allowed: `false`
- Credential exfiltration allowed: `false`
- Unapproved external submission allowed: `false`
- External action performed: `false`
- Credential use performed: `false`
- Secret values logged: `false`

## Operating Meaning

The AIGC trigger can procure an access-automation plan with human-in-loop requested capabilities set to true. Effective use is conditional on the submission cockpit, connector allowlists, secret-reference-only access, audit receipts, rate limits, and redaction. Raw secret values are never logged.
"""


def write_outputs(root: Path, config: Dict[str, Any], packet: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("output_paths", {})
    packet_path = resolve_path(root, outputs.get("packet", "data/access_automation/aigc_access_automation_procurement_packet.json"))
    report_path = resolve_path(root, outputs.get("report", "reports/access_automation_procurement_report.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_access_automation_procurement_audit.jsonl"))
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(packet), encoding="utf-8")
    audit_record = {
        "event_id": f"AIGC-ACCESS-AUTOMATION-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": packet["generated_at"],
        "phase": PHASE_NAME,
        "status": packet["status"],
        "domain_categories": packet["summary"]["domain_categories"],
        "requested_external_action_allowed": packet["summary"]["requested_external_action_allowed"],
        "requested_auto_submit_to_employer": packet["summary"]["requested_auto_submit_to_employer"],
        "raw_secret_value_logging_allowed": False,
        "external_action_performed": False,
        "credential_use_performed": False,
        "secret_values_logged": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_record, ensure_ascii=False) + "\n")
    return packet_path, report_path, audit_path


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC access automation procurement stage.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config = load_json(resolve_path(root, args.config))
    packet = build_packet(config)
    packet_path, report_path, audit_path = write_outputs(root, config, packet)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": packet["status"],
        "domain_categories": packet["summary"]["domain_categories"],
        "packet_path": str(packet_path),
        "report_path": str(report_path),
        "audit_path": str(audit_path),
        "external_action_performed": False,
        "credential_use_performed": False,
        "secret_values_logged": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
