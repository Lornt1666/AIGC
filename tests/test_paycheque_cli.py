from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_paycheque_workflow_cli_smoke(tmp_path: Path) -> None:
    config = {
        "user_profile": {
            "name": "Justice Gray Maciocha",
            "skills": ["Python automation", "proposal drafting"],
        },
        "platforms": [
            {
                "platform_id": "manual",
                "name": "Manual Leads",
                "source_type": "manual_entry",
                "read_only": True,
                "opportunities": [
                    {
                        "opportunity_id": "PAY-CLI-OPP",
                        "title": "Create a local business dashboard",
                        "platform": "Manual Lead",
                        "url": "https://example.com/paycheque-cli",
                        "description": "Build a local dashboard and draft reports.",
                        "fit_score": 91,
                    }
                ],
            }
        ],
        "pending_contracts": [],
        "pending_payments": [],
        "constraints": {
            "auto_apply": False,
            "auto_submit": False,
            "auto_accept": False,
            "auto_pay": False,
            "auto_purchase": False,
            "auto_deploy": False,
            "auto_use_credentials": False,
            "secret_logging": False,
            "self_approval": False,
            "external_action_performed": False,
        },
        "dashboard_buttons": ["ReviewDraft", "CopyText", "OpenPlatformLink", "MarkCompletedInternalOnly"],
    }
    config_path = tmp_path / "paycheque_workflow.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "src/paycheque_workflow_cli.py",
            "--root",
            str(tmp_path),
            "--input",
            str(config_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["external_action_performed"] is False
    assert output["pipeline"]["actions"][0]["buttons"]["submit_apply_accept_pay_deploy"] is False


def test_unified_cli_declares_paycheque_mode() -> None:
    help_result = subprocess.run(
        [sys.executable, "src/aigc.py", "run", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert help_result.returncode == 0
    assert "paycheque" in help_result.stdout
