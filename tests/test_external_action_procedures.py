from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.core.external_action_procedures import run_external_action_procedure


def test_external_action_procedure_allows_popup_for_message(tmp_path: Path) -> None:
    copy_fixture("config/approval_gated_external_actions.json", tmp_path)
    copy_fixture("config/external_action_procedure_controls.json", tmp_path)

    result = run_external_action_procedure(
        project_root=tmp_path,
        action="message",
        destination="manual-review",
        payload={"message": "Draft only"},
        risk_class="medium",
        platform_terms_status="review_required",
    )

    packet = result["procedure_packet"]
    assert result["external_action_performed"] is False
    assert packet["status"] == "approval_gated_procedure_ready_for_operator_review"
    assert packet["proceed_button_enabled"] is True
    assert packet["operator_popup_required"] is True
    assert packet["professional_controls"]["self_approval_allowed"] is False
    assert Path(tmp_path / result["procedure_packet_path"]).exists()


def test_external_action_procedure_blocks_fabricated_credentials(tmp_path: Path) -> None:
    copy_fixture("config/approval_gated_external_actions.json", tmp_path)
    copy_fixture("config/external_action_procedure_controls.json", tmp_path)

    result = run_external_action_procedure(
        project_root=tmp_path,
        action="fabricate_credentials",
        destination="blocked",
        payload={"claim": "fake certification"},
        risk_class="critical",
        platform_terms_status="blocked",
    )

    packet = result["procedure_packet"]
    assert packet["status"] == "hard_blocked_procedure"
    assert packet["proceed_button_enabled"] is False
    assert packet["popup_packet"]["external_action_performed"] is False


def test_external_action_procedure_cli_smoke(tmp_path: Path) -> None:
    copy_fixture("config/approval_gated_external_actions.json", tmp_path)
    copy_fixture("config/external_action_procedure_controls.json", tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "src/external_action_procedures_cli.py",
            "--root",
            str(tmp_path),
            "--action",
            "message",
            "--destination",
            "manual-review",
            "--payload-json",
            json.dumps({"message": "Draft only"}),
            "--risk-class",
            "medium",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["external_action_performed"] is False
    assert payload["procedure_packet"]["proceed_button_enabled"] is True


def copy_fixture(relative: str, target_root: Path) -> None:
    source = Path(relative)
    target = target_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
