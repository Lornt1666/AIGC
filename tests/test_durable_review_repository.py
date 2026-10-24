from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.core import durable_review_repository as repository


@dataclass(frozen=True)
class FakeRef:
    key: str
    version_id: str


@dataclass(frozen=True)
class FakeSnapshot:
    key: str
    items: list[dict[str, Any]]
    ref: FakeRef


class FakeStore:
    pass


def test_load_uses_canonical_authoritative_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, str]] = []
    packets = FakeSnapshot(repository.AUTHORIZATION_PACKETS_KEY, [{"action_id": "A1"}], FakeRef("p", "v1"))
    work_orders = FakeSnapshot(repository.WORK_ORDER_GOVERNANCE_KEY, [{"work_order_id": "W1"}], FakeRef("w", "v2"))

    def fake_load(store: object, key: str) -> FakeSnapshot:
        calls.append((store, key))
        if key == repository.AUTHORIZATION_PACKETS_KEY:
            return packets
        if key == repository.WORK_ORDER_GOVERNANCE_KEY:
            return work_orders
        raise AssertionError(f"unexpected collection key: {key}")

    monkeypatch.setattr(repository, "load_json_collection", fake_load)
    store = FakeStore()
    loaded = repository.DurableReviewRepository(store).load_review_collections()  # type: ignore[arg-type]

    assert loaded.authorization_packets is packets
    assert loaded.work_order_governance is work_orders
    assert calls == [
        (store, repository.AUTHORIZATION_PACKETS_KEY),
        (store, repository.WORK_ORDER_GOVERNANCE_KEY),
    ]


def test_missing_authority_fails_closed_without_local_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    class MissingAuthority(RuntimeError):
        pass

    def fail_load(_store: object, key: str) -> FakeSnapshot:
        raise MissingAuthority(f"missing {key}")

    monkeypatch.setattr(repository, "load_json_collection", fail_load)
    with pytest.raises(MissingAuthority, match="missing"):
        repository.DurableReviewRepository(FakeStore()).load_authorization_packets()  # type: ignore[arg-type]


def test_save_binds_to_exact_expected_reference_and_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = FakeRef(repository.AUTHORIZATION_PACKETS_KEY, "v-current")
    saved_ref = FakeRef(repository.AUTHORIZATION_PACKETS_KEY, "v-next")
    captured: dict[str, Any] = {}

    def fake_save(store: object, **kwargs: Any) -> FakeRef:
        captured.update(kwargs)
        captured["store"] = store
        return saved_ref

    monkeypatch.setattr(repository, "save_json_collection", fake_save)
    store = FakeStore()
    result = repository.DurableReviewRepository(store).save_authorization_packets(
        items=[{"action_id": "A1"}],
        expected=expected,  # type: ignore[arg-type]
        operation_id="retry-stable-op-123",
    )

    assert result is saved_ref
    assert captured["store"] is store
    assert captured["key"] == repository.AUTHORIZATION_PACKETS_KEY
    assert captured["expected"] is expected
    assert captured["operation_id"] == "retry-stable-op-123"
    assert captured["schema_version"] == repository.COLLECTION_SCHEMA_VERSION
    assert captured["provenance"] == repository.COLLECTION_PROVENANCE


def test_work_order_write_uses_separate_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_save(_store: object, **kwargs: Any) -> FakeRef:
        captured.update(kwargs)
        return FakeRef(kwargs["key"], "v-new")

    monkeypatch.setattr(repository, "save_json_collection", fake_save)
    result = repository.DurableReviewRepository(FakeStore()).save_work_orders(
        items=[{"work_order_id": "W1"}],
        expected=None,
        operation_id="initial-work-order-seed-123",
    )

    assert result.key == repository.WORK_ORDER_GOVERNANCE_KEY
    assert captured["expected"] is None
    assert captured["key"] == repository.WORK_ORDER_GOVERNANCE_KEY
