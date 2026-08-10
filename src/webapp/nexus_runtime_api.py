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
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_RUNTIME_ROLES = frozenset({"operator", "judge"})
_LOGGER = logging.getLogger("aigc.nexus.runtime")


def _environment_flag(name: str) -> bool:
    value = os.environ.get(name, "false").strip().lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return value == "true"


@dataclass(frozen=True)
class NexusRuntimeConfig:
    project_id: str
    runtime_role: str
    release_revision: str
    image_digest: str
    region: str
    deployment_authorization_sha256: str
    live_provider_execution_enabled: bool
    production_activation: bool
    runtime_control_dsn_secret_ref: str = ""

    @classmethod
    def from_environment(cls) -> "NexusRuntimeConfig":
        return cls(
            project_id=os.environ.get("AIGC_PROJECT_ID", "").strip(),
            runtime_role=os.environ.get("AIGC_RUNTIME_ROLE", "operator").strip().lower(),
            release_revision=os.environ.get("AIGC_RELEASE_REVISION", "").strip().lower(),
            image_digest=os.environ.get("AIGC_IMAGE_DIGEST", "").strip().lower(),
            region=os.environ.get("AIGC_REGION", REGION).strip(),
            deployment_authorization_sha256=os.environ.get(
                "AIGC_DEPLOYMENT_AUTHORIZATION_SHA256", ""
            ).strip().lower(),
            live_provider_execution_enabled=_environment_flag(
                "AIGC_LIVE_PROVIDER_EXECUTION_ENABLED"
            ),
            production_activation=_environment_flag("AIGC_PRODUCTION_ACTIVATION"),
            runtime_control_dsn_secret_ref=os.environ.get(
                "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF", ""
            ).strip(),
        )

    @property
    def provider_capable(self) -> bool:
        return self.runtime_role == "operator"

    def validate(self, resolver: RegionalSecretManagerResolver) -> None:
        if not _PROJECT.fullmatch(self.project_id):
            raise ValueError("AIGC_PROJECT_ID must be an exact Google Cloud project ID")
        if self.runtime_role not in _RUNTIME_ROLES:
            raise ValueError("AIGC_RUNTIME_ROLE must be operator or judge")
        if not _EXACT_REVISION.fullmatch(self.release_revision):
            raise ValueError("AIGC_RELEASE_REVISION must be an exact 40-character Git SHA")
        if not _IMAGE_DIGEST.fullmatch(self.image_digest):
            raise ValueError("AIGC_IMAGE_DIGEST must be an immutable sha256 digest")
        if self.region != REGION:
            raise ValueError(f"AIGC_REGION must equal {REGION}")
        if not _SHA256.fullmatch(self.deployment_authorization_sha256):
            raise ValueError("AIGC_DEPLOYMENT_AUTHORIZATION_SHA256 must be an exact SHA-256")
        if self.live_provider_execution_enabled:
            raise ValueError("staging service runtime cannot enable live provider execution")
        if self.production_activation:
            raise ValueError("staging service runtime cannot enable production activation")
        if self.runtime_role == "judge":
            if self.runtime_control_dsn_secret_ref:
                raise ValueError("provider-free judge must not receive a runtime secret reference")
            return
        metadata = resolver.parse_reference(self.runtime_control_dsn_secret_ref)
        if metadata.project_id != self.project_id:
            raise ValueError("runtime-control secret reference belongs to another project")


class NexusRuntimeDependencies:
    """Lazy role boundary; no secret access occurs at import or /health."""

    def __init__(
        self,
        *,
        config: NexusRuntimeConfig | None = None,
        secret_resolver: RegionalSecretManagerResolver | None = None,
        control_store_factory: Callable[[str], PostgresRuntimeControlStore] = PostgresRuntimeControlStore,
    ) -> None:
        self.config = config or NexusRuntimeConfig.from_environment()
        expected_project = self.config.project_id if _PROJECT.fullmatch(self.config.project_id) else None
        self.secret_resolver = secret_resolver or RegionalSecretManagerResolver(
            expected_project_id=expected_project
        )
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
            common: dict[str, object] = {
                "ready": True,
                "project_id": self.config.project_id,
                "runtime_role": self.config.runtime_role,
                "release_revision": self.config.release_revision,
                "image_digest": self.config.image_digest,
                "region": self.config.region,
                "deployment_authorization_sha256": self.config.deployment_authorization_sha256,
                "provider_capable": self.config.provider_capable,
                "live_provider_execution_enabled": False,
                "production_activation": False,
            }
            if self.config.runtime_role == "judge":
                result = {
                    **common,
                    "runtime_control_backend": "not_applicable",
                    "emergency_active": False,
                    "stop_epoch": None,
                }
                _LOGGER.info(
                    "nexus_readiness ready=true role=judge release=%s image=%s region=%s",
                    self.config.release_revision,
                    self.config.image_digest,
                    self.config.region,
                )
                return result
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
            if health.emergency_active:
                raise RuntimeError("durable runtime emergency stop is active")
            result = {
                **common,
                "runtime_control_backend": health.backend,
                "emergency_active": health.emergency_active,
                "stop_epoch": health.stop_epoch,
            }
            _LOGGER.info(
                "nexus_readiness ready=true role=operator release=%s image=%s region=%s backend=%s stop_epoch=%s emergency=%s",
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
                "nexus_readiness ready=false role=%s failure=%s",
                self.config.runtime_role,
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
            "runtime_role": deps.config.runtime_role,
            "process_alive": True,
            "provider_capable": deps.config.provider_capable,
            "live_provider_execution_enabled": False,
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
                    "runtime_role": deps.config.runtime_role,
                    "failure_class": type(exc).__name__,
                    "live_provider_execution_enabled": False,
                    "production_activation": False,
                    "live_model_call_performed": False,
                },
            )

    @app.get("/observability")
    def observability() -> dict[str, object]:
        return {
            "service": "aigc-nexus-v1",
            "runtime_role": deps.config.runtime_role,
            "provider_capable": deps.config.provider_capable,
            "live_provider_execution_enabled": False,
            "production_activation": False,
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
            "authorization_digest_configured": bool(
                _SHA256.fullmatch(deps.config.deployment_authorization_sha256)
            ),
            "secret_reference_configured": bool(
                deps.config.runtime_control_dsn_secret_ref
            ),
            "secret_values_exposed": False,
            "provider_calls_performed": 0,
        }

    return app


app = create_app()
