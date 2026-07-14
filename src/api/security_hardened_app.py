from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI

from src.api.app import create_app
from src.security.production_http_security import (
    DEFAULT_POLICY_PATH,
    ProductionSecurityMiddleware,
    security_status,
)


def create_security_hardened_app(
    database_path: str | Path | None = None,
    *,
    policy_path: str | Path = DEFAULT_POLICY_PATH,
) -> FastAPI:
    """Create the AIGC API with enforceable internal security controls.

    This entrypoint is suitable for local and isolated staging validation. It
    does not claim production TLS termination, edge WAF/rate limiting, managed
    identity, secret access, or deployment authority.
    """

    api = create_app(database_path)
    api.title = "AIGC Security-Hardened Operator API"
    api.version = "1.0.0-internal"
    api.description = (
        "AIGC governed operator surface with host, origin, request-size, "
        "CSRF, rate-limit, cache, and response-header controls. Production "
        "operational evidence remains incomplete."
    )
    api.add_middleware(ProductionSecurityMiddleware, policy_path=policy_path)

    @api.get("/api/v1/security/status")
    def production_security_status() -> dict[str, Any]:
        return security_status()

    return api


app = create_security_hardened_app()
