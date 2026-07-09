from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_standalone_work_order_cli_smoke(tmp_path: Path) -> None:
    payload = {
        "work_order_id": "AIGC-WO-CLI-001",
        "title": "CLI smoke work order",
        "objective": "Verify the standalone dry-run CLI writes governed artifacts.",
        "domain": "testing",
        "urgency": "normal",
        "risk_class": "medium",
        "desired_output": "run receipt",
        "external_action_intent": "none",
        "acceptance_criteria": ["CLI exits zero", "no external action"],
        "operator_visible_summary": "CLI smoke.",
        "symbolic_layers": [],
        "requested_agents": [],
        "secret_references": [],
        "source": "pytest",
    }
    input_path = tmp_path / "work_order.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "src/work_order_cli.py",
            "--root",
            str(tmp_path),
            "work-order",
            "--input",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["run_receipt"]["external_action_performed"] is False
    assert output["governance_decision"]["self_approval_allowed"] is False


def test_unified_aigc_cli_accepts_work_order_smoke_phase() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "src/aigc.py",
            "run",
            "governance-smoke",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["run_receipt"]["external_action_performed"] is False
    assert output["approval_packet"]["self_approval_allowed"] is False
