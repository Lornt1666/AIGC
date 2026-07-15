from __future__ import annotations

from pathlib import Path

from src.core.operator_initialization import (
    INITIALIZATION_BOUNDARY,
    build_initialization_commands,
)


ROOT = Path(__file__).resolve().parents[1]


def test_initialization_sequence_is_internal_and_mock_only() -> None:
    commands = build_initialization_commands(ROOT)
    rendered = "\n".join(" ".join(item.command).lower() for item in commands)

    assert len(commands) == 7
    assert "init-db" in rendered
    assert "validate" in rendered
    assert "readiness" in rendered
    assert "work-acquisition" in rendered
    assert "cockpit-smoke" in rendered
    assert "run_provider_discovery_mock.py" in rendered
    assert "terraform apply" not in rendered
    assert "auto_apply" not in rendered
    assert "auto_submit" not in rendered
    assert "auto_message" not in rendered
    assert "schedule interview" not in rendered


def test_initialization_boundary_forbids_consequential_automation() -> None:
    boundary = "\n".join(INITIALIZATION_BOUNDARY).lower()

    for marker in (
        "no package installation",
        "credential use",
        "provider mutation",
        "terraform apply",
        "job submission",
        "messaging",
        "contract acceptance",
        "interview scheduling",
        "deployment",
        "delivery",
    ):
        assert marker in boundary
