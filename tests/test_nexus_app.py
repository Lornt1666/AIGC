import pytest

from src.dashboard.nexus_app import build_demo_run
from src.domain.nexus.contracts import WorkOrder


EXACT_REVISION = "a" * 40


def test_nexus_visible_demo_is_deterministic_and_provider_free() -> None:
    work_order = WorkOrder(
        work_order_id="WO-NEXUSAPP1",
        objective="Exercise visible Nexus dashboard",
        domain_tags=("software", "security", "dashboard"),
    )
    first = build_demo_run(work_order, EXACT_REVISION)
    second = build_demo_run(work_order, EXACT_REVISION)

    assert first.run_id == second.run_id
    assert first.terminal_state == "accepted"
    assert first.external_action_performed is False
    assert all(decision.authority_source == "POLICY" for decision in first.decisions)


def test_nexus_visible_demo_rejects_floating_revision_names() -> None:
    work_order = WorkOrder(
        work_order_id="WO-NEXUSAPP2",
        objective="Reject mutable branch evidence",
        domain_tags=("software",),
    )
    with pytest.raises(ValueError, match="exact 40- or 64-character"):
        build_demo_run(work_order, "release/aigc-nexus-v1")
