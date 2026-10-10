from __future__ import annotations

import json

import pytest

from src.core.durable_json_artifacts import load_json_collection, save_json_collection
from src.core.production_artifact_store import ArtifactConflict, ArtifactIntegrityError, ArtifactNotFound

from tests.test_production_artifact_store import setup_store


def test_json_collection_round_trip_and_versioned_update():
    store, _, _ = setup_store()
    first = save_json_collection(
        store,
        key="runtime/authorization-packets",
        items=[{"action_id": "A1", "decision": "pending"}],
        expected=None,
        operation_id="packet-snapshot-1",
        schema_version="1",
        provenance="migration:test",
    )
    snapshot = load_json_collection(store, "runtime/authorization-packets")
    assert snapshot.ref == first
    assert snapshot.items == [{"action_id": "A1", "decision": "pending"}]

    second = save_json_collection(
        store,
        key="runtime/authorization-packets",
        items=[{"action_id": "A1", "decision": "denied"}],
        expected=first,
        operation_id="packet-snapshot-2",
        schema_version="1",
        provenance="review:test",
    )
    assert second.version_id != first.version_id
    assert load_json_collection(store, "runtime/authorization-packets").items == [
        {"action_id": "A1", "decision": "denied"}
    ]


def test_json_collection_rejects_stale_snapshot():
    store, _, _ = setup_store()
    first = save_json_collection(
        store, key="runtime/work-orders", items=[{"work_order_id": "W1"}],
        expected=None, operation_id="work-orders-1", schema_version="1",
        provenance="test",
    )
    save_json_collection(
        store, key="runtime/work-orders", items=[{"work_order_id": "W2"}],
        expected=first, operation_id="work-orders-2", schema_version="1",
        provenance="test",
    )
    with pytest.raises(ArtifactConflict, match="stale artifact write"):
        save_json_collection(
            store, key="runtime/work-orders", items=[{"work_order_id": "W3"}],
            expected=first, operation_id="work-orders-3", schema_version="1",
            provenance="test",
        )


def test_json_collection_missing_authority_fails_closed():
    store, _, _ = setup_store()
    with pytest.raises(ArtifactNotFound):
        load_json_collection(store, "runtime/missing")


def test_json_collection_rejects_malformed_json():
    store, _, _ = setup_store()
    ref = store.put(
        key="runtime/invalid",
        content=b"{broken",
        media_type="application/json",
        schema_version="1",
        provenance="test",
        operation_id="invalid-json-1",
    )
    with pytest.raises(ArtifactIntegrityError):
        load_json_collection(store, "runtime/invalid")


def test_json_collection_requires_object_entries():
    store, _, _ = setup_store()
    ref = store.put(
        key="runtime/scalars",
        content=json.dumps([1, 2, 3]).encode(),
        media_type="application/json",
        schema_version="1",
        provenance="test",
        operation_id="scalar-json-1",
    )
    with pytest.raises(ArtifactIntegrityError):
        load_json_collection(store, "runtime/scalars")
