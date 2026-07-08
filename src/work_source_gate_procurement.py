from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_work_source_gate_catalog.json"
PHASE_NAME = "work_source_gate_procurement"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def gate_record(source: Dict[str, Any], template: Dict[str, str]) -> Dict[str, Any]:
    source_id = source.get("id", "unknown_source")
    access_mode = source.get("access_mode", template.get("source_access_mode_classification"))
    connector_status = source.get("connector_status", "review_required")
    submission_requires_review = "submission_requires" in str(source.get("automation_status", "")) or "manual" in str(access_mode)
    return {
        "source_id": source_id,
        "name": source.get("name", source_id),
        "category": source.get("category", "uncategorized"),
        "base_url": source.get("base_url", ""),
        "source_terms_review": {
            "status": template.get("source_terms_review"),
            "target": source.get("terms_review_target", "official terms and legal policy review required"),
            "live_use_blocked_until_review": True,
        },
        "source_access_mode_classification": {
            "mode": access_mode,
            "classification": source.get("access_mode", template.get("source_access_mode_classification")),
            "read_only_discovery_allowed": True,
            "submission_requires_operator_proceed": True,
        },
        "robots_or_api_policy_check_when_applicable": {
            "status": template.get("robots_or_api_policy_check_when_applicable"),
            "robots_url": source.get("robots_url", "per_site"),
            "api_or_feed": source.get("api_or_feed", "none_assumed"),
            "crawl_or_api_use_blocked_until_review": True,
        },
        "connector_allowlist": {
            "status": connector_status,
            "allowlisted_for_read_only_discovery": connector_status in {"read_only_candidate"},
            "allowlisted_for_submission": False,
            "live_connector_activation_requires_review": True,
        },
        "secret_reference_manifest": {
            "status": template.get("secret_reference_manifest"),
            "required_refs": [
                f"gcp_secret://AIGC_SOURCE_{source_id.upper()}_CONNECTOR_TOKEN/latest",
                f"gcp_secret://AIGC_SOURCE_{source_id.upper()}_ACCOUNT_REF/latest",
            ],
            "raw_secret_values_allowed": False,
        },
        "approval_token_or_exact_phrase": {
            "status": template.get("approval_token_or_exact_phrase"),
            "required_phrase_for_submission": "PROCEED AIGC SUBMISSION",
            "human_review_required": True,
        },
        "dry_run_receipt": {
            "status": template.get("dry_run_receipt"),
            "required_before_live_action": True,
        },
        "idempotency_key": {
            "status": template.get("idempotency_key"),
            "format": f"AIGC-{source_id}-{{submission_id}}",
            "required_for_external_handoff": True,
        },
        "rate_limit_policy": {
            "status": template.get("rate_limit_policy"),
            "default_policy": "lowest_reasonable_frequency_read_only_until_platform_limits_are_confirmed",
            "respect_platform_limits": True,
        },
        "redaction_scan": {
            "status": template.get("redaction_scan"),
            "scan_before_log_or_display": True,
            "raw_secret_logging_allowed": False,
        },
        "audit_receipt": {
            "status": template.get("audit_receipt"),
            "required_for_every_action": True,
            "audit_event_prefix": f"AIGC-SOURCE-{source_id.upper()}",
        },
        "rollback_or_manual_handoff_path": {
            "status": template.get("rollback_or_manual_handoff_path"),
            "manual_handoff_default": True,
            "rollback_required_for_live_connector": True,
        },
        "summary": {
            "submission_requires_review": submission_requires_review,
            "terms_sensitive": connector_status in {"terms_sensitive", "account_sensitive", "identity_sensitive"},
            "external_action_performed": False,
            "credential_use_performed": False,
            "secret_values_logged": False,
        },
    }


def build_packet(config: Dict[str, Any]) -> Dict[str, Any]:
    template = config.get("default_gate_template", {})
    records = [gate_record(source, template) for source in config.get("sources", [])]
    categories = Counter(record.get("category", "uncategorized") for record in records)
    connector_statuses = Counter(record.get("connector_allowlist", {}).get("status", "unknown") for record in records)
    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "completed_per_source_gate_procurement",
        "purpose": config.get("purpose", ""),
        "default_gate_template": template,
        "sources_reviewed": records,
        "summary": {
            "source_count": len(records),
            "category_counts": dict(sorted(categories.items())),
            "connector_status_counts": dict(sorted(connector_statuses.items())),
            "external_action_performed": False,
            "credential_use_performed": False,
            "secret_values_logged": False,
            "raw_secret_logging_allowed": False,
            "unapproved_submission_allowed": False,
        },
    }


def render_report(packet: Dict[str, Any]) -> str:
    summary = packet["summary"]
    category_lines = "\n".join(f"- `{k}`: {v}" for k, v in summary.get("category_counts", {}).items()) or "- None"
    connector_lines = "\n".join(f"- `{k}`: {v}" for k, v in summary.get("connector_status_counts", {}).items()) or "- None"
    source_lines = "\n".join(
        f"- `{record['source_id']}` ({record['name']}): `{record['source_access_mode_classification']['classification']}` / `{record['connector_allowlist']['status']}`"
        for record in packet.get("sources_reviewed", [])
    ) or "- None"
    return f"""# AIGC Work Source Gate Procurement Report

Generated At: {packet['generated_at']}

Status: {packet['status']}

## Summary

- Sources reviewed: `{summary['source_count']}`
- External action performed: `false`
- Credential use performed: `false`
- Secret values logged: `false`
- Raw secret logging allowed: `false`
- Unapproved submission allowed: `false`

## Category Counts

{category_lines}

## Connector Status Counts

{connector_lines}

## Source Gate Index

{source_lines}

## Operating Rule

Each source has terms review, access-mode classification, robots/API review, connector allowlist, secret-reference manifest, approval phrase, dry-run receipt, idempotency key, rate-limit policy, redaction scan, audit receipt, and rollback/manual handoff path.
"""


def write_outputs(root: Path, config: Dict[str, Any], packet: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("outputs", {})
    packet_path = resolve_path(root, outputs.get("packet", "data/work_source_gates/aigc_work_source_gate_procurement_packet.json"))
    report_path = resolve_path(root, outputs.get("report", "reports/work_source_gate_procurement_report.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_work_source_gate_procurement_audit.jsonl"))
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(packet), encoding="utf-8")
    audit = {
        "event_id": f"AIGC-WORK-SOURCES-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": packet["generated_at"],
        "phase": PHASE_NAME,
        "status": packet["status"],
        "source_count": packet["summary"]["source_count"],
        "external_action_performed": False,
        "credential_use_performed": False,
        "secret_values_logged": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit, ensure_ascii=False) + "\n")
    return packet_path, report_path, audit_path


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC work source gate procurement stage.")
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
        "source_count": packet["summary"]["source_count"],
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
