from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_n8n_workflow_dispatch_bridge.json"
PHASE_NAME = "n8n_workflow_dispatch_bridge_procurement"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_packet(config: Dict[str, Any]) -> Dict[str, Any]:
    trigger_contract = config.get("trigger_contract", {})
    nodes = config.get("n8n_nodes", [])
    dispatch = config.get("github_dispatch_request", {})
    safety = config.get("safety_controls", {})
    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": "completed_n8n_workflow_dispatch_bridge_procurement",
        "purpose": config.get("purpose", ""),
        "trigger_contract": trigger_contract,
        "n8n_nodes": nodes,
        "github_dispatch_request": {
            "method": dispatch.get("method", "POST"),
            "url": dispatch.get("url", ""),
            "auth_model": "n8n_managed_credential_reference_only",
            "headers_are_reference_only": True,
            "body": dispatch.get("body", {}),
        },
        "secret_references": config.get("secret_references", []),
        "safety_controls": safety,
        "expected_response": config.get("expected_response", {}),
        "failure_checks": config.get("failure_checks", []),
        "summary": {
            "ingress": trigger_contract.get("ingress", ""),
            "allowed_phrase": trigger_contract.get("allowed_phrase", ""),
            "workflow_file": trigger_contract.get("workflow_file", ""),
            "repo_full_name": trigger_contract.get("repo_full_name", ""),
            "node_count": len(nodes),
            "secret_reference_count": len(config.get("secret_references", [])),
            "raw_secret_values_logged": False,
            "raw_trigger_payload_stored": False,
            "external_submission_from_n8n_allowed": False,
            "workflow_dispatch_performed_by_this_stage": False,
            "operator_review_required": True,
        },
    }


def render_report(packet: Dict[str, Any]) -> str:
    trigger = packet.get("trigger_contract", {})
    nodes = packet.get("n8n_nodes", [])
    node_lines = "\n".join(
        f"- `{node.get('name', 'unknown')}`: {node.get('type', 'unknown')} — {node.get('purpose', '')}"
        for node in nodes
        if isinstance(node, dict)
    ) or "- None"
    secret_lines = "\n".join(f"- `{item}`" for item in packet.get("secret_references", [])) or "- None"
    checks = "\n".join(f"- {item}" for item in packet.get("failure_checks", [])) or "- None"
    body = packet.get("github_dispatch_request", {}).get("body", {})
    body_text = json.dumps(body, ensure_ascii=False, indent=2)
    return f"""# AIGC n8n Workflow Dispatch Bridge Procurement Report

Generated At: {packet['generated_at']}

Status: {packet['status']}

## Purpose

{packet.get('purpose', '')}

## Trigger Contract

- Ingress: `{trigger.get('ingress', '')}`
- Allowed phrase: `{trigger.get('allowed_phrase', '')}`
- Default ref: `{trigger.get('default_ref', '')}`
- Workflow file: `{trigger.get('workflow_file', '')}`
- Repository: `{trigger.get('repo_full_name', '')}`

## n8n Nodes

{node_lines}

## Dispatch Body

```json
{body_text}
```

## Secret References

{secret_lines}

## Failure Checks

{checks}

## Safety Result

- Raw secret values logged: `false`
- Raw trigger payload stored: `false`
- External submission from n8n allowed: `false`
- Workflow dispatch performed by this stage: `false`
- Operator review required: `true`
"""


def write_outputs(root: Path, config: Dict[str, Any], packet: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("outputs", {})
    packet_path = resolve_path(root, outputs.get("packet", "data/n8n_bridge/aigc_n8n_workflow_dispatch_bridge_packet.json"))
    report_path = resolve_path(root, outputs.get("report", "reports/n8n_workflow_dispatch_bridge_report.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_n8n_workflow_dispatch_bridge_audit.jsonl"))
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(packet), encoding="utf-8")
    audit = {
        "event_id": f"AIGC-N8N-BRIDGE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": packet["generated_at"],
        "phase": PHASE_NAME,
        "status": packet["status"],
        "workflow_dispatch_performed_by_this_stage": False,
        "raw_secret_values_logged": False,
        "operator_review_required": True,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit, ensure_ascii=False) + "\n")
    return packet_path, report_path, audit_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC n8n workflow dispatch bridge procurement stage.")
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
        "workflow_dispatch_performed_by_this_stage": False,
        "raw_secret_values_logged": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
