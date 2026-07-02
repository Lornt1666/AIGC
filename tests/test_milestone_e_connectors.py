from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.connector_policy import ConnectorPolicyGate
from src.core.contract_validator import validate_artifact
from src.core.phase_registry import build_phase_registry
from src.phase10_connector_registry import ConnectorRegistryBuilder


def test_connector_policy_blocks_write_like_actions() -> None:
    record = {
        "enabled": True,
        "allowed_actions": ["read_api", "submit_application"],
        "read_only": True,
        "external_write_allowed": False,
        "live_execution_allowed": False,
        "external_action_performed": False,
        "requires_secret": False,
    }
    result = ConnectorPolicyGate(allowed_read_only_actions=["read_api"]).inspect(record)
    assert result.status == "blocked"
    assert "allowed_actions_contain_write_like_capability" in result.risk_flags


def test_phase10_connector_registry_generates_read_only_records(tmp_path: Path) -> None:
    create_phase10_fixture(tmp_path)
    records = ConnectorRegistryBuilder(tmp_path).run_from_config(tmp_path / "config" / "phase10_connector_registry.json")
    payloads = [asdict(record) for record in records]

    assert len(records) == 2
    for payload in payloads:
        validate_artifact("connector_record", payload)
        assert payload["external_action_performed"] is False
        assert payload["external_write_allowed"] is False
        assert payload["live_execution_allowed"] is False
    ready = [item for item in payloads if item["status"] == "ready_read_only"]
    disabled = [item for item in payloads if item["status"] == "disabled_reference_only"]
    assert len(ready) == 1
    assert len(disabled) == 1


def test_cli_run_phase10_exports_registry(tmp_path: Path) -> None:
    create_phase10_fixture(tmp_path)
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase10",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase10_connectors" / "aigc_phase10_connector_registry.json"
    records = json.loads(output_path.read_text(encoding="utf-8"))
    assert records
    assert all(item["external_action_performed"] is False for item in records)


def test_phase_registry_includes_phase10_connector_registry() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase10"].schema_name == "connector_record"
    assert registry["phase10"].external_action_risk == "no_live_write_connectors"


def create_phase10_fixture(root: Path) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "phase10_connector_registry.json").write_text(json.dumps({
        "input_files": {
            "phase2_sources": "config/phase2_sources.json"
        },
        "output_file": "data/phase10_connectors/aigc_phase10_connector_registry.json",
        "report_file": "data/reports/phase10_signature_update.md",
        "audit_log": "data/audit/aigc_phase10_audit.jsonl",
        "default_capability": "opportunity_discovery",
        "allowed_runtime_modes": ["read_only_connector_registry"],
        "allowed_read_only_actions": ["read_api", "normalize", "classify", "score", "search_jobs"],
        "forbidden_write_action_terms": ["apply", "submit", "message", "send", "bid"],
        "maturity_levels": {
            "enabled_read_only": "read_only_validated",
            "disabled_reference": "configured_reference_only",
            "needs_review": "needs_connector_review",
            "blocked": "blocked_by_connector_policy"
        }
    }, indent=2), encoding="utf-8")
    (root / "config" / "phase2_sources.json").write_text(json.dumps({
        "sources": [
            {
                "name": "Ready Source",
                "slug": "ready",
                "connector": "ready_api",
                "type": "api",
                "enabled": True,
                "attribution_required": True,
                "url": "https://example.invalid/ready",
                "allowed_actions": ["read_api", "normalize", "classify", "score"],
                "forbidden_actions": ["auto_apply"]
            },
            {
                "name": "Credential Source",
                "slug": "credential",
                "connector": "credential_api",
                "type": "api",
                "enabled": False,
                "attribution_required": False,
                "requires_api_key": True,
                "url": "https://example.invalid/credential",
                "allowed_actions": ["search_jobs", "normalize", "classify", "score"],
                "forbidden_actions": ["auto_apply"]
            }
        ]
    }, indent=2), encoding="utf-8")
