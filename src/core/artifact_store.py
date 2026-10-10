"""Immutable artifact-store contract and development-only filesystem adapter.

Production storage must use a shared metadata database and a private, versioned object
store. This adapter is deliberately local-only and is not safe as a multi-replica
production authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Protocol


_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class ArtifactStoreError(RuntimeError):
    """Base class for artifact-store failures."""


class ArtifactConflict(ArtifactStoreError):
    """An operation ID or immutable artifact reference conflicts with existing data."""


class ArtifactIntegrityError(ArtifactStoreError):
    """Stored bytes do not match their recorded digest."""


class ArtifactNotFound(ArtifactStoreError):
    """The requested immutable artifact does not exist."""


@dataclass(frozen=True)
class ArtifactRef:
    """Immutable reference returned after an artifact is committed."""

    key: str
    version_id: str
    sha256: str
    media_type: str
    schema_version: str
    provenance: str
    operation_id: str


class ArtifactStore(Protocol):
    """Storage contract; implementations must preserve immutability and idempotency."""

    def put(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        schema_version: str,
        provenance: str,
        operation_id: str,
    ) -> ArtifactRef:
        """Persist bytes, returning the same reference for an identical retry."""

    def get(self, ref: ArtifactRef) -> bytes:
        """Read and verify bytes using the complete immutable reference."""


class LocalArtifactStore:
    """Content-addressed filesystem adapter for development and tests only.

    It stores blobs by SHA-256 and operation receipts separately. It never overwrites
    an existing operation receipt, and rejects reuse of an operation ID with different
    content or metadata. Do not use this adapter as production authorization state.
    """

    durable = False

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.blobs = self.root / "blobs"
        self.operations = self.root / "operations"
        self.blobs.mkdir(parents=True, exist_ok=True)
        self.operations.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        schema_version: str,
        provenance: str,
        operation_id: str,
    ) -> ArtifactRef:
        fields = {
            "key": key.strip(),
            "media_type": media_type.strip(),
            "schema_version": schema_version.strip(),
            "provenance": provenance.strip(),
            "operation_id": operation_id.strip(),
        }
        if not all(fields.values()):
            raise ValueError("key, media_type, schema_version, provenance, and operation_id are required")
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")
        digest = hashlib.sha256(content).hexdigest()
        operation_path = self.operations / (hashlib.sha256(fields["operation_id"].encode("utf-8")).hexdigest() + ".json")
        blob_path = self.blobs / digest

        receipt = {
            **fields,
            "version_id": digest,
            "sha256": digest,
        }
        if operation_path.exists():
            existing = json.loads(operation_path.read_text(encoding="utf-8"))
            if existing != receipt:
                raise ArtifactConflict("operation_id was already committed with different artifact data")
            self._verify_blob(blob_path, digest)
            return ArtifactRef(**existing)

        self._write_blob_if_absent(blob_path, content, digest)
        self._write_receipt_if_absent(operation_path, receipt)
        # A concurrent conflicting writer may win the receipt race; always verify it.
        existing = json.loads(operation_path.read_text(encoding="utf-8"))
        if existing != receipt:
            raise ArtifactConflict("operation_id was concurrently committed with different artifact data")
        return ArtifactRef(**existing)

    def get(self, ref: ArtifactRef) -> bytes:
        if not _SHA256.fullmatch(ref.sha256) or ref.version_id != ref.sha256:
            raise ArtifactIntegrityError("artifact reference has an invalid digest or version")
        if not ref.operation_id:
            raise ArtifactIntegrityError("artifact reference is missing its operation ID")
        operation_path = self.operations / (
            hashlib.sha256(ref.operation_id.encode("utf-8")).hexdigest() + ".json"
        )
        try:
            receipt = json.loads(operation_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ArtifactNotFound("artifact operation receipt is missing") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactIntegrityError("artifact operation receipt is unreadable") from exc
        if receipt != asdict(ref):
            raise ArtifactIntegrityError("artifact reference metadata does not match its committed receipt")
        path = self.blobs / ref.sha256
        if not path.is_file():
            raise ArtifactNotFound("artifact blob is missing")
        return self._verify_blob(path, ref.sha256)

    @staticmethod
    def _verify_blob(path: Path, expected_digest: str) -> bytes:
        try:
            content = path.read_bytes()
        except FileNotFoundError as exc:
            raise ArtifactNotFound("artifact blob is missing") from exc
        if hashlib.sha256(content).hexdigest() != expected_digest:
            raise ArtifactIntegrityError("artifact blob digest mismatch")
        return content

    @staticmethod
    def _write_blob_if_absent(path: Path, content: bytes, digest: str) -> None:
        if path.exists():
            LocalArtifactStore._verify_blob(path, digest)
            return
        LocalArtifactStore._atomic_create(path, content)

    @staticmethod
    def _write_receipt_if_absent(path: Path, receipt: dict[str, str]) -> None:
        encoded = (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        LocalArtifactStore._atomic_create(path, encoded)

    @staticmethod
    def _atomic_create(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".artifact-tmp-", dir=path.parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp_path, path)
            except FileExistsError:
                pass
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
