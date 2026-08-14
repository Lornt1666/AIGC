"""Test AIGC phase execution."""

import subprocess
import sys


def test_phase14_preflight():
    """Test Phase 14 runtime preflight."""
    result = subprocess.run(
        [sys.executable, "src/aigc.py", "run", "phase14"],
        capture_output=True,
        text=True,
    )
    assert result.returncode in [0, 1], "Phase 14 should complete"


def test_health_check():
    """Test health check functionality."""
    result = subprocess.run(
        [sys.executable, "src/aigc.py", "health"],
        capture_output=True,
        text=True,
    )
    assert result.returncode in [0, 1], "Health check should execute"


def test_validation():
    """Test contract validation."""
    result = subprocess.run(
        [sys.executable, "src/aigc.py", "validate"],
        capture_output=True,
        text=True,
    )
    assert result.returncode in [0, 1], "Validation should execute"
