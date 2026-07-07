from __future__ import annotations

from src.webapp.app import BUSINESS_CYCLE, app


def test_cloud_app_exposes_expected_routes() -> None:
    paths = {route.path for route in app.routes}

    assert "/" in paths
    assert "/health" in paths
    assert "/api/run" in paths
    assert "/api/reviews" in paths
    assert "/api/emergency-stop" in paths


def test_business_cycle_contains_phase24_and_validation() -> None:
    names = [name for name, _command in BUSINESS_CYCLE]

    assert names[0] == "runtime_preflight"
    assert "autonomic_business_pipeline" in names
    assert names[-1] == "contract_validation"


def test_business_cycle_commands_are_project_scoped() -> None:
    for _name, command in BUSINESS_CYCLE:
        joined = " ".join(command)
        assert "src" in joined
        assert "aigc.py" in joined or "phase24_autonomic_business_pipeline.py" in joined
