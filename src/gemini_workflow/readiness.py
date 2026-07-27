from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hmac
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .api import create_router
from .auth import (
    GeminiAuthenticationError,
    authenticate_shared_credential,
)
from .control_store import PostgresRuntimeControlStore
from .models import OperatorIdentity
from .secret_broker import OmegaXSecretAccess
from .settings import GeminiWorkflowSettings


RUNTIME_LIMITS_ENV = "AIGC_GEMINI_RUNTIME_LIMITS_PATH"
DEFAULT_RUNTIME_LIMITS_PATH = Path("config/gemini_runtime_limits.json")
COMMAND_TOKEN_ENV = "AIGC_COMMAND_CENTER_TOKEN"
OPERATOR_SUBJECT_KEY_ENV = "AIGC_OPERATOR_SUBJECT_KEY"


@dataclass(frozen=True)
class ProbeResult:
    name: str
    ready: bool
    detail: str
    operation: str
    generative_call_performed: bool = False
    external_action_performed: bool = False


@dataclass(frozen=True)
class ReadinessReport:
    ready: bool
    status: str
    checks: tuple[ProbeResult, ...]
    generative_call_performed: bool = False
    external_action_performed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "status": self.status,
            "checks": [asdict(item) for item in self.checks],
            "generative_call_performed": False,
            "external_action_performed": False,
        }


class ReadinessProbe(Protocol):
    name: str

    def check(self) -> ProbeResult: ...


@dataclass(frozen=True)
class CallableProbe:
    name: str
    operation: str
    callback: Callable[[], bool]

    def check(self) -> ProbeResult:
        ready = self.callback() is True
        return ProbeResult(
            name=self.name,
            ready=ready,
            detail="probe_succeeded" if ready else "probe_failed",
            operation=self.operation,
        )


class ReadinessEvaluator:
    """Evaluates only injected, non-generative dependency probes."""

    def __init__(
        self,
        probes: Sequence[ReadinessProbe],
        *,
        cache_ttl_seconds: float = 0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._probes = tuple(probes)
        names = [probe.name for probe in self._probes]
        if len(names) != len(set(names)):
            raise ValueError("Readiness probe names must be unique")
        if not 0 <= cache_ttl_seconds <= 60:
            raise ValueError("cache_ttl_seconds must be between 0 and 60")
        self._cache_ttl_seconds = float(cache_ttl_seconds)
        self._clock = clock
        self._cache: tuple[float, ReadinessReport] | None = None
        self._lock = threading.Lock()

    def evaluate(self, *, force: bool = False) -> ReadinessReport:
        with self._lock:
            now = self._clock()
            if (
                not force
                and self._cache is not None
                and now - self._cache[0] < self._cache_ttl_seconds
            ):
                return self._cache[1]

            checks: list[ProbeResult] = []
            for probe in self._probes:
                try:
                    result = probe.check()
                    if result.name != probe.name:
                        raise ValueError("Probe result name mismatch")
                    if (
                        result.generative_call_performed
                        or result.external_action_performed
                    ):
                        raise ValueError(
                            "Readiness probes must be non-generative and read-only"
                        )
                    checks.append(result)
                except Exception:
                    checks.append(
                        ProbeResult(
                            name=probe.name,
                            ready=False,
                            detail="probe_failed_closed",
                            operation="read_only",
                        )
                    )

            ready = bool(checks) and all(item.ready for item in checks)
            report = ReadinessReport(
                ready=ready,
                status="ready" if ready else "not_ready",
                checks=tuple(checks),
            )
            self._cache = (now, report)
            return report


@dataclass(frozen=True)
class ConfigurationProbe:
    settings_factory: Callable[[], GeminiWorkflowSettings]
    name: str = "configuration"

    def check(self) -> ProbeResult:
        settings = self.settings_factory()
        return ProbeResult(
            name=self.name,
            ready=settings.enabled,
            detail=(
                "live_configuration_valid"
                if settings.enabled
                else "live_configuration_disabled"
            ),
            operation="local_configuration_validation",
        )


@dataclass(frozen=True)
class SecretPresenceProbe:
    environ: Mapping[str, str]
    name: str = "application_secrets"

    def check(self) -> ProbeResult:
        command_token = self.environ.get(COMMAND_TOKEN_ENV, "").strip()
        subject_key = self.environ.get(OPERATOR_SUBJECT_KEY_ENV, "").strip()
        ready = (
            len(command_token) >= 32
            and len(subject_key) >= 32
            and not hmac.compare_digest(command_token, subject_key)
        )
        return ProbeResult(
            name=self.name,
            ready=ready,
            detail=(
                "required_application_secrets_present"
                if ready
                else "required_secret_configuration_invalid"
            ),
            operation="local_presence_validation",
        )


@dataclass(frozen=True)
class SecretReferenceProbe:
    """Resolve exact-version application secrets through SecretBroker."""

    project_id_factory: Callable[[], str]
    roles: tuple[Literal["operator", "runtime_admin", "judge"], ...]
    environ: Mapping[str, str]
    access_factory: Callable[[str, Mapping[str, str]], OmegaXSecretAccess] = (
        lambda project_id, environ: OmegaXSecretAccess.from_environment(
            project_id=project_id,
            environ=environ,
        )
    )
    name: str = "application_secrets"

    def check(self) -> ProbeResult:
        project_id = self.project_id_factory().strip()
        if not project_id:
            raise ValueError("Google Cloud project is not configured")
        access = self.access_factory(project_id, self.environ)
        resolved_values: list[str] = []
        for role in self.roles:
            prefix = {
                "operator": "AIGC_OPERATOR",
                "runtime_admin": "AIGC_RUNTIME_ADMIN",
                "judge": "AIGC_JUDGE",
            }[role]
            purpose_role = (
                "runtime-admin" if role == "runtime_admin" else role
            )
            token, _token_receipt = access.resolve(
                f"gemini-{purpose_role}-authentication"
            )
            binding_key, _key_receipt = access.resolve(
                f"gemini-{purpose_role}-principal-binding"
            )
            if (
                len(token) < 16
                or len(binding_key) < 16
                or hmac.compare_digest(token, binding_key)
            ):
                raise ValueError("Application secret values are invalid")
            resolved_values.extend([token, binding_key])
        if len(resolved_values) != len(set(resolved_values)):
            raise ValueError(
                "Application roles must use pairwise-distinct secret values"
            )
        return ProbeResult(
            name=self.name,
            ready=True,
            detail="exact_secret_versions_resolved",
            operation="secret_manager_exact_version_access",
        )


@dataclass(frozen=True)
class RuntimeLimitsProbe:
    path: Path
    name: str = "runtime_limits"

    def check(self) -> ProbeResult:
        limits = load_runtime_limits(self.path)
        ready = (
            limits["surface"] == "aigc-gemini-only"
            and limits["security"]["legacy_routes_allowed"] is False
            and limits["security"]["generative_readiness_probe_allowed"] is False
            and limits["security"]["external_business_action_allowed"] is False
            and limits["security"]["provider_transport_attempts"] == 1
        )
        return ProbeResult(
            name=self.name,
            ready=ready,
            detail="runtime_limits_valid" if ready else "runtime_limits_invalid",
            operation="local_file_validation",
        )


@dataclass(frozen=True)
class GcsReadProbe:
    settings_factory: Callable[[], GeminiWorkflowSettings]
    client_factory: Callable[[GeminiWorkflowSettings], Any]
    timeout_seconds: int
    name: str = "gcs_evidence_read"

    def check(self) -> ProbeResult:
        settings = self.settings_factory()
        if settings.evidence_backend != "gcs" or not settings.evidence_bucket:
            raise ValueError("Durable GCS evidence is not configured")
        client = self.client_factory(settings)
        blobs = client.list_blobs(
            settings.evidence_bucket,
            prefix=f"{settings.evidence_prefix}/",
            max_results=1,
            timeout=self.timeout_seconds,
            retry=None,
        )
        next(iter(blobs), None)
        return ProbeResult(
            name=self.name,
            ready=True,
            detail="evidence_prefix_read_succeeded",
            operation="cloud_storage_metadata_read",
        )


@dataclass(frozen=True)
class VertexModelMetadataProbe:
    settings_factory: Callable[[], GeminiWorkflowSettings]
    client_factory: Callable[[GeminiWorkflowSettings, int], Any]
    timeout_seconds: int
    name: str = "vertex_model_metadata"

    def check(self) -> ProbeResult:
        settings = self.settings_factory()
        client = self.client_factory(settings, self.timeout_seconds)
        model = client.models.get(model=settings.model)
        if not getattr(model, "name", None):
            raise ValueError("Vertex AI returned incomplete model metadata")
        return ProbeResult(
            name=self.name,
            ready=True,
            detail="model_metadata_read_succeeded",
            operation="vertex_model_metadata_read",
        )


@dataclass(frozen=True)
class RuntimeControlProbe:
    settings_factory: Callable[[], GeminiWorkflowSettings]
    store_factory: Callable[[GeminiWorkflowSettings], Any]
    name: str = "runtime_control_database"

    def check(self) -> ProbeResult:
        settings = self.settings_factory()
        store = self.store_factory(settings)
        health = store.healthcheck()
        ready = (
            getattr(health, "ok", False) is True
            and getattr(health, "durable", False) is True
            and getattr(health, "backend", "") == "postgresql"
            and getattr(health, "emergency_active", True) is False
        )
        return ProbeResult(
            name=self.name,
            ready=ready,
            detail=(
                "runtime_control_read_succeeded"
                if ready
                else "runtime_control_read_failed"
            ),
            operation="cloud_sql_readiness_query",
        )


@dataclass(frozen=True)
class JudgeConfigurationProbe:
    environ: Mapping[str, str]
    name: str = "configuration"

    def check(self) -> ProbeResult:
        ready = (
            self.environ.get("AIGC_SURFACE", "").strip().lower() == "judge"
            and self.environ.get("AIGC_GEMINI_ENABLED", "").strip().lower()
            not in {"1", "true", "yes", "on"}
            and bool(self.environ.get("GOOGLE_CLOUD_PROJECT", "").strip())
            and bool(
                self.environ.get("AIGC_JUDGE_RECEIPT_BUCKET", "").strip()
            )
            and bool(
                self.environ.get("AIGC_JUDGE_RECEIPT_PREFIX", "").strip()
            )
        )
        return ProbeResult(
            name=self.name,
            ready=ready,
            detail=(
                "judge_configuration_valid"
                if ready
                else "judge_configuration_invalid"
            ),
            operation="local_configuration_validation",
        )


@dataclass(frozen=True)
class GcsObjectMetadataProbe:
    project_id_factory: Callable[[], str]
    bucket_factory: Callable[[], str]
    object_name_factory: Callable[[], str]
    client_factory: Callable[[str], Any]
    timeout_seconds: int
    name: str = "gcs_judge_receipt_read"

    def check(self) -> ProbeResult:
        project_id = self.project_id_factory().strip()
        bucket_name = self.bucket_factory().strip()
        object_name = self.object_name_factory().strip()
        if not project_id or not bucket_name or not object_name:
            raise ValueError("Judge readiness object is not configured")
        blob = self.client_factory(project_id).bucket(bucket_name).blob(
            object_name
        )
        blob.reload(timeout=self.timeout_seconds, retry=None)
        if not getattr(blob, "generation", None):
            raise ValueError("Judge readiness object has no generation")
        return ProbeResult(
            name=self.name,
            ready=True,
            detail="judge_readiness_object_metadata_succeeded",
            operation="cloud_storage_generation_metadata_read",
        )


def load_runtime_limits(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Runtime limits must be a JSON object")
    if raw.get("schema_version") != "1.0":
        raise ValueError("Unsupported runtime-limits schema")
    if not isinstance(raw.get("server"), dict):
        raise ValueError("Runtime limits require server settings")
    if not isinstance(raw.get("readiness"), dict):
        raise ValueError("Runtime limits require readiness settings")
    if not isinstance(raw.get("security"), dict):
        raise ValueError("Runtime limits require security settings")

    concurrency = raw["server"].get("concurrency_limit")
    keep_alive = raw["server"].get("keep_alive_seconds")
    cache_ttl = raw["readiness"].get("cache_ttl_seconds")
    probe_timeout = raw["readiness"].get("probe_timeout_seconds")
    required_probes = raw["readiness"].get("required_probes")
    if not isinstance(concurrency, int) or not 1 <= concurrency <= 32:
        raise ValueError("Invalid concurrency limit")
    if not isinstance(keep_alive, int) or not 1 <= keep_alive <= 30:
        raise ValueError("Invalid keep-alive limit")
    if not isinstance(cache_ttl, int) or not 0 <= cache_ttl <= 60:
        raise ValueError("Invalid readiness cache TTL")
    if not isinstance(probe_timeout, int) or not 1 <= probe_timeout <= 10:
        raise ValueError("Invalid readiness probe timeout")
    if required_probes != [
        "configuration",
        "application_secrets",
        "runtime_limits",
        "gcs_evidence_read",
        "runtime_control_database",
        "vertex_model_metadata",
    ]:
        raise ValueError("Required readiness probes do not match the contract")
    return raw


def _runtime_limits_path() -> Path:
    value = os.environ.get(RUNTIME_LIMITS_ENV, "").strip()
    return Path(value) if value else DEFAULT_RUNTIME_LIMITS_PATH


def _readiness_number(name: str, default: int) -> int:
    try:
        value = load_runtime_limits(_runtime_limits_path())["readiness"][name]
        return int(value)
    except Exception:
        return default


def _storage_client(settings: GeminiWorkflowSettings) -> Any:
    from google.cloud import storage

    return storage.Client(project=settings.project_id)


def _evidence_readiness_object(
    settings_factory: Callable[[], GeminiWorkflowSettings],
) -> str:
    configured = os.environ.get(
        "AIGC_GEMINI_EVIDENCE_READINESS_OBJECT",
        "",
    ).strip()
    if configured:
        return configured
    settings = settings_factory()
    return f"{settings.evidence_prefix}/readiness.json"


def _vertex_client(
    settings: GeminiWorkflowSettings,
    timeout_seconds: int,
) -> Any:
    from google import genai
    from google.genai import types

    return genai.Client(
        vertexai=True,
        project=settings.project_id,
        location=settings.location,
        http_options=types.HttpOptions(
            api_version="v1",
            timeout=timeout_seconds * 1_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


@lru_cache(maxsize=1)
def _runtime_control_store(
    settings: GeminiWorkflowSettings,
) -> PostgresRuntimeControlStore:
    control_dsn = settings.control_dsn
    if settings.environment == "production":
        control_dsn, _receipt = OmegaXSecretAccess.from_environment(
            project_id=settings.project_id
        ).resolve("gemini-runtime-control-dsn")
    return PostgresRuntimeControlStore.from_dsn(control_dsn)


@lru_cache(maxsize=1)
def build_default_evaluator() -> ReadinessEvaluator:
    settings_factory = GeminiWorkflowSettings.from_env
    timeout_seconds = _readiness_number("probe_timeout_seconds", 5)
    return ReadinessEvaluator(
        [
            ConfigurationProbe(settings_factory),
            SecretPresenceProbe(os.environ),
            RuntimeLimitsProbe(_runtime_limits_path()),
            GcsObjectMetadataProbe(
                lambda: settings_factory().project_id,
                lambda: settings_factory().evidence_bucket,
                lambda: _evidence_readiness_object(settings_factory),
                lambda project_id: __import__(
                    "google.cloud.storage",
                    fromlist=["storage"],
                ).Client(project=project_id),
                timeout_seconds,
                name="gcs_evidence_read",
            ),
            RuntimeControlProbe(
                settings_factory,
                _runtime_control_store,
            ),
            VertexModelMetadataProbe(
                settings_factory,
                _vertex_client,
                timeout_seconds,
            ),
        ],
        cache_ttl_seconds=_readiness_number("cache_ttl_seconds", 10),
    )


@lru_cache(maxsize=2)
def build_surface_evaluator(
    surface: Literal["operator", "judge"],
) -> ReadinessEvaluator:
    timeout_seconds = _readiness_number("probe_timeout_seconds", 5)
    cache_ttl = _readiness_number("cache_ttl_seconds", 10)
    project_factory = lambda: os.environ.get(
        "GOOGLE_CLOUD_PROJECT",
        "",
    )
    if surface == "judge":
        return ReadinessEvaluator(
            [
                JudgeConfigurationProbe(os.environ),
                SecretReferenceProbe(
                    project_factory,
                    ("judge",),
                    os.environ,
                ),
                RuntimeLimitsProbe(_runtime_limits_path()),
                GcsObjectMetadataProbe(
                    project_factory,
                    lambda: os.environ.get(
                        "AIGC_JUDGE_RECEIPT_BUCKET",
                        "",
                    ),
                    lambda: os.environ.get(
                        "AIGC_JUDGE_READINESS_OBJECT",
                        "judge-receipts/v1/readiness.json",
                    ),
                    lambda project_id: __import__(
                        "google.cloud.storage",
                        fromlist=["storage"],
                    ).Client(project=project_id),
                    timeout_seconds,
                ),
            ],
            cache_ttl_seconds=cache_ttl,
        )

    settings_factory = GeminiWorkflowSettings.from_env
    return ReadinessEvaluator(
        [
            ConfigurationProbe(settings_factory),
            SecretReferenceProbe(
                project_factory,
                ("operator", "runtime_admin"),
                os.environ,
            ),
            RuntimeLimitsProbe(_runtime_limits_path()),
            GcsObjectMetadataProbe(
                lambda: settings_factory().project_id,
                lambda: settings_factory().evidence_bucket,
                lambda: _evidence_readiness_object(settings_factory),
                lambda project_id: __import__(
                    "google.cloud.storage",
                    fromlist=["storage"],
                ).Client(project=project_id),
                timeout_seconds,
                name="gcs_evidence_read",
            ),
            RuntimeControlProbe(
                settings_factory,
                _runtime_control_store,
            ),
            VertexModelMetadataProbe(
                settings_factory,
                _vertex_client,
                timeout_seconds,
            ),
        ],
        cache_ttl_seconds=cache_ttl,
    )


_EVALUATOR_OVERRIDE: ReadinessEvaluator | None = None


def set_readiness_evaluator_override(
    evaluator: ReadinessEvaluator | None,
) -> None:
    global _EVALUATOR_OVERRIDE
    _EVALUATOR_OVERRIDE = evaluator
    build_default_evaluator.cache_clear()


def _evaluator() -> ReadinessEvaluator:
    return _EVALUATOR_OVERRIDE or build_default_evaluator()


def require_operator_header(request: Request) -> OperatorIdentity:
    if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin", "").strip()
        if origin:
            origin_host = urlsplit(origin).netloc.lower()
            request_host = request.headers.get("host", "").strip().lower()
            if not origin_host or origin_host != request_host:
                raise HTTPException(
                    status_code=403,
                    detail="Cross-origin state-changing request rejected.",
                )

    expected = os.environ.get(COMMAND_TOKEN_ENV, "").strip()
    subject_key = os.environ.get(OPERATOR_SUBJECT_KEY_ENV, "").strip()
    if (
        len(expected) < 32
        or len(subject_key) < 32
        or hmac.compare_digest(expected, subject_key)
    ):
        raise HTTPException(
            status_code=503,
            detail="Application authentication is not safely configured.",
        )
    supplied = request.headers.get("x-aigc-command-token", "").strip()
    label = (
        request.headers.get("x-aigc-operator-label", "").strip()
        or "unlabeled-api-operator"
    )
    if len(label) > 100:
        raise HTTPException(status_code=400, detail="Operator label is too long.")
    try:
        return authenticate_shared_credential(
            provided_token=supplied,
            expected_token=expected,
            credential_binding_key=subject_key,
            role="operator",
            attested_label=label,
        )
    except GeminiAuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail="Operator authentication required.",
        ) from exc


app = FastAPI(
    title="AIGC Governed Gemini API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(create_router(require_operator_header))


@app.get("/livez", include_in_schema=False)
def livez() -> dict[str, Any]:
    return {
        "live": True,
        "status": "live",
        "generative_call_performed": False,
        "external_action_performed": False,
    }


@app.get("/readyz", include_in_schema=False)
def readyz() -> JSONResponse:
    report = _evaluator().evaluate()
    return JSONResponse(
        content=report.as_dict(),
        status_code=200 if report.ready else 503,
    )
