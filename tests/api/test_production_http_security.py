from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.api.security_hardened_app import create_security_hardened_app
from src.security.production_http_security import _FixedWindowRateLimiter


def client(tmp_path: Path, *, base_url: str = "http://testserver") -> TestClient:
    return TestClient(
        create_security_hardened_app(tmp_path / "security.sqlite3"),
        base_url=base_url,
    )


def test_hardened_app_adds_security_headers_and_request_id(tmp_path: Path) -> None:
    response = client(tmp_path).get("/health", headers={"x-request-id": "req-test-001"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-test-001"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "camera=()" in response.headers["permissions-policy"]


def test_https_requests_receive_hsts(tmp_path: Path) -> None:
    response = client(tmp_path, base_url="https://testserver").get("/health")

    assert response.status_code == 200
    assert response.headers["strict-transport-security"].startswith("max-age=31536000")


def test_sensitive_api_responses_are_not_cacheable(tmp_path: Path) -> None:
    response = client(tmp_path).get("/api/v1/security/status")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    body = response.json()
    assert body["implemented_internal"] is True
    assert body["production_complete"] is False
    assert body["external_action_performed"] is False


def test_same_origin_is_allowed_while_unapproved_host_and_origin_are_denied(
    tmp_path: Path,
) -> None:
    same_origin = client(tmp_path).get(
        "/health",
        headers={"origin": "http://testserver"},
    )
    assert same_origin.status_code == 200

    bad_host = client(tmp_path, base_url="http://evil.example").get("/health")
    assert bad_host.status_code == 400
    assert bad_host.json()["detail"]["code"] == "HOST_NOT_ALLOWED"

    bad_origin = client(tmp_path).get(
        "/health",
        headers={"origin": "https://evil.example"},
    )
    assert bad_origin.status_code == 403
    assert bad_origin.json()["detail"]["code"] == "CROSS_ORIGIN_REQUEST_DENIED"


def test_cookie_authenticated_write_requires_matching_csrf_token(tmp_path: Path) -> None:
    api = client(tmp_path)
    api.cookies.set("aigc_session", "session-reference")
    api.cookies.set("aigc_csrf", "csrf-value")

    blocked = api.post("/api/v1/identity/authorize", json={})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "CSRF_VALIDATION_FAILED"

    passed_boundary = api.post(
        "/api/v1/identity/authorize",
        json={},
        headers={"x-csrf-token": "csrf-value"},
    )
    assert passed_boundary.status_code == 422


def test_declared_oversized_request_is_rejected_before_application(tmp_path: Path) -> None:
    response = client(tmp_path).post(
        "/api/v1/identity/authorize",
        content=b"{}",
        headers={
            "content-type": "application/json",
            "content-length": "1048577",
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "REQUEST_BODY_TOO_LARGE"


def test_fixed_window_limiter_fails_closed_at_limit() -> None:
    limiter = _FixedWindowRateLimiter(2)

    assert limiter.allow("client", now=100.0) is True
    assert limiter.allow("client", now=101.0) is True
    assert limiter.allow("client", now=102.0) is False
    assert limiter.allow("client", now=161.1) is True
