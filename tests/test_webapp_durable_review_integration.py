from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.webapp import app as command_center


def test_shared_review_mode_uses_durable_repository_without_local_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    packets = [{"action_id": "A1"}]
    work_orders = [{"work_order_id": "W1"}]
    snapshot = SimpleNamespace(
        authorization_packets=SimpleNamespace(items=packets),
        work_order_governance=SimpleNamespace(items=work_orders),
    )

    class FakeRepository:
        @classmethod
        def from_env(cls) -> "FakeRepository":
            return cls()

        def load_review_collections(self) -> SimpleNamespace:
            return snapshot

    monkeypatch.setenv("AIGC_REVIEW_STORAGE_MODE", "shared")
    monkeypatch.setattr(command_center, "DurableReviewRepository", FakeRepository)
    monkeypatch.setattr(
        command_center,
        "load_authorization_packets",
        lambda *_args, **_kwargs: pytest.fail("shared mode must not read local authorization files"),
    )
    monkeypatch.setattr(
        command_center,
        "load_work_order_governance_records",
        lambda *_args, **_kwargs: pytest.fail("shared mode must not read local work-order files"),
    )

    assert command_center._load_review_collections() == (packets, work_orders)


def test_shared_review_mode_fails_closed_when_authority_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnavailableRepository:
        @classmethod
        def from_env(cls) -> "UnavailableRepository":
            return cls()

        def load_review_collections(self) -> None:
            raise RuntimeError("shared store unavailable")

    monkeypatch.setenv("AIGC_REVIEW_STORAGE_MODE", "shared")
    monkeypatch.setattr(command_center, "DurableReviewRepository", UnavailableRepository)
    monkeypatch.setattr(
        command_center,
        "load_authorization_packets",
        lambda *_args, **_kwargs: pytest.fail("must not fall back to local authorization files"),
    )

    with pytest.raises(HTTPException) as exc:
        command_center._load_review_collections()
    assert exc.value.status_code == 503


def test_shared_review_mode_blocks_local_mutation_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIGC_REVIEW_STORAGE_MODE", "shared")
    with pytest.raises(HTTPException) as exc:
        command_center._require_local_review_mutation_authority()
    assert exc.value.status_code == 503


def test_production_guard_remains_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIGC_ENV", "production")
    with pytest.raises(HTTPException) as exc:
        command_center._require_shared_artifact_authority()
    assert exc.value.status_code == 503
