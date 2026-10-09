from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runner_recovery_runbook_refuses_zero_step_evidence() -> None:
    text = (ROOT / "docs" / "GITHUB_ACTIONS_RUNNER_RECOVERY.md").read_text(
        encoding="utf-8"
    )

    assert "steps: none" in text
    assert "logs: none" in text
    assert "artifacts: none" in text
    assert "Do not merge" in text
    assert "PR #123" in text
    assert "PR #121" in text
    assert "PR #122" in text
