from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "core" / "assurance" / "sensorium.py"
SPEC = importlib.util.spec_from_file_location("assurance_sensorium", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

AssuranceSensorium = MODULE.AssuranceSensorium


def test_healthy_observation_has_no_finding() -> None:
    result = AssuranceSensorium().observe(
        observation_id="OBS-001",
        sensor_id="exact-revision",
        revision="abcdef123456",
        signal="revision bound",
        health_state="healthy",
        domain="evidence",
    )
    assert result.passed
    assert result.finding is None
    assert result.observation["contract_type"] == "observation"


def test_unavailable_sensor_is_blocking() -> None:
    result = AssuranceSensorium().observe(
        observation_id="OBS-002",
        sensor_id="traceability",
        revision="abcdef123456",
        signal="required source unavailable",
        health_state="unavailable",
        domain="governance",
        severity="high",
    )
    assert result.passed
    assert result.finding is not None
    assert result.finding["payload"]["blocking"] is True
    assert AssuranceSensorium.aggregate([result.finding]) == "blocking"


def test_invalid_confidence_fails() -> None:
    result = AssuranceSensorium().observe(
        observation_id="OBS-003",
        sensor_id="claim-check",
        revision="abcdef123456",
        signal="claim checked",
        health_state="healthy",
        domain="truth",
        confidence=1.2,
    )
    assert not result.passed
    assert "INVALID_CONFIDENCE" in result.reason_codes


def test_invalid_health_fails() -> None:
    result = AssuranceSensorium().observe(
        observation_id="OBS-004",
        sensor_id="health-check",
        revision="abcdef123456",
        signal="health checked",
        health_state="unknown",
        domain="operations",
    )
    assert not result.passed
    assert "INVALID_SENSOR_HEALTH" in result.reason_codes
