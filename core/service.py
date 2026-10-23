"""Minimal authenticated API for the AIGC reference runtime.

Only health, typed task admission, and static code screening are exposed. There is no
endpoint for arbitrary agent execution, tool invocation, merge, deployment or release.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import ValidationError

from core.arbiter import audit_python_source
from core.contracts import TaskContract
from core.orchestrator import SagaCoordinator, OrchestrationError
from core.telemetry import configure_telemetry


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


app = FastAPI(title="RegenExcalibur AIGC Runtime", version="1.0.0", lifespan=lifespan)


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
            "execution_mode": "dry_run_default", "release_authority": "RX-19",
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
