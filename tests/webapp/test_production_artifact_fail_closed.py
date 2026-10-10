from __future__ import annotations

import pytest
from fastapi import HTTPException

import src.webapp.app as command_center


def test_production_review_source_fails_closed_until_durable_store_is_integrated(monkeypatch):
    monkeypatch.setattr(command_center, "_production_mode", lambda: True)

    with pytest.raises(HTTPException) as exc_info:
        command_center._load_review_source_records()

    assert exc_info.value.status_code == 503
    assert "Durable authorization/evidence storage is not integrated" in exc_info.value.detail


def test_development_review_source_uses_existing_local_loaders(monkeypatch):
    monkeypatch.setattr(command_center, "_production_mode", lambda: False)
    monkeypatch.setattr(command_center, "load_authorization_packets", lambda root: [{"id": "packet"}])
    monkeypatch.setattr(command_center, "load_work_order_governance_records", lambda root: [{"id": "work-order"}])

    packets, work_orders = command_center._load_review_source_records()

    assert packets == [{"id": "packet"}]
    assert work_orders == [{"id": "work-order"}]
