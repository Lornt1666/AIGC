from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from src.core.artifact_store import (
    ArtifactConflict,
    ArtifactIntegrityError,
    ArtifactNotFound,
    ArtifactRef,
    LocalArtifactStore,
)


def put(store, *, content=b"approved packet", operation_id="op-001"):
    return store.put(
        key="authorizations/AIGC-AUTH-1",
        content=content,
        media_type="application/json",
        schema_version="1.0",
        provenance="phase5:test-fixture",
        operation_id=operation_id,
    )


def test_put_and_get_returns_verified_immutable_reference(tmp_path):
    store = LocalArtifactStore(tmp_path)
    content = b'{"decision":"pending"}'
    ref = put(store, content=content)
    assert isinstance(ref, ArtifactRef)
    assert ref.sha256 == hashlib.sha256(content).hexdigest()
    assert ref.version_id == ref.sha256
    assert store.get(ref) == content


def test_identical_operation_retry_is_idempotent(tmp_path):
    store = LocalArtifactStore(tmp_path)
    assert put(store) == put(store)


def test_operation_id_reuse_with_different_content_is_rejected(tmp_path):
    store = LocalArtifactStore(tmp_path)
    put(store)
    with pytest.raises(ArtifactConflict):
        put(store, content=b"changed packet")


def test_operation_id_reuse_with_different_metadata_is_rejected(tmp_path):
    store = LocalArtifactStore(tmp_path)
    put(store)
    with pytest.raises(ArtifactConflict):
        store.put(
            key="authorizations/AIGC-AUTH-2",
            content=b"approved packet",
            media_type="application/json",
            schema_version="1.0",
            provenance="phase5:test-fixture",
            operation_id="op-001",
        )


def test_tampered_blob_fails_closed(tmp_path):
    store = LocalArtifactStore(tmp_path)
    ref = put(store)
    (tmp_path / "blobs" / ref.sha256).write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError):
        store.get(ref)


def test_missing_blob_fails_closed(tmp_path):
    store = LocalArtifactStore(tmp_path)
    ref = put(store)
    (tmp_path / "blobs" / ref.sha256).unlink()
    with pytest.raises(ArtifactNotFound):
        store.get(ref)


def test_reference_metadata_must_match_committed_receipt(tmp_path):
    store = LocalArtifactStore(tmp_path)
    ref = put(store)
    forged_ref = replace(ref, provenance="phase7:unverified")
    with pytest.raises(ArtifactIntegrityError, match="metadata does not match"):
        store.get(forged_ref)


def test_missing_operation_receipt_fails_closed(tmp_path):
    store = LocalArtifactStore(tmp_path)
    ref = put(store)
    receipt = tmp_path / "operations" / (
        hashlib.sha256(ref.operation_id.encode("utf-8")).hexdigest() + ".json"
    )
    receipt.unlink()
    with pytest.raises(ArtifactNotFound, match="operation receipt"):
        store.get(ref)


def test_empty_required_metadata_is_rejected(tmp_path):
    store = LocalArtifactStore(tmp_path)
    with pytest.raises(ValueError):
        store.put(
            key="",
            content=b"x",
            media_type="text/plain",
            schema_version="1",
            provenance="test",
            operation_id="op-empty",
        )
