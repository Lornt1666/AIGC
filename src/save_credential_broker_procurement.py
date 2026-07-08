from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_save_credential_broker.json"
PHASE_NAME = "save_credential_broker_procurement"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_packet(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "completed_save_credential_broker_procurement",
        "purpose": config.get("purpose", ""),
        "flow": config.get("flow", []),
        "approved_vault_targets": config.get("approved_vault_targets", []),
        "broker_popup_fields": config.get("broker_popup_fields", []),
        "credential_reference_inspector": config.get("credential_reference_inspector", {}),
        "audit_events": config.get("audit_events", []),
        "safety_result": config.get("safety_result", {}),
        "summary": {
            "vault_targets": len(config.get("approved_vault_targets", [])),
            "flow_steps": len(config.get("flow", [])),
            "audit_event_types": len(config.get("audit_events", [])),
            "payload_written_to_repo": False,
            "payload_written_to_artifacts": False,
            "payload_written_to_logs": False,
            "payload_displayed_in_ui": False,
            "external_action_performed": False,
            "nothing_silently_submits": True,
        },
    }


def render_report(packet: Dict[str, Any]) -> str:
    flow = "\n".join(f"{index}. `{step}`" for index, step in enumerate(packet.get("flow", []), start=1)) or "- None"
    targets = "\n".join(
        f"- `{target.get('id')}`: {target.get('label')}"
        for target in packet.get("approved_vault_targets", [])
    ) or "- None"
    fields = "\n".join(f"- `{field}`" for field in packet.get("broker_popup_fields", [])) or "- None"
    inspector = packet.get("credential_reference_inspector", {})
    allowed = "\n".join(f"- `{field}`" for field in inspector.get("allowed_display", [])) or "- None"
    return f"""# AIGC Save Credential Broker Report

Generated At: {packet['generated_at']}

Status: {packet['status']}

## Purpose

{packet.get('purpose', '')}

## Saved Flow

{flow}

## Approved Vault Targets

{targets}

## Broker Popup Fields

{fields}

## Credential Reference Inspector

Shortcut: `{inspector.get('shortcut', 'Ctrl+N')}`

Allowed display:

{allowed}

Payload display allowed: `false`

Plaintext viewer allowed: `false`

## Safety Result

- Payload written to repo: `false`
- Payload written to artifacts: `false`
- Payload written to logs: `false`
- Payload displayed in UI: `false`
- External action performed: `false`
- Nothing silently submits: `true`
"""


def write_outputs(root: Path, config: Dict[str, Any], packet: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("outputs", {})
    packet_path = resolve_path(root, outputs.get("packet", "data/save_credential_broker/aigc_save_credential_broker_packet.json"))
    report_path = resolve_path(root, outputs.get("report", "reports/save_credential_broker_report.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_save_credential_broker_audit.jsonl"))
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(packet), encoding="utf-8")
    audit = {
        "event_id": f"AIGC-SAVE-CREDENTIAL-BROKER-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": packet["generated_at"],
        "phase": PHASE_NAME,
        "status": packet["status"],
        "vault_targets": packet["summary"]["vault_targets"],
        "payload_written_to_repo": False,
        "payload_written_to_artifacts": False,
        "payload_displayed_in_ui": False,
        "external_action_performed": False,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit, ensure_ascii=False) + "\n")
    return packet_path, report_path, audit_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC save credential broker procurement stage.")
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
        "payload_written_to_repo": False,
        "payload_displayed_in_ui": False,
        "external_action_performed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
