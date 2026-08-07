from src.dashboard.nexus_app import build_demo_run
from src.domain.nexus.contracts import WorkOrder


def test_nexus_visible_demo_is_deterministic_and_provider_free() -> None:
    work_order = WorkOrder(
        work_order_id="WO-NEXUSAPP1",
        objective="Exercise visible Nexus dashboard",
        domain_tags=("software", "security", "dashboard"),
    )
    first = build_demo_run(work_order, "test-revision")
    second = build_demo_run(work_order, "test-revision")

    assert first.run_id == second.run_id
    assert first.terminal_state == "accepted"
    assert first.external_action_performed is False
    assert all(decision.authority_source == "POLICY" for decision in first.decisions)
