from __future__ import annotations

import json
from pathlib import Path

from src.core.contract_validator import validate_file
from src.core.work_acquisition import WorkAcquisitionError, run_work_acquisition


def test_work_acquisition_generates_safe_packets(tmp_path: Path) -> None:
    registry = {
        "registry_id": "TEST-DOMAINS",
        "mode": "read_only_or_manual_handoff_only",
        "domains": [
            {
                "domain_id": "greenhouse",
                "name": "Greenhouse job boards",
                "base_url": "https://boards.greenhouse.io",
                "source_mode": "public_board_read_only",
                "priority": 88,
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
        "profile_id": "TEST-PROFILE",
        "operator_name": "Justice Gray Maciocha",
        "program_name": "AIGC Operator Program",
        "positioning": "Governed AI operator workbench.",
        "skills": ["Python automation", "proposal drafting"],
        "target_work_types": ["automation dashboard setup", "proposal packet preparation"],
    }
    registry_path = tmp_path / "work_domain_registry.json"
    profile_path = tmp_path / "work_acquisition_profile.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    result = run_work_acquisition(tmp_path, registry_path, profile_path)

    assert result["external_action_performed"] is False
    assert result["acquisition_packet"]["domain_count"] == 1
    assert result["acquisition_packet"]["search_domains"][0]["operator_commit_required"] is True
    assert "auto_submit" in result["acquisition_packet"]["blocked_actions"]
    assert result["performance_packet"]["operator_review_required"] is True
    validate_file("work_acquisition_packet", tmp_path / result["acquisition_path"])
    validate_file("work_performance_packet", tmp_path / result["performance_path"])


def test_work_acquisition_rejects_unsafe_constraints(tmp_path: Path) -> None:
    registry = {
        "registry_id": "UNSAFE-DOMAINS",
        "mode": "read_only_or_manual_handoff_only",
        "domains": [],
        "global_constraints": {
            "dry_run_by_default": False,
            "domain_allowlist_required": True,
            "no_login_by_default": True,
            "no_forms_by_default": True,
            "no_auto_apply": True,
            "no_auto_submit": True,
            "operator_review_required": True,
            "external_action_performed": False,
        },
    }
    profile = {"profile_id": "TEST-PROFILE", "target_work_types": []}
    registry_path = tmp_path / "work_domain_registry.json"
    profile_path = tmp_path / "work_acquisition_profile.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    try:
        run_work_acquisition(tmp_path, registry_path, profile_path)
    except WorkAcquisitionError as exc:
        assert "dry_run_by_default" in str(exc)
    else:
        raise AssertionError("Unsafe registry should be rejected.")
