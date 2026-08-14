from __future__ import annotations

import importlib.util
from pathlib import Path

from occupational.knowledge_ingestion import ConceptKind, SourceAuthority
from occupational.procurement_relay import SourceProcurementContract


def _load_runner_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "occupational_procurement_runner.py"
    spec = importlib.util.spec_from_file_location("occupational_procurement_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_select_rejects_unknown_authority() -> None:
    runner = _load_runner_module()
    contracts = [
        SourceProcurementContract(
            authority=SourceAuthority.NOC,
            version="2021.0",
            dataset_kind="STRUCTURE",
            acquisition_mode="DIRECT_FILE",
            endpoint="https://www.statcan.gc.ca/example.csv",
            allowed_hosts=("www.statcan.gc.ca",),
            concept_kind=ConceptKind.OCCUPATION,
        )
    ]
    try:
        runner._select(contracts, {"ONET"})
    except ValueError as exc:
        assert "no procurement contract" in str(exc)
    else:
        raise AssertionError("unknown authority must fail closed")


def test_select_preserves_requested_contract() -> None:
    runner = _load_runner_module()
    contract = SourceProcurementContract(
        authority=SourceAuthority.NOC,
        version="2021.0",
        dataset_kind="STRUCTURE",
        acquisition_mode="DIRECT_FILE",
        endpoint="https://www.statcan.gc.ca/example.csv",
        allowed_hosts=("www.statcan.gc.ca",),
        concept_kind=ConceptKind.OCCUPATION,
    )
    assert runner._select([contract], {"NOC"}) == [contract]
