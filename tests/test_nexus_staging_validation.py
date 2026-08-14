from __future__ import annotations

from types import SimpleNamespace

import pytest

import scripts.validate_nexus_staging_runtime as validator


class Response:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeClient:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url, headers=None):
        if headers is None:
            return Response(403, {"detail": "denied"})
        if url.endswith("/health"):
            return Response(200, {"ok": True})
        if url.endswith("/ready"):
            return Response(200, {"ready": True})
        if url.endswith("/observability"):
            return Response(200, {"secret_values_exposed": False})
        return Response(404, {"detail": "not found"})


def test_candidate_validation_records_bounded_load_security_and_reconciliation(monkeypatch):
    monkeypatch.setattr(validator.httpx, "Client", lambda **_kwargs: FakeClient())
    monkeypatch.setattr(
        validator.httpx,
        "get",
        lambda *_args, **_kwargs: Response(200, {"ready": True}),
    )
    result = validator.validate_candidate(
        candidate_url="https://candidate.example.invalid",
        audience="https://service.example.invalid",
        requests=8,
        concurrency=2,
        token_supplier=lambda _audience: "opaque-test-token",
    )
    assert result["authenticated_health"] == "PASS"
    assert result["authenticated_readiness"] == "PASS"
    assert result["unauthenticated_access"] == "DENIED"
    assert result["invalid_route"] == "FAIL_CLOSED"
    assert result["load_requests"] == 8
    assert result["load_failures"] == 0
    assert result["canonical_reconciliation_boundary"] == "PASS"
    assert result["state_advanced"] is False
    assert result["deployed_fault_injection_performed"] is False
    assert result["provider_calls_performed"] == 0


def test_candidate_validation_rejects_unbounded_load():
    with pytest.raises(ValueError, match="load bounds"):
        validator.validate_candidate(
            candidate_url="https://candidate.example.invalid",
            audience="https://service.example.invalid",
            requests=201,
            concurrency=1,
            token_supplier=lambda _audience: "opaque-test-token",
        )
