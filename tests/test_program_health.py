from __future__ import annotations

import json
from pathlib import Path

from src.core.program_health import run_program_health, write_health_report


def test_program_health_reports_safe_defaults() -> None:
    report = run_program_health(Path("."))
    payload = report.to_dict()

    assert payload["safe_mode_default"] is True
    assert payload["external_actions_enabled"] is False
    assert payload["overall_status"] in {"healthy", "warning"}
    assert any(item["name"] == "external_action_default" for item in payload["checks"])


def test_program_health_can_write_report(tmp_path: Path) -> None:
    required_paths = [
        "src/aigc.py",
        "src/dashboard/operator_cockpit_app.py",
        "src/security/redaction_scanner.py",
        "src/core/work_order.py",
        "src/core/paycheque_workflow.py",
        "config/example_work_order.json",
        "config/paycheque_workflow.json",
        "schemas/work_order_packet.schema.json",
        "schemas/paycheque_pipeline.schema.json",
        "tests",
    ]
    for relative in required_paths:
        path = tmp_path / relative
        if "." in Path(relative).name:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)

    report_path = write_health_report(tmp_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report_path.exists()
    assert payload["external_actions_enabled"] is False
    assert payload["safe_mode_default"] is True
