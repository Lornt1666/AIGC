"""S3 Object Lock evidence archive adapter.

Uses a pre-provisioned, separately administered bucket with Object Lock enabled.
Never creates buckets or changes bucket policy. Production use requires an
independent operator to configure retention, IAM, logging, and recovery.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

BINDINGS = ("repository", "commit_sha", "tree_sha", "policy_digest", "invocation_id")


def archive_and_verify(s3_client: Any, bucket: str, key: str, bundle: bytes,
                       bindings: dict[str, str], retain_until: datetime) -> dict[str, Any]:
    if not bucket.strip() or not key.strip() or not isinstance(bundle, bytes) or not bundle:
        raise ValueError("bucket, key, and non-empty bytes bundle are required")
    missing = [field for field in BINDINGS if not bindings.get(field)]
    if missing:
        raise ValueError("missing exact-version bindings: " + ", ".join(missing))
    if len(bindings["commit_sha"]) != 40 or len(bindings["tree_sha"]) != 40:
        raise ValueError("commit_sha and tree_sha must be full 40-character Git object IDs")
    if retain_until.tzinfo is None or retain_until <= datetime.now(timezone.utc):
        raise ValueError("retain_until must be a future timezone-aware datetime")

    digest = hashlib.sha256(bundle).hexdigest()
    metadata = {**bindings, "sha256": digest, "schema_version": "1.0"}
    response = s3_client.put_object(
        Bucket=bucket, Key=key, Body=bundle, ContentType="application/octet-stream",
        Metadata=metadata, ObjectLockMode="COMPLIANCE",
        ObjectLockRetainUntilDate=retain_until.astimezone(timezone.utc),
    )
    version_id = response.get("VersionId")
    if not version_id or version_id == "null":
        raise RuntimeError("archive write did not return an immutable object version ID")

    head = s3_client.head_object(Bucket=bucket, Key=key, VersionId=version_id)
    if head.get("VersionId") != version_id:
        raise RuntimeError("remote archive version ID mismatch")
    if head.get("ObjectLockMode") != "COMPLIANCE":
        raise RuntimeError("remote object is not protected by COMPLIANCE retention")
    remote_retention = head.get("ObjectLockRetainUntilDate")
    if not isinstance(remote_retention, datetime) or remote_retention < retain_until:
        raise RuntimeError("remote retention date does not satisfy requested minimum")
    if head.get("ContentLength") != len(bundle):
        raise RuntimeError("remote content length mismatch")
    remote_metadata = head.get("Metadata", {})
    for field, value in metadata.items():
        if remote_metadata.get(field) != value:
            raise RuntimeError("remote metadata mismatch: " + field)

    fetched = s3_client.get_object(Bucket=bucket, Key=key, VersionId=version_id)
    body = fetched.get("Body")
    if body is None:
        raise RuntimeError("remote archive read returned no body")
    data = body.read()
    if hashlib.sha256(data).hexdigest() != digest or data != bundle:
        raise RuntimeError("remote archive content digest mismatch")
    return {
        "status": "ARCHIVED_AND_VERIFIED",
        "bucket": bucket,
        "key": key,
        "version_id": version_id,
        "object_lock_mode": "COMPLIANCE",
        "retain_until_utc": remote_retention.astimezone(timezone.utc).isoformat(),
        "sha256": digest,
        **bindings,
        "remote_readback_verified": True,
    }
