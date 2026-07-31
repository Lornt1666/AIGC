from __future__ import annotations

from functools import lru_cache
import os
from typing import Any, Callable, Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from src.gemini_workflow.api import create_router
from src.gemini_workflow.auth import (
    GeminiAuthenticationError,
    authenticate_shared_credential,
)
from src.gemini_workflow.judge_receipts import (
    JudgeReceiptNotFoundError,
    JudgeReceiptReadService,
    JudgeReceiptStorageError,
)
from src.gemini_workflow.judge_store import GcsJudgeReceiptReader
from src.gemini_workflow.models import OperatorIdentity
from src.gemini_workflow.readiness import build_surface_evaluator
from src.gemini_workflow.secret_broker import (
    OmegaXSecretAccess,
    SecretBrokerError,
)
from src.webapp.gemini_ui import (
    render_surface_script,
    render_surface_styles,
    render_surface_ui,
)


Surface = Literal["operator", "judge"]


def create_app(
    surface: Surface | None = None,
    *,
    judge_reader: JudgeReceiptReadService | None = None,
    readiness_check: Callable[[], dict[str, Any]] | None = None,
) -> FastAPI:
    selected = surface or _configured_surface()
    effective_readiness = readiness_check or (
        lambda: build_surface_evaluator(selected).evaluate().as_dict()
    )
    application = FastAPI(
        title=(
            "AIGC Governed Gemini Operator"
            if selected == "operator"
            else "AIGC Judge Evidence"
        ),
        version="1.0.0",
        description=(
            "Isolated Gemini production surface for RegenExcalibur's AIGC."
        ),
    )
    application.state.aigc_surface = selected
    application.state.provider_initialized = False
    application.state.control_writer_initialized = False

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; connect-src 'self'; img-src 'self' data:; "
            "style-src 'self'; script-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        return response

    @application.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {
            "status": "live",
            "surface": selected,
            "dependency_probe_performed": False,
            "model_api_call_performed": False,
        }

    @application.get("/readyz")
    def readyz() -> dict[str, Any]:
        report = effective_readiness()
        if not report.get("ready"):
            raise HTTPException(status_code=503, detail=report)
        return report

    @application.get("/", response_class=HTMLResponse)
    def root() -> str:
        return render_surface_ui(selected)

    @application.get(
        "/assets/aigc.css",
        response_class=Response,
        include_in_schema=False,
    )
    def surface_styles() -> Response:
        return Response(
            content=render_surface_styles(),
            media_type="text/css",
        )

    @application.get(
        "/assets/surface.js",
        response_class=Response,
        include_in_schema=False,
    )
    def surface_script() -> Response:
        return Response(
            content=render_surface_script(selected),
            media_type="text/javascript",
        )

    if selected == "operator":
        application.include_router(
            create_router(
                require_operator,
                runtime_admin_dependency=require_runtime_admin,
            )
        )
        application.state.provider_initialized = "lazy_on_authenticated_request"
        application.state.control_writer_initialized = (
            "lazy_on_authenticated_request"
        )
    else:

        def get_reader() -> JudgeReceiptReadService:
            return judge_reader or _default_judge_reader()

        @application.get("/api/judge/receipts/{receipt_id}")
        def get_judge_receipt(
            receipt_id: str,
            _actor: OperatorIdentity = Depends(require_judge),
            reader: JudgeReceiptReadService = Depends(get_reader),
        ) -> dict[str, Any]:
            try:
                return reader.get(receipt_id).model_dump(mode="json")
            except JudgeReceiptNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except JudgeReceiptStorageError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Judge receipt storage is unavailable",
                ) from exc

    return application


def require_operator(request: Request) -> OperatorIdentity:
    return _require_role(request, role="operator")


def require_runtime_admin(request: Request) -> OperatorIdentity:
    return _require_role(request, role="runtime_admin")


def require_judge(request: Request) -> OperatorIdentity:
    return _require_role(request, role="judge")


def _require_role(request: Request, *, role: str) -> OperatorIdentity:
    if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin", "").strip()
        if origin:
            origin_host = urlsplit(origin).netloc.lower()
            request_host = request.headers.get("host", "").strip().lower()
            if not origin_host or origin_host != request_host:
                raise HTTPException(
                    status_code=403,
                    detail="Cross-origin state-changing request rejected",
                )
    token_header = {
        "operator": "x-aigc-operator-token",
        "runtime_admin": "x-aigc-runtime-admin-token",
        "judge": "x-aigc-judge-token",
    }[role]
    label_header = (
        "x-aigc-operator-label"
        if role != "judge"
        else "x-aigc-judge-label"
    )
    try:
        token, binding_key = _role_credentials(role)
        return authenticate_shared_credential(
            provided_token=request.headers.get(token_header, ""),
            expected_token=token,
            credential_binding_key=binding_key,
            role=role,
            attested_label=request.headers.get(label_header, ""),
        )
    except (GeminiAuthenticationError, SecretBrokerError) as exc:
        status = (
            503
            if "configured" in str(exc).lower()
            or isinstance(exc, SecretBrokerError)
            else 401
        )
        raise HTTPException(
            status_code=status,
            detail=(
                "Gemini application authentication is unavailable"
                if status == 503
                else "Gemini authentication failed"
            ),
        ) from exc


@lru_cache(maxsize=3)
def _role_credentials(role: str) -> tuple[str, str]:
    environment = os.environ.get("AIGC_ENV", "development").strip().lower()
    prefix = {
        "operator": "AIGC_OPERATOR",
        "runtime_admin": "AIGC_RUNTIME_ADMIN",
        "judge": "AIGC_JUDGE",
    }[role]
    if environment == "production":
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        if not project_id:
            raise SecretBrokerError(
                "GOOGLE_CLOUD_PROJECT is required for SecretBroker"
            )
        surface = _configured_surface()
        if surface == "judge":
            if role != "judge":
                raise SecretBrokerError(
                    "Judge surface cannot resolve operator credentials"
                )
            return _resolve_production_role(project_id, role)
        if role == "judge":
            raise SecretBrokerError(
                "Operator surface cannot resolve judge credentials"
            )
        credentials = {
            "operator": _resolve_production_role(project_id, "operator"),
            "runtime_admin": _resolve_production_role(
                project_id,
                "runtime_admin",
            ),
        }
        flattened = [
            value
            for pair in credentials.values()
            for value in pair
        ]
        if len(flattened) != len(set(flattened)):
            raise SecretBrokerError(
                "Operator and runtime-admin secrets must be pairwise distinct"
            )
        return credentials[role]

    token = os.environ.get(f"{prefix}_TOKEN", "").strip()
    binding_key = os.environ.get(f"{prefix}_BINDING_KEY", "").strip()
    if role == "operator":
        token = token or os.environ.get(
            "AIGC_COMMAND_CENTER_TOKEN",
            "",
        ).strip()
        binding_key = binding_key or os.environ.get(
            "AIGC_OPERATOR_SUBJECT_KEY",
            "",
        ).strip()
    if not token or not binding_key:
        raise GeminiAuthenticationError(
            f"{prefix} credentials are not configured"
        )
    return token, binding_key


def _configured_surface() -> Surface:
    raw = os.environ.get("AIGC_SURFACE", "").strip()
    environment = os.environ.get("AIGC_ENV", "development").strip().lower()
    if environment == "production" and not raw:
        raise RuntimeError("Production requires an explicit AIGC_SURFACE")
    value = (raw or "operator").lower()
    if value not in {"operator", "judge"}:
        raise RuntimeError("AIGC_SURFACE must be operator or judge")
    return value  # type: ignore[return-value]


def _resolve_production_role(
    project_id: str,
    role: str,
) -> tuple[str, str]:
    access = OmegaXSecretAccess.from_environment(project_id=project_id)
    purpose_role = "runtime-admin" if role == "runtime_admin" else role
    token, _token_receipt = access.resolve(
        f"gemini-{purpose_role}-authentication"
    )
    binding_key, _key_receipt = access.resolve(
        f"gemini-{purpose_role}-principal-binding"
    )
    return token, binding_key


@lru_cache(maxsize=1)
def _default_judge_reader() -> JudgeReceiptReadService:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    bucket_name = os.environ.get(
        "AIGC_JUDGE_RECEIPT_BUCKET",
        "",
    ).strip()
    prefix = os.environ.get(
        "AIGC_JUDGE_RECEIPT_PREFIX",
        "",
    ).strip()
    if not project_id or not bucket_name or not prefix:
        raise HTTPException(
            status_code=503,
            detail="Judge receipt storage is not configured",
        )
    return JudgeReceiptReadService(
        reader=GcsJudgeReceiptReader(
            project_id=project_id,
            bucket_name=bucket_name,
            prefix=prefix,
        )
    )


app = create_app()
