from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .knowledge_ingestion import ConceptKind, SourceAuthority
from .source_adapters import RawSourcePackage


class AcquisitionMode(str):
    DIRECT_FILE = "DIRECT_FILE"
    API_PAGINATED = "API_PAGINATED"
    OFFICIAL_ARCHIVE = "OFFICIAL_ARCHIVE"
    USER_SUPPLIED_OFFICIAL_FILE = "USER_SUPPLIED_OFFICIAL_FILE"
    MANUAL_ACQUISITION_REQUIRED = "MANUAL_ACQUISITION_REQUIRED"


class ProcurementState(str):
    DISCOVERED = "DISCOVERED"
    SOURCE_VERIFIED = "SOURCE_VERIFIED"
    ACQUIRING = "ACQUIRING"
    ACQUIRED = "ACQUIRED"
    HASH_VERIFIED = "HASH_VERIFIED"
    QUARANTINED = "QUARANTINED"
    NORMALIZED = "NORMALIZED"
    DRY_RUN_COMPLETE = "DRY_RUN_COMPLETE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ADMISSION_ELIGIBLE = "ADMISSION_ELIGIBLE"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    ACQUISITION_BLOCKED = "ACQUISITION_BLOCKED"


class SourceProcurementContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authority: SourceAuthority
    version: str = Field(min_length=1)
    dataset_kind: str = Field(min_length=1)
    acquisition_mode: Literal[
        "DIRECT_FILE", "API_PAGINATED", "OFFICIAL_ARCHIVE", "USER_SUPPLIED_OFFICIAL_FILE", "MANUAL_ACQUISITION_REQUIRED"
    ]
    endpoint: str
    allowed_hosts: tuple[str, ...]
    concept_kind: ConceptKind
    expected_media_types: tuple[str, ...] = ()
    expected_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    max_download_bytes: int = Field(default=200_000_000, gt=0)
    max_archive_uncompressed_bytes: int = Field(default=1_000_000_000, gt=0)
    note: str | None = None
    canonical_commit_allowed: Literal[False] = False

    @model_validator(mode="after")
    def secure_endpoint(self) -> "SourceProcurementContract":
        parsed = urllib.parse.urlparse(self.endpoint)
        if parsed.scheme != "https":
            raise ValueError("procurement endpoint must use HTTPS")
        if not parsed.hostname or parsed.hostname.lower() not in {h.lower() for h in self.allowed_hosts}:
            raise ValueError("endpoint host is not allowlisted")
        return self


class AcquisitionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_type: Literal["OCCUPATIONAL_SOURCE_ACQUISITION"] = "OCCUPATIONAL_SOURCE_ACQUISITION"
    authority: SourceAuthority
    requested_version: str
    observed_version: str | None = None
    dataset_kind: str
    source_url: str
    final_url: str | None = None
    acquisition_mode: str
    http_status: int | None = None
    content_type: str | None = None
    byte_size: int | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    state: str
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quarantine_path: str | None = None
    canonical_registry_mutated: Literal[False] = False
    detail: str | None = None


@dataclass(frozen=True)
class ProcurementResult:
    receipt: AcquisitionReceipt
    package: RawSourcePackage | None


class ArchiveGuard:
    @staticmethod
    def validate_zip(path: Path, *, max_uncompressed_bytes: int) -> None:
        total = 0
        with zipfile.ZipFile(path) as zf:
            for member in zf.infolist():
                normalized = Path(member.filename)
                if normalized.is_absolute() or ".." in normalized.parts:
                    raise ValueError("archive path traversal detected")
                if member.flag_bits & 0x1:
                    raise ValueError("encrypted archive entries are not allowed")
                total += member.file_size
                if total > max_uncompressed_bytes:
                    raise ValueError("archive expansion limit exceeded")


class OccupationalProcurementRelay:
    """Acquire official occupational source bytes without mutating the canonical registry."""

    def __init__(self, quarantine_root: str | Path) -> None:
        self.quarantine_root = Path(quarantine_root)

    @staticmethod
    def _host_allowed(url: str, allowed_hosts: Iterable[str]) -> bool:
        host = urllib.parse.urlparse(url).hostname
        return bool(host and host.lower() in {h.lower() for h in allowed_hosts})

    def procure(self, contract: SourceProcurementContract, *, observed_version: str | None = None) -> ProcurementResult:
        if observed_version is not None and observed_version != contract.version:
            return ProcurementResult(
                AcquisitionReceipt(
                    authority=contract.authority,
                    requested_version=contract.version,
                    observed_version=observed_version,
                    dataset_kind=contract.dataset_kind,
                    source_url=contract.endpoint,
                    acquisition_mode=contract.acquisition_mode,
                    state=ProcurementState.VERSION_MISMATCH,
                    detail="observed source version does not match sealed requested version",
                ),
                None,
            )

        request = urllib.request.Request(contract.endpoint, headers={"User-Agent": "AIGC-OccupationalProcurementRelay/1.0"})
        temp_path: Path | None = None
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                final_url = response.geturl()
                if not self._host_allowed(final_url, contract.allowed_hosts):
                    raise ValueError("redirect escaped allowlisted official hosts")
                status = getattr(response, "status", 200)
                content_type = response.headers.get_content_type()
                if contract.expected_media_types and content_type not in contract.expected_media_types:
                    raise ValueError(f"unexpected media type: {content_type}")

                hasher = hashlib.sha256()
                size = 0
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    temp_path = Path(tmp.name)
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > contract.max_download_bytes:
                            raise ValueError("download size limit exceeded")
                        hasher.update(chunk)
                        tmp.write(chunk)

            digest = hasher.hexdigest()
            if contract.expected_sha256 and digest != contract.expected_sha256:
                raise ValueError("source package checksum mismatch")

            if content_type in {"application/zip", "application/x-zip-compressed"} or contract.endpoint.lower().endswith(".zip"):
                ArchiveGuard.validate_zip(temp_path, max_uncompressed_bytes=contract.max_archive_uncompressed_bytes)

            destination = self.quarantine_root / "sha256" / digest[:2] / digest
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                temp_path.unlink(missing_ok=True)
            else:
                os.replace(temp_path, destination)
            temp_path = None

            payload = destination.read_bytes()
            package = RawSourcePackage(
                authority=contract.authority,
                version=contract.version,
                dataset_name=contract.dataset_kind,
                concept_kind=contract.concept_kind,
                source_uri=final_url,
                payload=payload,
                expected_sha256=digest,
                media_type=content_type,
            )
            receipt = AcquisitionReceipt(
                authority=contract.authority,
                requested_version=contract.version,
                observed_version=observed_version or contract.version,
                dataset_kind=contract.dataset_kind,
                source_url=contract.endpoint,
                final_url=final_url,
                acquisition_mode=contract.acquisition_mode,
                http_status=status,
                content_type=content_type,
                byte_size=size,
                sha256=digest,
                state=ProcurementState.QUARANTINED,
                quarantine_path=str(destination),
            )
            return ProcurementResult(receipt, package)
        except (urllib.error.URLError, OSError, ValueError, zipfile.BadZipFile) as exc:
            return ProcurementResult(
                AcquisitionReceipt(
                    authority=contract.authority,
                    requested_version=contract.version,
                    observed_version=observed_version,
                    dataset_kind=contract.dataset_kind,
                    source_url=contract.endpoint,
                    acquisition_mode=contract.acquisition_mode,
                    state=ProcurementState.ACQUISITION_BLOCKED,
                    detail=str(exc),
                ),
                None,
            )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


def receipt_json(receipt: AcquisitionReceipt) -> str:
    return json.dumps(receipt.model_dump(mode="json"), sort_keys=True, indent=2)
