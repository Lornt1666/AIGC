from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.contract_validator import validate_artifact
from src.core.phase_registry import build_phase_registry
from src.phase18_productization import ProductizationReadiness


def test_phase18_productization_generates_internal_release_candidate(tmp_path: Path) -> None:
    create_phase18_fixture(tmp_path)
    record = ProductizationReadiness(tmp_path).run_from_config(tmp_path / "config" / "phase18_productization.json")
    payload = asdict(record)

    validate_artifact("productization_release_record", payload)
    assert payload["status"] == "internal_release_candidate"
    assert payload["required_files_present"] is True
    assert payload["all_rights_reserved"] is True
    assert payload["deployment_performed"] is False
    assert payload["public_release_allowed"] is False
    assert payload["external_action_performed"] is False


def test_phase18_productization_blocks_missing_release_files(tmp_path: Path) -> None:
    create_phase18_fixture(tmp_path)
    (tmp_path / "README.md").unlink()
    record = ProductizationReadiness(tmp_path).run_from_config(tmp_path / "config" / "phase18_productization.json")

    assert record.status == "blocked_until_release_requirements_met"
    assert "README.md" in record.missing_required_files
    assert record.external_action_performed is False


def test_cli_run_phase18_exports_release_readiness(tmp_path: Path) -> None:
    create_phase18_fixture(tmp_path)
    subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "--root",
            str(tmp_path),
            "--state-db",
            str(tmp_path / "state.sqlite"),
            "run",
            "phase18",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_path = tmp_path / "data" / "phase18_productization" / "aigc_phase18_release_readiness.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    validate_artifact("productization_release_record", payload)
    assert payload["external_action_performed"] is False


def test_phase_registry_includes_phase18_productization() -> None:
    registry = build_phase_registry(PROJECT_ROOT)
    assert registry["phase18"].schema_name == "productization_release_record"
    assert registry["phase18"].external_action_risk == "deployment_and_public_release_require_approval"


def create_phase18_fixture(root: Path) -> None:
    required_files = [
        "README.md",
        "LICENSE",
        "src/aigc.py",
        "schemas/productization_release_record.schema.json",
        "docs/PRODUCTIZATION_RUNBOOK.md",
    ]
    for relative_path in required_files:
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative_path == "LICENSE":
            target.write_text("Copyright 2026\n\nAll Rights Reserved.\n", encoding="utf-8")
        else:
            target.write_text("fixture\n", encoding="utf-8")
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "phase18_productization.json").write_text(json.dumps({
        "version": "0.0.0-test",
        "release_type": "internal_private_kernel",
        "public_release_allowed": False,
        "output_file": "data/phase18_productization/aigc_phase18_release_readiness.json",
        "report_file": "data/reports/phase18_signature_update.md",
        "audit_log": "data/audit/aigc_phase18_audit.jsonl",
        "required_files": required_files,
        "validation_commands": ["python -m pytest"],
        "manual_release_gates": ["confirm_private_repo"],
        "forbidden_productization_behaviors": ["publish_public_release_without_operator_approval"],
        "release_artifacts": ["data/phase18_productization/aigc_phase18_release_readiness.json"],
    }, indent=2), encoding="utf-8")
