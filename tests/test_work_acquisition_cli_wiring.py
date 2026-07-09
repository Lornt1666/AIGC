from __future__ import annotations

import subprocess
import sys


def test_unified_aigc_cli_exposes_work_acquisition_mode() -> None:
    result = subprocess.run(
        [sys.executable, "src/aigc.py", "run", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "work-acquisition" in result.stdout
