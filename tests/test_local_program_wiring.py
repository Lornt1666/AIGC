from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_aigc_cli_exposes_health_command() -> None:
    result = subprocess.run(
        [sys.executable, "src/aigc.py", "health"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode in {0, 1}
    assert "safe_mode_default" in result.stdout
    assert "external_actions_enabled" in result.stdout


def test_local_program_docs_exist() -> None:
    docs = [
        Path("docs/AIGC_WINDOWS_DESKTOP_SETUP.md"),
        Path("docs/AIGC_PROGRAM_RUNBOOK.md"),
        Path("docs/AIGC_TROUBLESHOOTING.md"),
        Path("docs/AIGC_EXE_BUILD_NOTES.md"),
    ]

    for doc in docs:
        assert doc.exists()
        text = doc.read_text(encoding="utf-8")
        assert "AIGC" in text
        assert "external" in text.lower()


def test_readme_documents_local_program_path() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Run AIGC as a Local Program" in readme
    assert "RUN_AIGC_PROGRAM.bat" in readme
    assert "python .\\src\\aigc.py health" in readme
