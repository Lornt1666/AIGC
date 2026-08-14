from __future__ import annotations

from pathlib import Path

import pytest

from occupational.knowledge_ingestion import ConceptKind, SourceAuthority
from occupational.procurement_relay import (
    ArchiveGuard,
    OccupationalProcurementRelay,
    ProcurementState,
    SourceProcurementContract,
)


def contract(**overrides):
    values = {
        "authority": SourceAuthority.NOC,
        "version": "2021.0",
        "dataset_kind": "CLASSIFICATION_STRUCTURE",
        "acquisition_mode": "DIRECT_FILE",
        "endpoint": "https://www.statcan.gc.ca/noc.csv",
        "allowed_hosts": ("www.statcan.gc.ca",),
        "concept_kind": ConceptKind.OCCUPATION,
        "expected_media_types": ("text/csv",),
    }
    values.update(overrides)
    return SourceProcurementContract(**values)


def test_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        contract(endpoint="http://www.statcan.gc.ca/noc.csv")


def test_requires_allowlisted_host() -> None:
    with pytest.raises(ValueError, match="allowlisted"):
        contract(endpoint="https://evil.example/noc.csv")


def test_canonical_commit_cannot_be_enabled() -> None:
    with pytest.raises(Exception):
        contract(canonical_commit_allowed=True)


def test_version_mismatch_fails_before_network(tmp_path: Path) -> None:
    relay = OccupationalProcurementRelay(tmp_path)
    result = relay.procure(contract(), observed_version="2026.0")
    assert result.receipt.state == ProcurementState.VERSION_MISMATCH
    assert result.package is None


def test_archive_guard_rejects_path_traversal(tmp_path: Path) -> None:
    import zipfile

    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("../escape.txt", "bad")
    with pytest.raises(ValueError, match="path traversal"):
        ArchiveGuard.validate_zip(path, max_uncompressed_bytes=1024)


def test_archive_guard_rejects_expansion_limit(tmp_path: Path) -> None:
    import zipfile

    path = tmp_path / "large.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("large.txt", "x" * 2048)
    with pytest.raises(ValueError, match="expansion limit"):
        ArchiveGuard.validate_zip(path, max_uncompressed_bytes=1024)
