from __future__ import annotations

from pathlib import Path


def test_windows_launcher_exists_and_defaults_safe() -> None:
    launcher = Path("RUN_AIGC_PROGRAM.bat")
    text = launcher.read_text(encoding="utf-8")

    assert launcher.exists()
    assert "AIGC_SAFE_MODE" in text
    assert "python .\\src\\aigc.py health --write" in text
    assert "streamlit run .\\src\\dashboard\\operator_cockpit_app.py" in text
    assert "submit" not in text.lower()
    assert "pay" not in text.lower().replace("paycheque", "")


def test_powershell_launcher_exists_and_runs_health_first() -> None:
    launcher = Path("scripts/run_aigc_program.ps1")
    text = launcher.read_text(encoding="utf-8")

    assert launcher.exists()
    assert "AIGC_SAFE_MODE" in text
    assert "python .\\src\\aigc.py health --write" in text
    assert "streamlit run .\\src\\dashboard\\operator_cockpit_app.py" in text
    assert "AIGC_INSTALL_DEPENDENCIES" in text


def test_setup_script_is_local_only_and_validates_before_launch() -> None:
    setup = Path("scripts/setup_aigc_local.ps1")
    text = setup.read_text(encoding="utf-8")
    lowered = text.lower()

    assert setup.exists()
    assert "$SystemPython.Source -m venv .venv" in text
    assert "$VenvPython" in text
    assert "$PythonExe -m pip install -r requirements.txt" in text
    assert "$PythonExe .\\src\\aigc.py validate" in text
    assert "$PythonExe .\\src\\aigc.py run governance-smoke" in text
    assert "$PythonExe .\\src\\security_privacy_wiring_cli.py" in text
    assert "$PythonExe .\\src\\agent_operating_doctrine_cli.py" in text
    assert "$PythonExe -m pytest -q" in text
    assert "external_action_performed" not in lowered
    assert "deploy" not in lowered
