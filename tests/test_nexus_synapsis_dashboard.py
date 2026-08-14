from src.core.nexus.odse import synthesize_strategy
from src.domain.nexus.contracts import WorkOrder
from src.domain.nexus.odse import KnowledgePillar
from src.webapp.nexus_dashboard import build_nexus_dashboard_snapshot


def test_dashboard_exposes_odse_memory_and_evidence_without_authority() -> None:
    work_order = WorkOrder(
        work_order_id="WO-SYNAPSIS1",
        objective="Integrate governed memory and evidence into Nexus",
        domain_tags=("software", "security", "dashboard"),
    )
    strategy = synthesize_strategy(
        work_order=work_order,
        academic=KnowledgePillar(pillar="ACADEMIC", findings=("Academic input",), evidence_refs=("EVD-DEMO0001",)),
        disciplinary=KnowledgePillar(pillar="DISCIPLINARY", findings=("Standards input",), evidence_refs=("EVD-DEMO0001",)),
        occupational=KnowledgePillar(pillar="OCCUPATIONAL", findings=("Practice input",), evidence_refs=("EVD-DEMO0001",)),
        next_gen=KnowledgePillar(pillar="NEXT_GEN", findings=("Technology input",), evidence_refs=("EVD-DEMO0001",)),
    )
    snapshot = build_nexus_dashboard_snapshot(
        work_order=work_order,
        strategy=strategy,
        memory_records=({"memory_id": "MEM-DEMO0001", "active": True},),
        memory_candidates=({"candidate_id": "MEMC-DEMO001", "status": "PENDING"},),
        evidence_records=({"evidence_id": "EVD-DEMO0001", "integrity_state": "verified"},),
    )

    assert snapshot["system"]["odse"] == "ACTIVE_PROVIDER_FREE"
    assert snapshot["synapsis"]["strategy_id"] == strategy.strategy_id
    assert snapshot["memory"]["grants_authority"] is False
    assert snapshot["evidence"]["grants_authority"] is False
    assert snapshot["artifact_canvas"]["write_through_enabled"] is False
    assert "ODSE" in snapshot["run_graph"]
    assert "MEMORY_ADMISSION" in snapshot["run_graph"]
