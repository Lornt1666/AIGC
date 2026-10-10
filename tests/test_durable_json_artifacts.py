from __future__ import annotations

import hashlib
import json

import pytest

from src.core.durable_json_artifacts import load_json_collection, save_json_collection
from src.core.production_artifact_store import (
    ArtifactConflict, ArtifactIntegrityError, ArtifactNotFound, ArtifactRef,
)


class FakeJsonStore:
    def __init__(self):
        self.current = {}
        self.operations = {}

    def get_current(self, key):
        value = self.current.get(key)
        return value

    def put(self, *, key, content, media_type, schema_version, provenance,
            operation_id, expected_current_version_id=None):
        digest = hashlib.sha256(content).hexdigest()
        metadata = (key, digest, media_type, schema_version, provenance)
        if operation_id in self.operations:
            prior, prior_content = self.operations[operation_id]
            if (prior.key, prior.sha256, prior.media_type, prior.schema_version, prior.provenance) != metadata:
                raise ArtifactConflict("operation_id reused with conflicting artifact data")
            return prior
        current = self.current.get(key)
        current_version = current[0].version_id if current else None
        if current_version != expected_current_version_id:
            raise ArtifactConflict("stale artifact write")
        ref = ArtifactRef(key, f"v{len(self.operations)+1}", digest, media_type,
                          schema_version, provenance, operation_id)
        self.operations[operation_id] = (ref, content)
        self.current[key] = (ref, content)
        return ref


def test_json_collection_round_trip_and_versioned_update():
    store = FakeJsonStore()
    first = save_json_collection(
        store, key="runtime/authorization-packets",
        items=[{"action_id": "A1", "decision": "pending"}], expected=None,
        operation_id="packet-snapshot-1", schema_version="1", provenance="migration:test",
    )
    snapshot = load_json_collection(store, "runtime/authorization-packets")
    assert snapshot.ref == first
    assert snapshot.items == [{"action_id": "A1", "decision": "pending"}]

    second = save_json_collection(
        store, key="runtime/authorization-packets",
        items=[{"action_id": "A1", "decision": "denied"}], expected=first,
        operation_id="packet-snapshot-2", schema_version="1", provenance="review:test",
    )
    assert second.version_id != first.version_id
    assert load_json_collection(store, "runtime/authorization-packets").items == [
        {"action_id": "A1", "decision": "denied"}
    ]


def test_json_collection_rejects_stale_snapshot():
    store = FakeJsonStore()
    first = save_json_collection(
        store, key="runtime/work-orders", items=[{"work_order_id": "W1"}],
        expected=None, operation_id="work-orders-1", schema_version="1", provenance="test",
    )
    save_json_collection(
        store, key="runtime/work-orders", items=[{"work_order_id": "W2"}],
        expected=first, operation_id="work-orders-2", schema_version="1", provenance="test",
    )
    with pytest.raises(ArtifactConflict, match="stale artifact write"):
        save_json_collection(
            store, key="runtime/work-orders", items=[{"work_order_id": "W3"}],
            expected=first, operation_id="work-orders-3", schema_version="1", provenance="test",
        )


def test_json_collection_missing_authority_fails_closed():
    with pytest.raises(ArtifactNotFound):
        load_json_collection(FakeJsonStore(), "runtime/missing")


@pytest.mark.parametrize("content", [b"{broken", json.dumps([1, 2, 3]).encode()])
def test_json_collection_rejects_invalid_authoritative_payload(content):
    store = FakeJsonStore()
    ref = ArtifactRef(
        key="runtime/invalid", version_id="v1", sha256=hashlib.sha256(content).hexdigest(),
        media_type="application/json", schema_version="1", provenance="test",
        operation_id="invalid-json-1",
    )
    store.current["runtime/invalid"] = (ref, content)
    with pytest.raises(ArtifactIntegrityError):
        load_json_collection(store, "runtime/invalid")
