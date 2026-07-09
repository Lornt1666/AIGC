from __future__ import annotations

import json
from pathlib import Path

from src.core.contract_validator import validate_file
from src.core.paycheque_workflow import PaychequeWorkflowError, prepare_paycheque_workflow, run_paycheque_workflow


def make_config() -> dict:
    return {
        "user_profile": {
            "name": "Justice Gray Maciocha",
            "skills": ["Python automation", "proposal drafting", "systems engineering"],
        },
        "platforms": [
            {
                "platform_id": "manual",
                "name": "Manual Leads",
                "source_type": "manual_entry",
                "read_only": True,
                "opportunities": [
                    {
                        "opportunity_id": "PAY-OPP-TEST",
                        "title": "Build a local dashboard",
                        "platform": "Manual Lead",
                        "url": "https://example.com/manual-lead",
                        "description": "Need a small local dashboard.",
                        "fit_score": 90,
                    }
                ],
            }
        ],
        "pending_contracts": [
            {
                "contract_id": "PAY-CONTRACT-TEST",
                "title": "Finish milestone",
                "platform": "Manual Contract Tracker",
                "url": "https://example.com/contract",
                "milestone": "Review deliverable and submit manually.",
                "fit_score": 95,
            }
        ],
        "pending_payments": [
            {
                "payment_id": "PAY-INVOICE-TEST",
                "title": "Draft invoice",
                "platform": "Manual Invoice Tracker",
                "url": "https://example.com/invoice",
                "invoice_note": "Draft invoice note only.",
                "fit_score": 80,
            }
        ],
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


def test_prepare_paycheque_workflow_blocks_commit_actions() -> None:
    config = make_config()
    pipeline = prepare_paycheque_workflow(
        config["user_profile"],
        config["platforms"],
        config["pending_contracts"],
        config["pending_payments"],
    )

    assert pipeline["external_action_performed"] is False
    assert "auto_submit" in pipeline["commit_actions_blocked"]
    assert "Submit" not in pipeline["dashboard_buttons"]
    assert pipeline["actions"]
    assert all(action["external_action_performed"] is False for action in pipeline["actions"])
    assert all(action["buttons"]["submit_apply_accept_pay_deploy"] is False for action in pipeline["actions"])


def test_run_paycheque_workflow_writes_valid_pipeline(tmp_path: Path) -> None:
    config_path = tmp_path / "paycheque_workflow.json"
    config_path.write_text(json.dumps(make_config()), encoding="utf-8")

    result = run_paycheque_workflow(tmp_path, config_path)

    assert result["external_action_performed"] is False
    validate_file("paycheque_pipeline", tmp_path / result["pipeline_path"])
    assert (tmp_path / result["report_path"]).exists()
    assert (tmp_path / result["audit_receipt_path"]).exists()


def test_paycheque_workflow_rejects_unsafe_constraint() -> None:
    config = make_config()
    config["constraints"]["auto_submit"] = True
    config_path = Path("paycheque_unsafe_tmp.json")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    try:
        try:
            run_paycheque_workflow(Path("."), config_path)
        except PaychequeWorkflowError as exc:
            assert "auto_submit" in str(exc)
        else:
            raise AssertionError("Unsafe auto_submit must be rejected.")
    finally:
        config_path.unlink(missing_ok=True)
