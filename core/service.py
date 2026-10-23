"""Minimal authenticated API for the AIGC reference runtime.

Only health, typed task admission, and static code screening are exposed. There is no
endpoint for arbitrary agent execution, tool invocation, merge, deployment or release.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from core.arbiter import audit_python_source
from core.contracts import TaskContract
from core.orchestrator import SagaCoordinator, OrchestrationError
from core.telemetry import configure_telemetry, record_http_request, traced_operation


def _api_key() -> str:
    value = os.environ.get("AIGC_API_BEARER_TOKEN", "")
    if len(value) < 32:
        raise RuntimeError("AIGC_API_BEARER_TOKEN must be at least 32 characters")
    return value


async def require_api_key(authorization: str | None = Header(default=None)) -> None:
    expected = _api_key()
    provided = authorization.removeprefix("Bearer ").strip() if isinstance(authorization, str) else ""
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_bearer_token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _api_key()
    auth_limit = int(os.environ.get("AIGC_RATE_LIMIT_AUTHENTICATED_PER_MINUTE", "120"))
    unauth_limit = int(os.environ.get("AIGC_RATE_LIMIT_UNAUTHENTICATED_PER_MINUTE", "30"))
    if not (1 <= auth_limit <= 10_000 and 1 <= unauth_limit <= 10_000):
        raise RuntimeError("rate_limit_configuration_out_of_bounds")
    app.state.rate_limit_auth = auth_limit
    app.state.rate_limit_unauth = unauth_limit
    telemetry_status = configure_telemetry()
    app.state.telemetry_status = telemetry_status
    coordinator = SagaCoordinator(
        database_url=os.environ["DATABASE_URL"],
        redis_url=os.environ["REDIS_URL"],
        dry_run=os.environ.get("AIGC_DRY_RUN", "true").lower() != "false",
        max_hops=int(os.environ.get("AIGC_MAX_HOPS", "10")),
        max_concurrency=int(os.environ.get("AIGC_MAX_CONCURRENCY", "16")),
    )
    await coordinator.open()
    app.state.coordinator = coordinator
    try:
        yield
    finally:
        await coordinator.close()


app = FastAPI(title="RegenExcalibur AIGC Runtime", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

_RATE_LIMIT_SCRIPT = """
local now = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call("ZREMRANGEBYSCORE", KEYS[1], "-inf", now - window_ms)
local count = redis.call("ZCARD", KEYS[1])
if count >= limit then return 0 end
redis.call("ZADD", KEYS[1], now, member)
redis.call("PEXPIRE", KEYS[1], window_ms)
return count + 1
"""

@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    started = time.monotonic()
    route_class = "health" if request.url.path.startswith("/health/") else "api"
    status_code = 500
    if route_class != "health":
        expected = os.environ.get("AIGC_API_BEARER_TOKEN", "")
        authorization = request.headers.get("authorization", "")
        provided = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
        authenticated = len(expected) >= 32 and hmac.compare_digest(provided.encode(), expected.encode())
        identity = hashlib.sha256(expected.encode()).hexdigest() if authenticated else "unauthenticated"
        limit = request.app.state.rate_limit_auth if authenticated else request.app.state.rate_limit_unauth
        coordinator = getattr(request.app.state, "coordinator", None)
        if coordinator is None:
            status_code = 503
            record_http_request(request.method, status_code, time.monotonic() - started, route_class)
            return JSONResponse(status_code=503, content={"detail": "rate_limit_dependency_unavailable"})
        try:
            allowed = await coordinator.redis.eval(_RATE_LIMIT_SCRIPT, 1,
                "aigc:rate-limit:v1:" + identity, int(time.time() * 1000), 60_000, limit, uuid4().hex)
        except Exception:
            status_code = 503
            record_http_request(request.method, status_code, time.monotonic() - started, route_class)
            return JSONResponse(status_code=503, content={"detail": "rate_limit_dependency_unavailable"})
        if int(allowed) == 0:
            status_code = 429
            record_http_request(request.method, status_code, time.monotonic() - started, route_class)
            return JSONResponse(status_code=429, headers={"Retry-After": "60"}, content={"detail": "rate_limit_exceeded"})
    try:
        with traced_operation("aigc.http.request", {"http.request.method": request.method, "aigc.route_class": route_class}):
            response = await call_next(request)
            status_code = response.status_code
            return response
    finally:
        record_http_request(request.method, status_code, time.monotonic() - started, route_class)


@app.get("/health/live")
async def live() -> dict[str, Any]:
    return {"status": "alive", "side_effects_performed": False}


@app.get("/health/ready")
async def ready(request: Request) -> dict[str, Any]:
    coordinator = getattr(request.app.state, "coordinator", None)
    if coordinator is None:
        raise HTTPException(status_code=503, detail="runtime_not_initialized")
    try:
        await coordinator.redis.ping()
        async with coordinator.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="dependency_unavailable") from None
    return {"status": "ready", "persistence": "postgresql", "transport": "redis_streams",
            "execution_mode": "dry_run_default", "telemetry": getattr(request.app.state, "telemetry_status", {"configured": False}), "release_authority": "RX-19",
            "side_effects_performed": False}


@app.post("/v1/tasks/validate", dependencies=[Depends(require_api_key)])
async def validate_task(task: TaskContract) -> dict[str, Any]:
    encoded = json.dumps(task.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"status": "VALIDATED_NOT_SUBMITTED", "task_id": str(task.task_id),
            "contract_version": task.contract_version, "canonical_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
            "side_effects_performed": False, "production_execution_authorized": False}


@app.post("/v1/tasks", dependencies=[Depends(require_api_key)])
async def submit_task(task: TaskContract, request: Request) -> dict[str, Any]:
    coordinator: SagaCoordinator = request.app.state.coordinator
    try:
        result = await coordinator.submit(task)
        # A prior request may have committed the DB transaction but lost the
        # response before Redis publication. Always drain pending outbox rows.
        result["outbox_published_count"] = await coordinator.publish_outbox(batch_size=100)
        return result
    except (OrchestrationError, ValidationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception:
        # Avoid leaking connection strings, tokens, or upstream exception payloads.
        raise HTTPException(status_code=503, detail="task_admission_unavailable") from None


@app.post("/v1/arbiter/audit", dependencies=[Depends(require_api_key)])
async def audit_source(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("source")
    if not isinstance(source, str):
        raise HTTPException(status_code=422, detail="source_must_be_string")
    return audit_python_source(source).to_dict()
