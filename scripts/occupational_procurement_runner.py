from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from occupational.ingestion_pipeline import OccupationalIngestionPipeline
from occupational.procurement_relay import OccupationalProcurementRelay, SourceProcurementContract, receipt_json
from occupational.source_adapters import adapter_for


def _load_contracts(path: Path) -> list[SourceProcurementContract]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("contracts", payload)
    if isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, list):
        raise ValueError("contract file must contain a list or {'contracts': [...]} structure")
    return [SourceProcurementContract.model_validate(item) for item in raw]


def _select(contracts: list[SourceProcurementContract], authorities: set[str] | None) -> list[SourceProcurementContract]:
    if not authorities:
        return contracts
    wanted = {value.upper() for value in authorities}
    selected = [contract for contract in contracts if contract.authority.value.upper() in wanted]
    missing = wanted - {contract.authority.value.upper() for contract in selected}
    if missing:
        raise ValueError(f"no procurement contract for: {', '.join(sorted(missing))}")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the sealed AIGC occupational taxonomy acquisition commission locally.")
    parser.add_argument("--contracts", default=str(REPO_ROOT / "config" / "aigc_occupational_procurement_contracts.v1.json"))
    parser.add_argument("--quarantine", default=str(REPO_ROOT / "data" / "occupational" / "quarantine"))
    parser.add_argument("--receipts", default=str(REPO_ROOT / "evidence" / "occupational_procurement" / "local"))
    parser.add_argument("--authority", action="append", help="Limit acquisition to one or more authorities, e.g. NOC or ONET")
    parser.add_argument("--observed-version", action="append", default=[], help="AUTHORITY=VERSION evidence from an official version probe")
    args = parser.parse_args()

    version_map: dict[str, str] = {}
    for pair in args.observed_version:
        if "=" not in pair:
            parser.error("--observed-version must use AUTHORITY=VERSION")
        authority, version = pair.split("=", 1)
        version_map[authority.upper()] = version

    contracts = _select(_load_contracts(Path(args.contracts)), set(args.authority or []))
    quarantine = Path(args.quarantine)
    receipt_root = Path(args.receipts)
    receipt_root.mkdir(parents=True, exist_ok=True)

    relay = OccupationalProcurementRelay(quarantine)
    pipeline = OccupationalIngestionPipeline()
    blocked = 0

    for index, contract in enumerate(contracts, start=1):
        observed_version = version_map.get(contract.authority.value.upper())
        result = relay.procure(contract, observed_version=observed_version)
        base_name = f"{index:02d}_{contract.authority.value}_{contract.version}_{contract.dataset_kind}".replace("/", "_")
        acquisition_path = receipt_root / f"{base_name}.acquisition.json"
        acquisition_path.write_text(receipt_json(result.receipt) + "\n", encoding="utf-8")

        if result.package is None:
            blocked += 1
            print(f"BLOCKED {contract.authority.value} {contract.dataset_kind}: {result.receipt.detail}")
            continue

        adapter = adapter_for(contract.authority)
        dry = pipeline.dry_run(result.package, adapter, receipt_id=f"local:{base_name}:dry-run")
        dry_path = receipt_root / f"{base_name}.dry_run.json"
        dry_path.write_text(json.dumps(dry.model_dump(mode="json"), sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(
            f"DRY_RUN {contract.authority.value} {contract.dataset_kind}: {dry.result}; "
            f"records={dry.normalized_record_count}; new={dry.diff.new_concepts}; conflicts={dry.diff.conflicting_concepts}"
        )
        if dry.result != "PASS":
            blocked += 1

    summary = {
        "commission": "WC_AIGC_OCCUPATIONAL_TAXONOMY_ACQUISITION_001",
        "canonical_registry_mutated": False,
        "contracts_attempted": len(contracts),
        "blocked_or_failed": blocked,
        "admission_requested": False,
    }
    (receipt_root / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0 if blocked == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
