from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_work_acquisition_cli_smoke(tmp_path: Path) -> None:
    registry = {
        "registry_id": "CLI-DOMAINS",
        "mode": "read_only_or_manual_handoff_only",
        "domains": [
            {
                "domain_id": "remoteok",
                "name": "RemoteOK",
                "base_url": "https://remoteok.com",
                "source_mode": "approved_api_or_public_read_only",
                "priority": 84,
                "allowed_actions": ["search", "read", "rank", "draft_application_packet"],
                "blocked_actions": ["auto_apply", "auto_submit"],
                "terms_review_required": True,
            }
        ],
        "global_constraints": {
            "dry_run_by_default": True,
            "domain_allowlist_required": True,
            "no_login_by_default": True,
            "no_forms_by_default": True,
            "no_javascript_automation_by_default": True,
            "no_auto_apply": True,
            "no_auto_submit": True,
            "no_auto_accept": True,
            "no_auto_pay": True,
            "no_auto_purchase": True,
            "no_auto_deploy": True,
            "operator_review_required": True,
            "external_action_performed": False,
        },
    }
    profile = {
        "profile_id": "CLI-PROFILE",
        "operator_name": "Justice Gray Maciocha",
        "program_name": "AIGC Operator Program",
        "positioning": "Governed AI operator workbench.",
        "skills": ["Python automation"],
        "target_work_types": ["proposal packet preparation"],
    }
    registry_path = tmp_path / "work_domain_registry.json"
    profile_path = tmp_path / "work_acquisition_profile.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "src/work_acquisition_cli.py",
            "--root",
            str(tmp_path),
            "--registry",
            str(registry_path),
            "--profile",
            str(profile_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["external_action_performed"] is False
    assert payload["acquisition_packet"]["search_domains"][0]["operator_commit_required"] is True
