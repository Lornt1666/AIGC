from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
import re
import threading
from typing import Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.infrastructure.credentials.regional_secret_manager import (
    REGION,
    RegionalSecretManagerResolver,
)
from src.infrastructure.runtime.postgres_control_store import PostgresRuntimeControlStore


_EXACT_REVISION = re.compile(r"^[a-f0-9]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_LOGGER = logging.getLogger("aigc.nexus.runtime")


@dataclass(frozen=True)
class NexusRuntimeConfig:
    release_revision: str
    image_digest: str
    region: str
    runtime_control_dsn_secret_ref: str

    @classmethod
    def from_environment(cls) -> "NexusRuntimeConfig":
        return cls(
            release_revision=os.environ.get("AIGC_RELEASE_REVISION", "").strip().lower(),
            image_digest=os.environ.get("AIGC_IMAGE_DIGEST", "").strip().lower(),
            region=os.environ.get("AIGC_REGION", REGION).strip(),
            runtime_control_dsn_secret_ref=os.environ.get(
                "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF", ""
            ).strip(),
        )

    def validate(self, resolver: RegionalSecretManagerResolver) -> None:
        if not _EXACT_REVISION.fullmatch(self.release_revision):
            raise ValueError("AIGC_RELEASE_REVISION must be an exact 40-character Git SHA")
        if not _IMAGE_DIGEST.fullmatch(self.image_digest):
            raise ValueError("AIGC_IMAGE_DIGEST must be an immutable sha256 digest")
        if self.region != REGION:
            raise ValueError(f"AIGC_REGION must equal {REGION}")
        resolver.parse_reference(self.runtime_control_dsn_secret_ref)


class NexusRuntimeDependencies:
    """Lazy readiness dependency boundary; no secret access occurs at import or /health."""

    def __init__(
        self,
        *,
        config: NexusRuntimeConfig | None = None,
        secret_resolver: RegionalSecretManagerResolver | None = None,
        control_store_factory: Callable[[str], PostgresRuntimeControlStore] = PostgresRuntimeControlStore,
    ) -> None:
        self.config = config or NexusRuntimeConfig.from_environment()
        self.secret_resolver = secret_resolver or RegionalSecretManagerResolver()
        self._control_store_factory = control_store_factory
        self._control_store: PostgresRuntimeControlStore | None = None
        self._lock = threading.Lock()
        self.readiness_checks = 0
        self.readiness_failures = 0
        self.started_at = datetime.now(timezone.utc)

    def readiness(self) -> dict[str, object]:
        self.readiness_checks += 1
        try:
            self.config.validate(self.secret_resolver)
            with self._lock:
                if self._control_store is None:
                    dsn = self.secret_resolver.resolve_text(
                        self.config.runtime_control_dsn_secret_ref
                    )
                    try:
                        self._control_store = self._control_store_factory(dsn)
                    finally:
                        dsn = ""
            health = self._control_store.healthcheck()
            if not health.ok or not health.durable:
                raise RuntimeError("durable runtime control health is not ready")
            result = {
                "ready": True,
                "release_revision": self.config.release_revision,
                "image_digest": self.config.image_digest,
                "region": self.config.region,
                "runtime_control_backend": health.backend,
                "emergency_active": health.emergency_active,
                "stop_epoch": health.stop_epoch,
            }
            _LOGGER.info(
                "nexus_readiness ready=true release=%s image=%s region=%s backend=%s stop_epoch=%s emergency=%s",
                self.config.release_revision,
                self.config.image_digest,
                self.config.region,
                health.backend,
                health.stop_epoch,
                health.emergency_active,
            )
            return result
        except Exception as exc:
            self.readiness_failures += 1
            _LOGGER.warning(
                "nexus_readiness ready=false failure=%s",
                type(exc).__name__,
            )
            raise


def create_app(dependencies: NexusRuntimeDependencies | None = None) -> FastAPI:
    deps = dependencies or NexusRuntimeDependencies()
    app = FastAPI(
        title="AIGC Nexus V1 Runtime",
        version="1.0.0",
        description="Private staging runtime for governed Nexus health/readiness evidence.",
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "ok": True,
            "service": "aigc-nexus-v1",
            "process_alive": True,
            "production_activation": False,
            "live_model_call_performed": False,
        }

    @app.get("/ready")
    def ready():
        try:
            return deps.readiness()
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={
                    "ready": False,
                    "failure_class": type(exc).__name__,
                    "production_activation": False,
                    "live_model_call_performed": False,
                },
            )

    @app.get("/observability")
    def observability() -> dict[str, object]:
        return {
            "service": "aigc-nexus-v1",
            "started_at": deps.started_at.isoformat(),
            "readiness_checks": deps.readiness_checks,
            "readiness_failures": deps.readiness_failures,
            "region": deps.config.region,
            "release_revision_configured": bool(
                _EXACT_REVISION.fullmatch(deps.config.release_revision)
            ),
            "image_digest_configured": bool(
                _IMAGE_DIGEST.fullmatch(deps.config.image_digest)
            ),
            "secret_reference_configured": bool(
                deps.config.runtime_control_dsn_secret_ref
            ),
            "secret_values_exposed": False,
            "provider_calls_performed": 0,
        }

    return app


app = create_app()
