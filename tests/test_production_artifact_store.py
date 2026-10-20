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
    def __init__(self, state, mapping_rows=False):
        self.state = state
        self.mapping_rows = mapping_rows
        self.last_sql = ""
    def transaction(self): return FakeTransaction()
    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.last_sql = normalized
        if "pg_advisory_xact_lock" in normalized:
            return self
        if "WHERE operation_id = %s" in normalized:
            stored = self.state["ops"].get(params[0])
            if stored and "object_key" in normalized:
                self.row = (stored[0], stored[1], self.state["objects"][params[0]],
                            stored[2], stored[3], stored[4], stored[5], stored[6])
            else:
                self.row = stored
        elif "WHERE logical_key = %s" in normalized and "SELECT logical_key, version_id, sha256" in normalized:
            versions = self.state["keys"].get(params[0], [])
            if versions:
                operation = self.state["ops"][versions[-1][2]]
                self.row = (operation[0], operation[1], operation[2], operation[3],
                            operation[4], operation[5], operation[6])
            else:
                self.row = None
        elif "ORDER BY created_at DESC" in normalized:
            versions = self.state["keys"].get(params[0], [])
            self.row = (versions[-1][1],) if versions else None
        elif "INSERT INTO aigc_artifact_metadata" in normalized:
            key, version, object_key, digest, media_type, schema, provenance, op, expected_version = params
            if op in self.state["ops"]:
                raise RuntimeError("unique operation collision")
            row = (key, version, digest, media_type, schema, provenance, op, expected_version)
            self.state["ops"][op] = row
            self.state["objects"][op] = object_key
            self.state["keys"].setdefault(key, []).append((key, version, op))
            self.state["object_by_version"][version] = object_key
            self.row = None
        else:
            raise AssertionError(f"Unexpected SQL: {normalized}")
        return self
    def fetchone(self):
        if not self.mapping_rows or self.row is None:
            return self.row
        if "WHERE logical_key = %s" in self.last_sql and "SELECT logical_key, version_id, sha256" in self.last_sql:
            keys = ("logical_key", "version_id", "sha256", "media_type",
                    "schema_version", "provenance", "operation_id")
            return dict(zip(keys, self.row))
        if "ORDER BY created_at DESC" in self.last_sql:
            return {"version_id": self.row[0]}
        if "object_key" in self.last_sql and "WHERE operation_id" in self.last_sql:
            keys = ("logical_key", "version_id", "object_key", "sha256",
                    "media_type", "schema_version", "provenance", "operation_id")
            return dict(zip(keys, self.row))
        if "WHERE operation_id" in self.last_sql:
            keys = ("logical_key", "version_id", "sha256", "media_type",
                    "schema_version", "provenance", "operation_id")
            if "expected_current_version_id" in self.last_sql:
                keys = (*keys, "expected_current_version_id")
            return dict(zip(keys, self.row))
        return self.row


class FakePool:
    def __init__(self, mapping_rows=False):
        self.mapping_rows = mapping_rows
        self.state = {"ops": {}, "keys": {}, "objects": {}, "object_by_version": {}}
    def connection(self):
        pool = self
        class Context:
            def __enter__(self): return FakeConnection(pool.state, pool.mapping_rows)
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


def setup_store(mapping_rows=False):
    pool, s3 = FakePool(mapping_rows=mapping_rows), FakeS3()
    store = S3PostgresArtifactStore(pool=pool, s3_client=s3, bucket="private-test-bucket")
    return store, pool, s3


def put(store, content=b"packet", op="op-1", expected=None, key="authorizations/A1"):
    return store.put(key=key, content=content,
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


def test_operation_retry_rejects_changed_expected_version_precondition():
    store, _, _ = setup_store()
    first = put(store, content=b"first", op="op-first")
    second = put(store, content=b"second", op="op-second", expected=first.version_id)

    with pytest.raises(ArtifactConflict, match="precondition"):
        put(store, content=b"first", op="op-first", expected=second.version_id)

    assert store.get_current_ref("authorizations/A1") == second
    assert store.get_current("authorizations/A1") == (second, b"second")


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



def test_operation_id_cannot_be_reused_for_another_logical_key():
    store, _, _ = setup_store()
    put(store, op="globally-unique-op")
    with pytest.raises(ArtifactConflict):
        put(store, op="globally-unique-op", key="work-orders/W1")



def test_mapping_row_factory_is_supported():
    from src.core.production_artifact_store import ArtifactRef

    row = {
        "logical_key": "authorizations/A1",
        "version_id": "v7",
        "sha256": hashlib.sha256(b"packet").hexdigest(),
        "media_type": "application/json",
        "schema_version": "1",
        "provenance": "phase5:test",
        "operation_id": "op-7",
    }
    assert S3PostgresArtifactStore._row_to_ref(row) == ArtifactRef(
        key="authorizations/A1",
        version_id="v7",
        sha256=hashlib.sha256(b"packet").hexdigest(),
        media_type="application/json",
        schema_version="1",
        provenance="phase5:test",
        operation_id="op-7",
    )



def test_mapping_row_factory_supports_full_round_trip():
    store, _, _ = setup_store(mapping_rows=True)
    ref = put(store)
    assert store.get(ref) == b"packet"
    second = put(store, content=b"next", op="op-2", expected=ref.version_id)
    assert store.get(second) == b"next"



@pytest.mark.parametrize("mapping_rows", [False, True])
def test_current_artifact_read_returns_latest_verified_version(mapping_rows):
    store, _, _ = setup_store(mapping_rows=mapping_rows)
    first = put(store)
    second = put(store, content=b"newer", op="op-2", expected=first.version_id)

    assert store.get_current_ref("authorizations/A1") == second
    current = store.get_current("authorizations/A1")
    assert current == (second, b"newer")
    assert store.get_current_ref("missing/key") is None
