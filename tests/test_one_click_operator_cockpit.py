from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_double_click_launcher_runs_safe_initializer_then_cockpit_v2() -> None:
    batch = read("INITIALIZE_AIGC.bat")
    powershell = read("scripts/initialize_aigc.ps1")

    assert "initialize_aigc.ps1" in batch
    assert "scripts/initialize_aigc.py" in powershell
    assert "operator_cockpit_v2_app.py" in powershell
    assert "pip install" not in powershell
    assert "--execute" not in powershell


def test_cockpit_v2_preserves_existing_tabs_and_adds_new_controls() -> None:
    app = read("src/dashboard/operator_cockpit_v2_app.py")

    for tab in (
        '"Initialize"',
        '"Run"',
        '"Jobs & Interviews"',
        '"New Work Order"',
        '"Paycheque Pipeline"',
        '"Review & Accept"',
        '"Audit / Transparency"',
    ):
        assert tab in app
    assert "render_run_tab" in app
    assert "render_review_tab" in app
    assert "render_operator_initialization_tab" in app
    assert "render_jobs_interviews_tab" in app


def test_jobs_panel_has_no_external_commit_button() -> None:
    panel = read("src/dashboard/job_interview_panel.py").lower()

    assert "accept for manual submission" in panel
    assert "open official posting" in panel
    assert "record interview invitation internally" in panel
    assert "submit application" not in panel
    assert "send message" not in panel
    assert "schedule interview automatically" not in panel
