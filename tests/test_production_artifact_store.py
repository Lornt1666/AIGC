from __future__ import annotations

import hashlib
import io

import pytest

from src.core.production_artifact_store import (
    ArtifactConflict, ArtifactIntegrityError, ArtifactUnavailable,
    S3PostgresArtifactStore,
)


class FakeTransaction:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class FakeConnection:
    def __init__(self, state): self.state = state
    def transaction(self): return FakeTransaction()
    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        if "pg_advisory_xact_lock" in normalized:
            return self
        if "WHERE operation_id = %s" in normalized:
            self.row = self.state["ops"].get(params[0])
        elif "ORDER BY created_at DESC" in normalized:
            versions = self.state["keys"].get(params[0], [])
            self.row = (versions[-1][1],) if versions else None
        elif "INSERT INTO aigc_artifact_metadata" in normalized:
            key, version, object_key, digest, media_type, schema, provenance, op = params
            if op in self.state["ops"]:
                raise RuntimeError("unique operation collision")
            row = (key, version, digest, media_type, schema, provenance, op)
            self.state["ops"][op] = row
            self.state["objects"][op] = object_key
            self.state["keys"].setdefault(key, []).append((key, version))
            self.state["object_by_version"][version] = object_key
            self.row = None
        else:
            raise AssertionError(f"Unexpected SQL: {normalized}")
        return self
    def fetchone(self): return self.row


class FakePool:
    def __init__(self):
        self.state = {"ops": {}, "keys": {}, "objects": {}, "object_by_version": {}}
    def connection(self):
        pool = self
        class Context:
            def __enter__(self): return FakeConnection(pool.state)
            def __exit__(self, *_): return False
        return Context()


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.next_version = 0
        self.fail_put = False
        self.fail_get = False
        self.unversioned = False
    def put_object(self, **kwargs):
        if self.fail_put: raise PermissionError("AccessDenied")
        self.next_version += 1
        version = "null" if self.unversioned else f"v{self.next_version}"
        self.objects[(kwargs["Key"], version)] = kwargs["Body"]
        return {"VersionId": version}
    def get_object(self, **kwargs):
        if self.fail_get: raise TimeoutError("unavailable")
        return {"Body": io.BytesIO(self.objects[(kwargs["Key"], kwargs["VersionId"])])}


def setup_store():
    pool, s3 = FakePool(), FakeS3()
    store = S3PostgresArtifactStore(pool=pool, s3_client=s3, bucket="private-test-bucket")
    return store, pool, s3


def put(store, content=b"packet", op="op-1", expected=None):
    return store.put(key="authorizations/A1", content=content,
                     media_type="application/json", schema_version="1",
                     provenance="phase5:test", operation_id=op,
                     expected_current_version_id=expected)


def test_shared_adapter_round_trip_and_digest_verification():
    store, _, _ = setup_store()
    ref = put(store)
    assert store.get(ref) == b"packet"
    assert ref.sha256 == hashlib.sha256(b"packet").hexdigest()


def test_same_operation_is_idempotent():
    store, _, _ = setup_store()
    assert put(store) == put(store)


def test_conflicting_operation_id_fails_closed():
    store, _, _ = setup_store()
    put(store)
    with pytest.raises(ArtifactConflict):
        put(store, content=b"other")


def test_stale_version_write_is_rejected():
    store, _, _ = setup_store()
    first = put(store)
    with pytest.raises(ArtifactConflict, match="stale artifact write"):
        put(store, content=b"new", op="op-2", expected="wrong")
    second = put(store, content=b"new", op="op-2", expected=first.version_id)
    assert second.version_id != first.version_id


def test_s3_denial_fails_closed():
    store, _, s3 = setup_store()
    s3.fail_put = True
    with pytest.raises(ArtifactUnavailable):
        put(store)


def test_unversioned_s3_response_is_rejected():
    store, _, s3 = setup_store()
    s3.unversioned = True
    with pytest.raises(ArtifactUnavailable, match="versioning"):
        put(store)


def test_s3_outage_fails_closed_on_read():
    store, _, s3 = setup_store()
    ref = put(store)
    s3.fail_get = True
    with pytest.raises(ArtifactUnavailable):
        store.get(ref)


def test_tampered_bytes_are_rejected():
    store, _, s3 = setup_store()
    ref = put(store)
    object_key = f"aigc-artifacts/{ref.sha256}"
    s3.objects[(object_key, ref.version_id)] = b"tampered"
    with pytest.raises(ArtifactIntegrityError):
        store.get(ref)
