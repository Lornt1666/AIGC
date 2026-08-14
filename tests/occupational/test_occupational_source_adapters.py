from __future__ import annotations

import hashlib

import pytest

from occupational.ingestion_pipeline import InMemoryRegistryStore, OccupationalIngestionPipeline
from occupational.knowledge_ingestion import ConceptKind, SourceAuthority
from occupational.source_adapters import IscoAdapter, RawSourcePackage, adapter_for


def package(payload: bytes, *, version: str = "ISCO-08") -> RawSourcePackage:
    return RawSourcePackage(
        authority=SourceAuthority.ISCO,
        version=version,
        source_uri="https://example.invalid/isco.csv",
        payload=payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )


def test_adapter_rejects_checksum_mismatch() -> None:
    p = RawSourcePackage(
        authority=SourceAuthority.ISCO,
        version="ISCO-08",
        source_uri="https://example.invalid/isco.csv",
        payload=b"code,title\n2512,Software developers\n",
        expected_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        IscoAdapter().normalize(p)


def test_isco_normalizes_to_occupation() -> None:
    records = IscoAdapter().normalize(package(b"code,title,level\n2512,Software developers,unit_group\n"))
    assert len(records) == 1
    assert records[0].kind == ConceptKind.OCCUPATION
    assert records[0].source_id == "2512"
    assert records[0].metadata["classification_level"] == "unit_group"


def test_dry_run_never_persists() -> None:
    store = InMemoryRegistryStore()
    pipeline = OccupationalIngestionPipeline(store)
    p = package(b"code,title\n2512,Software developers\n")
    receipt = pipeline.dry_run(p, IscoAdapter(), receipt_id="r1")
    assert receipt.result == "PASS"
    assert receipt.imported_concept_count == 0
    assert receipt.diff.new_concepts == 1
    assert store.receipts == []


def test_commit_persists_only_after_clean_dry_run() -> None:
    store = InMemoryRegistryStore()
    pipeline = OccupationalIngestionPipeline(store)
    p = package(b"code,title\n2512,Software developers\n")
    receipt = pipeline.commit(p, IscoAdapter(), receipt_id="r2")
    assert receipt.result == "PASS"
    assert receipt.imported_concept_count == 1
    assert len(store.receipts) == 1


def test_same_version_conflict_is_blocked() -> None:
    store = InMemoryRegistryStore()
    pipeline = OccupationalIngestionPipeline(store)
    original = package(b"code,title\n2512,Software developers\n")
    assert pipeline.commit(original, IscoAdapter(), receipt_id="r3").result == "PASS"
    changed = package(b"code,title\n2512,Completely different occupation\n")
    receipt = pipeline.commit(changed, IscoAdapter(), receipt_id="r4")
    assert receipt.result == "BLOCKED"
    assert receipt.imported_concept_count == 0
    assert receipt.diff.conflicting_concepts == 1


def test_new_taxonomy_version_is_append_only_new_identity() -> None:
    store = InMemoryRegistryStore()
    pipeline = OccupationalIngestionPipeline(store)
    old = package(b"code,title\n2512,Software developers\n", version="ISCO-08")
    new = package(b"code,title\n2512,Software developers revised\n", version="ISCO-NEXT")
    assert pipeline.commit(old, IscoAdapter(), receipt_id="r5").result == "PASS"
    receipt = pipeline.commit(new, IscoAdapter(), receipt_id="r6")
    assert receipt.result == "PASS"
    assert receipt.imported_concept_count == 1


def test_adapter_registry_has_all_official_sources() -> None:
    for source in (SourceAuthority.ISCO, SourceAuthority.ESCO, SourceAuthority.NOC, SourceAuthority.SOC, SourceAuthority.ONET):
        assert adapter_for(source).authority == source
