from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.connector_policy import ConnectorPolicyGate  # noqa: E402


@dataclass
class ConnectorRecord:
    connector_id: str
    created_at: str
    slug: str
    name: str
    provider: str
    phase: str
    capability: str
    mode: str
    status: str
    maturity_level: str
    enabled: bool
    source_type: str
    source_url: str
    allowed_actions: List[str]
    forbidden_actions: List[str]
    allowed_runtime_modes: List[str]
    read_only: bool
    live_execution_allowed: bool
    external_write_allowed: bool
    external_action_performed: bool
    requires_secret: bool
    secret_key: str
    credential_policy: str
    attribution_required: bool
    terms_notes: List[str]
    rate_limit_policy: str
    risk_flags: List[str] = field(default_factory=list)
    safety_status: str = "cleared"
    audit_required: bool = True


class Phase10AuditLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, data: Dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "timestamp": utc_now(),
            "event_type": event_type,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event_id


class ConnectorRegistryBuilder:
    SECRET_HINTS = {
        "requires_api_key",
        "requires_app_registration",
        "requires_board_token",
    }

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def run_from_config(self, config_path: Path) -> List[ConnectorRecord]:
        config = load_json_dict(config_path)
        phase2_path = resolve_project_path(
            self.project_root,
            config.get("input_files", {}).get("phase2_sources", "config/phase2_sources.json"),
        )
        phase2_config = load_json_dict(phase2_path)
        output_path = resolve_project_path(
            self.project_root,
            config.get("output_file", "data/phase10_connectors/aigc_phase10_connector_registry.json"),
        )
        report_path = resolve_project_path(
            self.project_root,
            config.get("report_file", "data/reports/phase10_signature_update.md"),
        )
        audit_log = resolve_project_path(
            self.project_root,
            config.get("audit_log", "data/audit/aigc_phase10_audit.jsonl"),
        )
        records = self.build_records(config, phase2_config)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        ledger = Phase10AuditLedger(audit_log)
        ledger.record("phase10_connector_registry_exported", {
            "path": str(output_path),
            "records": len(records),
            "ready_read_only": len([item for item in records if item.status == "ready_read_only"]),
            "blocked": len([item for item in records if item.status == "blocked"]),
            "external_action_performed": False,
        })
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self.signature_update(records), encoding="utf-8")
        return records

    def build_records(
        self,
        config: Dict[str, Any],
        phase2_config: Dict[str, Any],
    ) -> List[ConnectorRecord]:
        gate = ConnectorPolicyGate(
            forbidden_write_terms=config.get("forbidden_write_action_terms", []),
            allowed_read_only_actions=config.get("allowed_read_only_actions", []),
            maturity_levels=config.get("maturity_levels", {}),
        )
        records: List[ConnectorRecord] = []
        for source in phase2_config.get("sources", []):
            if not isinstance(source, dict):
                continue
            base = self._base_record(config, source)
            result = gate.inspect(base)
            base["status"] = result.status
            base["maturity_level"] = result.maturity_level
            base["risk_flags"] = result.risk_flags
            base["safety_status"] = result.safety_status
            record = ConnectorRecord(**base)
            records.append(record)
        return records

    def _base_record(self, config: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
        slug = str(source.get("slug") or slugify(str(source.get("name", "connector"))))
        provider = str(source.get("connector") or slug)
        requires_secret = self._requires_secret(source)
        secret_key = str(source.get("secret_key", ""))
        url = str(source.get("url") or first_value(source.get("urls", [])) or "")
        if requires_secret and secret_key:
            credential_policy = "google_secret_manager_reference_required"
        elif requires_secret:
            credential_policy = "secret_required_before_enablement"
        else:
            credential_policy = "no_secret_required"
        return {
            "connector_id": make_connector_id(slug, provider),
            "created_at": utc_now(),
            "slug": slug,
            "name": str(source.get("name") or slug),
            "provider": provider,
            "phase": "phase10_connector_api_layer",
            "capability": str(config.get("default_capability", "opportunity_discovery")),
            "mode": "read_only",
            "status": "pending_policy_review",
            "maturity_level": "pending_policy_review",
            "enabled": bool(source.get("enabled", False)),
            "source_type": str(source.get("type") or "unknown"),
            "source_url": url,
            "allowed_actions": [str(item) for item in source.get("allowed_actions", [])],
            "forbidden_actions": [str(item) for item in source.get("forbidden_actions", [])],
            "allowed_runtime_modes": [str(item) for item in config.get("allowed_runtime_modes", [])],
            "read_only": True,
            "live_execution_allowed": False,
            "external_write_allowed": False,
            "external_action_performed": False,
            "requires_secret": requires_secret,
            "secret_key": secret_key,
            "credential_policy": credential_policy,
            "attribution_required": bool(source.get("attribution_required", False)),
            "terms_notes": [str(item) for item in config.get("terms_notes_by_slug", {}).get(slug, [])],
            "rate_limit_policy": str(config.get("rate_limit_policy", "single_read_only_run")),
            "audit_required": True,
        }

    def _requires_secret(self, source: Dict[str, Any]) -> bool:
        return any(bool(source.get(key, False)) for key in self.SECRET_HINTS)

    def signature_update(self, records: List[ConnectorRecord]) -> str:
        ready = [record for record in records if record.status == "ready_read_only"]
        disabled = [record for record in records if record.status == "disabled_reference_only"]
        blocked = [record for record in records if record.status == "blocked"]
        return "\n".join([
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 10 - Connector / API Integration Layer",
            "Operational Identity:",
            "Connector Maturity and Capability Governance Layer",
            "Action Performed:",
            "Generated a read-only connector maturity registry from configured discovery sources.",
            "Safety Review:",
            "No live write connectors enabled.",
            "No credentials used.",
            "No external action performed.",
            "No applications, messages, bids, submissions, or employer contact.",
            f"Connector Records: {len(records)}",
            f"Ready Read-Only Connectors: {len(ready)}",
            f"Disabled Reference Connectors: {len(disabled)}",
            f"Blocked Connectors: {len(blocked)}",
            "Approval Required:",
            "Yes, before enabling any connector with credential use or external write capability.",
        ]).strip() + "\n"


def make_connector_id(slug: str, provider: str) -> str:
    seed = f"{slug}|{provider}|phase10_connector_registry"
    return "AIGC-CONN-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def first_value(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return ""


def slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


def load_json_dict(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run AIGC Phase 10 connector registry.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "phase10_connector_registry.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phase = ConnectorRegistryBuilder(project_root=args.project_root)
    records = phase.run_from_config(args.config)
    print(phase.signature_update(records))
    print(f"\nConnector registry exported: {args.project_root / 'data' / 'phase10_connectors' / 'aigc_phase10_connector_registry.json'}")
    return 1 if any(record.status == "blocked" for record in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
