from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from occupational.ingestion_pipeline import OccupationalIngestionPipeline
from occupational.knowledge_ingestion import ConceptKind, SourceAuthority
from occupational.procurement_relay import OccupationalProcurementRelay, SourceProcurementContract, receipt_json
from occupational.source_adapters import RawSourcePackage, adapter_for


ONET_MEMBER_KINDS: tuple[tuple[str, ConceptKind], ...] = (
    ("occupation data", ConceptKind.OCCUPATION),
    ("alternate titles", ConceptKind.TITLE),
    ("task statements", ConceptKind.TASK),
    ("skills", ConceptKind.SKILL),
    ("knowledge", ConceptKind.KNOWLEDGE),
    ("abilities", ConceptKind.ABILITY),
    ("work styles", ConceptKind.WORK_STYLE),
    ("work activities", ConceptKind.WORK_ACTIVITY),
    ("work context", ConceptKind.WORK_CONTEXT),
    ("technology skills", ConceptKind.TECHNOLOGY),
    ("tools used", ConceptKind.TECHNOLOGY),
)


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


def _kind_for_onet_member(name: str) -> ConceptKind | None:
    lowered = Path(name).stem.lower().replace("_", " ")
    for marker, kind in ONET_MEMBER_KINDS:
        if marker in lowered:
            return kind
    return None


def _onet_member_packages(package: RawSourcePackage) -> tuple[RawSourcePackage, ...]:
    members: list[RawSourcePackage] = []
    with zipfile.ZipFile(io.BytesIO(package.payload)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            kind = _kind_for_onet_member(info.filename)
            if kind is None:
                continue
            payload = archive.read(info)
            digest = hashlib.sha256(payload).hexdigest()
            members.append(
                RawSourcePackage(
                    authority=SourceAuthority.ONET,
                    version=package.version,
                    dataset_name=Path(info.filename).stem,
                    concept_kind=kind,
                    source_uri=f"{package.source_uri}#{info.filename}",
                    payload=payload,
                    expected_sha256=digest,
                    media_type="text/csv",
                )
            )
    return tuple(members)


def _normalization_packages(package: RawSourcePackage) -> tuple[RawSourcePackage, ...]:
    if package.authority == SourceAuthority.ONET and package.media_type in {"application/zip", "application/x-zip-compressed"}:
        return _onet_member_packages(package)
    if package.media_type not in {"text/csv", "text/plain", "application/octet-stream"}:
        return ()
    return (package,)


def _write_blocked_normalization(receipt_root: Path, base_name: str, package: RawSourcePackage) -> None:
    record = {
        "receipt_type": "OCCUPATIONAL_SOURCE_DRY_RUN",
        "authority": package.authority.value,
        "version": package.version,
        "dataset_name": package.dataset_name,
        "source_uri": package.source_uri,
        "source_sha256": package.actual_sha256,
        "mode": "DRY_RUN",
        "result": "BLOCKED",
        "reason": f"no normalizer currently supports media type {package.media_type}",
        "canonical_registry_mutated": False,
    }
    (receipt_root / f"{base_name}.dry_run.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")


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
    dry_runs = 0

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

        packages = _normalization_packages(result.package)
        if not packages:
            blocked += 1
            _write_blocked_normalization(receipt_root, base_name, result.package)
            print(f"NORMALIZATION_BLOCKED {contract.authority.value} {contract.dataset_kind}: unsupported media={result.package.media_type}")
            continue

        adapter = adapter_for(contract.authority)
        for member_index, package in enumerate(packages, start=1):
            member_name = f"{base_name}.{member_index:02d}_{package.dataset_name}".replace("/", "_")
            try:
                dry = pipeline.dry_run(package, adapter, receipt_id=f"local:{member_name}:dry-run")
            except (UnicodeDecodeError, ValueError, csv.Error) as exc:
                blocked += 1
                record = {
                    "receipt_type": "OCCUPATIONAL_SOURCE_DRY_RUN",
                    "authority": package.authority.value,
                    "version": package.version,
                    "dataset_name": package.dataset_name,
                    "source_uri": package.source_uri,
                    "source_sha256": package.actual_sha256,
                    "mode": "DRY_RUN",
                    "result": "BLOCKED",
                    "reason": str(exc),
                    "canonical_registry_mutated": False,
                }
                (receipt_root / f"{member_name}.dry_run.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
                print(f"NORMALIZATION_BLOCKED {package.authority.value} {package.dataset_name}: {exc}")
                continue
            dry_runs += 1
            dry_path = receipt_root / f"{member_name}.dry_run.json"
            dry_path.write_text(json.dumps(dry.model_dump(mode="json"), sort_keys=True, indent=2) + "\n", encoding="utf-8")
            print(
                f"DRY_RUN {package.authority.value} {package.dataset_name}: {dry.result}; "
                f"records={dry.normalized_record_count}; new={dry.diff.new_concepts}; conflicts={dry.diff.conflicting_concepts}"
            )
            if dry.result != "PASS":
                blocked += 1

    summary = {
        "commission": "WC_AIGC_OCCUPATIONAL_TAXONOMY_ACQUISITION_001",
        "canonical_registry_mutated": False,
        "contracts_attempted": len(contracts),
        "dry_runs_completed": dry_runs,
        "blocked_or_failed": blocked,
        "admission_requested": False,
    }
    (receipt_root / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0 if blocked == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
