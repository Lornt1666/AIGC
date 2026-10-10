from __future__ import annotations

import argparse
import os

from src import aigc
from src.core.state_store import AIGCStateStore


def test_cli_durable_stop_fails_closed_in_production_without_dsn(monkeypatch) -> None:
    monkeypatch.setenv("AIGC_ENV", "production")
    monkeypatch.delenv("AIGC_COMMAND_CENTER_DATABASE_URL", raising=False)
    active, reason = aigc._durable_emergency_stop_state()
    assert active is True
    assert "configuration missing" in reason


def test_cli_durable_stop_is_optional_only_in_development_without_dsn(monkeypatch) -> None:
    monkeypatch.setenv("AIGC_ENV", "development")
    monkeypatch.delenv("AIGC_COMMAND_CENTER_DATABASE_URL", raising=False)
    assert aigc._durable_emergency_stop_state() == (False, "")


def test_cli_blocks_phase_when_shared_stop_is_active(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AIGC_ENV", "production")
    monkeypatch.setenv("AIGC_COMMAND_CENTER_DATABASE_URL", "postgresql://unused-for-monkeypatch")
    monkeypatch.setattr(aigc, "_durable_emergency_stop_state", lambda: (True, "durable emergency stop active at epoch 4"))
    store = AIGCStateStore(tmp_path / "aigc-state.sqlite3")
    args = argparse.Namespace(phase="work-order", input=None, artifact_root=None)
    result = aigc.command_run(args, tmp_path, store)
    assert result == 2
    assert store.emergency_stop_active() is False
