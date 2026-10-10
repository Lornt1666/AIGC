"""Production artifact persistence backed by private versioned S3 and PostgreSQL.

The PostgreSQL metadata row is authoritative. S3 objects written before a failed
metadata commit are harmless orphans and must be reconciled by a separate sweeper;
they are never authoritative merely because they exist in S3.

This module deliberately does not provision cloud resources or construct credentials.
Callers must supply a configured psycopg pool and S3-compatible client.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Protocol

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class ArtifactStoreError(RuntimeError):
    """Base class for fail-closed persistence errors."""


class ArtifactConflict(ArtifactStoreError):
    """Idempotency key or expected-current-version conflict."""


class ArtifactIntegrityError(ArtifactStoreError):
    """Reference, metadata, or bytes fail integrity validation."""


class ArtifactNotFound(ArtifactStoreError):
    """Authoritative metadata or the referenced S3 object is missing."""


class ArtifactUnavailable(ArtifactStoreError):
    """PostgreSQL or S3 is denied, unavailable, or returned an invalid response."""


@dataclass(frozen=True)
class ArtifactRef:
    key: str
    version_id: str
    sha256: str
    media_type: str
    schema_version: str
    provenance: str
    operation_id: str


class ConnectionPool(Protocol):
    def connection(self): ...


class S3Client(Protocol):
    def put_object(self, **kwargs: Any) -> dict[str, Any]: ...
    def get_object(self, **kwargs: Any) -> dict[str, Any]: ...


class S3PostgresArtifactStore:
    """Shared durable store. S3 bucket versioning must already be enabled.

    The database row is the source of truth; callers must not authorize from an
    S3 object or a stale local cache. S3 AccessDenied, timeouts, absent VersionId,
    and database failures are surfaced as errors so callers can fail closed.
    """

    durable = True

    def __init__(self, *, pool: ConnectionPool, s3_client: S3Client,
                 bucket: str, object_prefix: str = "aigc-artifacts"):
        if not bucket or not bucket.strip():
            raise ValueError("bucket is required")
        prefix = object_prefix.strip("/")
        if not prefix or ".." in prefix.split("/"):
            raise ValueError("object_prefix must be a non-empty safe prefix")
        self.pool = pool
        self.s3 = s3_client
        self.bucket = bucket
        self.prefix = prefix

    def put(self, *, key: str, content: bytes, media_type: str,
            schema_version: str, provenance: str, operation_id: str,
            expected_current_version_id: str | None = None) -> ArtifactRef:
        fields = {
            "key": key.strip(), "media_type": media_type.strip(),
            "schema_version": schema_version.strip(), "provenance": provenance.strip(),
            "operation_id": operation_id.strip(),
        }
        if not all(fields.values()):
            raise ValueError("key, media_type, schema_version, provenance, and operation_id are required")
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")
        digest = hashlib.sha256(content).hexdigest()
        object_key = f"{self.prefix}/{digest}"

        try:
            with self.pool.connection() as conn:
                with conn.transaction():
                    # Serialize updates to the same logical artifact identity across workers.
                    # Lock operation IDs globally before logical keys to make cross-key retries race-safe.
                    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("operation:" + fields["operation_id"],))
                    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("artifact:" + fields["key"],))
                    prior = conn.execute(
                        """SELECT logical_key, version_id, sha256, media_type, schema_version,
                                  provenance, operation_id
                           FROM aigc_artifact_metadata WHERE operation_id = %s""",
                        (fields["operation_id"],),
                    ).fetchone()
                    if prior:
                        ref = self._row_to_ref(prior)
                        expected = (fields["key"], digest, fields["media_type"],
                                    fields["schema_version"], fields["provenance"])
                        actual = (ref.key, ref.sha256, ref.media_type, ref.schema_version, ref.provenance)
                        if actual != expected:
                            raise ArtifactConflict("operation_id reused with conflicting artifact data")
                        return ref

                    current = conn.execute(
                        """SELECT version_id FROM aigc_artifact_metadata
                           WHERE logical_key = %s ORDER BY created_at DESC, id DESC LIMIT 1""",
                        (fields["key"],),
                    ).fetchone()
                    current_version = current[0] if current else None
                    if current_version != expected_current_version_id:
                        raise ArtifactConflict("stale artifact write: expected current version does not match")

                    try:
                        response = self.s3.put_object(
                            Bucket=self.bucket, Key=object_key, Body=content,
                            ContentType=fields["media_type"],
                            Metadata={"sha256": digest, "schema-version": fields["schema_version"]},
                        )
                    except Exception as exc:
                        raise ArtifactUnavailable("S3 write failed; artifact was not committed") from exc
                    version_id = response.get("VersionId")
                    if not version_id or version_id == "null":
                        raise ArtifactUnavailable("S3 bucket versioning is not active; refusing unversioned artifact")
                    ref = ArtifactRef(version_id=version_id, sha256=digest, **fields)
                    conn.execute(
                        """INSERT INTO aigc_artifact_metadata
                           (logical_key, version_id, object_key, sha256, media_type,
                            schema_version, provenance, operation_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (ref.key, ref.version_id, object_key, ref.sha256, ref.media_type,
                         ref.schema_version, ref.provenance, ref.operation_id),
                    )
                    return ref
        except (ArtifactConflict, ArtifactUnavailable):
            raise
        except Exception as exc:
            raise ArtifactUnavailable("PostgreSQL metadata transaction failed; do not authorize from uncommitted S3 objects") from exc

    def get(self, ref: ArtifactRef) -> bytes:
        if not _SHA256.fullmatch(ref.sha256) or not ref.version_id or ref.version_id == "null":
            raise ArtifactIntegrityError("invalid immutable artifact reference")
        try:
            with self.pool.connection() as conn:
                row = conn.execute(
                    """SELECT logical_key, version_id, object_key, sha256, media_type,
                              schema_version, provenance, operation_id
                       FROM aigc_artifact_metadata WHERE operation_id = %s""",
                    (ref.operation_id,),
                ).fetchone()
        except Exception as exc:
            raise ArtifactUnavailable("authoritative artifact metadata is unavailable") from exc
        if not row:
            raise ArtifactNotFound("artifact metadata is missing")
        stored = ArtifactRef(key=row[0], version_id=row[1], sha256=row[3],
                             media_type=row[4], schema_version=row[5],
                             provenance=row[6], operation_id=row[7])
        if stored != ref:
            raise ArtifactIntegrityError("reference does not match authoritative metadata")
        if row[3] != ref.sha256:
            raise ArtifactIntegrityError("metadata digest mismatch")
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=row[2], VersionId=ref.version_id)
            body = response["Body"].read()
        except Exception as exc:
            raise ArtifactUnavailable("versioned S3 object is denied or unavailable") from exc
        if hashlib.sha256(body).hexdigest() != ref.sha256:
            raise ArtifactIntegrityError("S3 bytes do not match authoritative SHA-256")
        return body

    @staticmethod
    def _row_to_ref(row: Any) -> ArtifactRef:
        # SELECT order: logical_key, version_id, sha256, media_type, schema_version,
        # provenance, operation_id.
        return ArtifactRef(key=row[0], version_id=row[1], sha256=row[2],
                           media_type=row[3], schema_version=row[4],
                           provenance=row[5], operation_id=row[6])
