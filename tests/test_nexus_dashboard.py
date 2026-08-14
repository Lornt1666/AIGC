from src.domain.nexus.contracts import WorkOrder
from src.webapp.nexus_dashboard import build_nexus_dashboard_snapshot


def test_dashboard_exposes_integrated_brain_without_execution_authority() -> None:
    work_order = WorkOrder(
        work_order_id="WO-DASH001",
        objective="Integrate AIGC Nexus V1",
        domain_tags=("software", "security", "dashboard"),
    )
    snapshot = build_nexus_dashboard_snapshot(work_order=work_order)

    assert snapshot["product"] == "AIGC NEXUS V1"
    assert snapshot["system"]["toolbroker"] == "GOVERNED_DEFAULT_DENY"
    assert snapshot["system"]["external_execution"] == "GOVERNED_AVAILABLE_DEFAULT_DENY"
    assert snapshot["system"]["provider_runtime"] == "LIVE_FOUNDATION_AVAILABLE_NOT_AUTO_CONNECTED"
    assert snapshot["system"]["durable_runtime_controls"] == "POSTGRES_AVAILABLE_NOT_AUTO_CONNECTED"
    assert snapshot["system"]["memory_adapter"] == "SQLITE_AVAILABLE_NOT_AUTO_CONNECTED"
    assert snapshot["artifact_canvas"]["write_through_enabled"] is False
    assert "VERIFIER" in snapshot["run_graph"]
    assert "GOVERNANCE" in snapshot["run_graph"]
    assert "GOVERNED_LIVE_PROVIDER_RUNTIME" in snapshot["available_runtime_surfaces"]
    assert "POSTGRES_RUNTIME_CONTROLS" in snapshot["available_runtime_surfaces"]
    assert {item["specialist_id"] for item in snapshot["specialists"]} >= {
        "SPC-PYTHON",
        "SPC-SECURITY",
        "SPC-UX",
    }
