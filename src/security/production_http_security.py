from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
import json
from pathlib import Path
import re
import threading
import time
from typing import Any, Mapping
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.security.redactor import Redactor


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = ROOT / "config" / "production_security_privacy_baseline.json"
DEFAULT_SCHEMA_PATH = ROOT / "schemas" / "production_security_privacy_baseline.schema.json"

_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "password",
    "secret",
    "secret_value",
    "private_key",
    "recovery_code",
    "provider_claims",
    "raw_assertion",
    "nonce",
}


class ProductionSecurityPolicyError(ValueError):
    """Raised when the production security/privacy baseline is malformed."""


@dataclass(frozen=True)
class ProductionSecurityEvaluation:
    status: str
    implemented_internal: bool
    production_complete: bool
    blocking_evidence: tuple[str, ...]
    provisional_controls: tuple[str, ...]
    enabled_production_connectors: tuple[str, ...]
    external_action_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": "AIGC-PRODUCTION-SECURITY-EVALUATION-001",
            "contract_version": "1.0.0",
            "status": self.status,
            "implemented_internal": self.implemented_internal,
            "production_complete": self.production_complete,
            "blocking_evidence": list(self.blocking_evidence),
            "provisional_controls": list(self.provisional_controls),
            "enabled_production_connectors": list(self.enabled_production_connectors),
            "external_action_performed": self.external_action_performed,
        }


def load_security_policy(
    policy_path: str | Path = DEFAULT_POLICY_PATH,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    try:
        policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionSecurityPolicyError(
            "Unable to load the production security/privacy baseline"
        ) from exc
    if not isinstance(policy, dict) or not isinstance(schema, dict):
        raise ProductionSecurityPolicyError("Security policy and schema must be objects")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(policy), key=lambda item: list(item.absolute_path))
    if errors:
        details: list[str] = []
        for error in errors[:10]:
            location = "$"
            if error.absolute_path:
                location += "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error.absolute_path
                )
            details.append(f"{location}: {error.message}")
        raise ProductionSecurityPolicyError(
            "Production security/privacy validation failed: " + "; ".join(details)
        )
    return policy


def evaluate_security_policy(policy: Mapping[str, Any]) -> ProductionSecurityEvaluation:
    value = dict(policy)
    evidence = dict(value["operational_evidence"])
    blockers = tuple(
        name
        for name in (
            "staging_tls_observed",
            "edge_rate_limit_observed",
            "sbom_generated",
            "vulnerability_scan_passed",
            "incident_exercise_passed",
            "independent_review_passed",
        )
        if evidence.get(name) is not True
    )
    provisional: list[str] = []
    if value["data_classification"]["status"] != "APPROVED":
        provisional.append("data_classification_register")
    if value["privacy"]["deletion_export_policy_status"] != "APPROVED":
        provisional.append("deletion_export_policy")
    if value["secrets"]["rotation_procedure_status"] != "APPROVED":
        provisional.append("secret_rotation_procedure")
    if int(evidence.get("unresolved_high_critical_findings", 0)) > 0:
        blockers += ("unresolved_high_critical_findings",)

    implemented = (
        value.get("status") == "IMPLEMENTED_INTERNAL_PENDING_OPERATIONAL_EVIDENCE"
        and value["authority"]["internal_control_implementation_authorized"] is True
        and value["external_action_performed"] is False
    )
    production_complete = implemented and not blockers and not provisional
    return ProductionSecurityEvaluation(
        status="complete" if production_complete else "implemented_internal",
        implemented_internal=implemented,
        production_complete=production_complete,
        blocking_evidence=blockers,
        provisional_controls=tuple(provisional),
        enabled_production_connectors=(),
    )


def redact_security_event(value: Any) -> Any:
    """Return a minimum-necessary structure safe for structured security logging."""

    redactor = Redactor()
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in _SENSITIVE_KEYS or any(
                marker in normalized
                for marker in ("password", "token", "secret", "private_key", "cookie")
            ):
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = redact_security_event(child)
        return result
    if isinstance(value, list):
        return [redact_security_event(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_security_event(item) for item in value)
    if isinstance(value, str):
        return redactor.redact_text(value)
    return value


class _FixedWindowRateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self.limit = requests_per_minute
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        current = now if now is not None else time.monotonic()
        threshold = current - 60.0
        with self._lock:
            events = self._events[key]
            while events and events[0] <= threshold:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(current)
            return True


class ProductionSecurityMiddleware(BaseHTTPMiddleware):
    """Local enforcement of the production HTTP security baseline.

    Cloud-edge controls remain separate operational evidence. This middleware
    does not claim TLS termination, distributed rate limiting, WAF coverage, or
    production deployment.
    """

    def __init__(self, app: Any, policy_path: str | Path = DEFAULT_POLICY_PATH) -> None:
        super().__init__(app)
        self.policy = load_security_policy(policy_path)
        http = dict(self.policy["http_security"])
        self.allowed_hosts = {str(item).lower() for item in http["allowed_hosts"]}
        self.max_request_bytes = int(http["max_request_bytes"])
        self.allowed_origins = {str(item) for item in http["cors_allowed_origins"]}
        self.protected_cookies = tuple(str(item) for item in http["csrf_protected_cookie_names"])
        self.csrf_cookie_name = str(http["csrf_cookie_name"])
        self.csrf_header_name = str(http["csrf_header_name"])
        self.headers = dict(http["response_headers"])
        self.sensitive_prefixes = tuple(str(item) for item in http["sensitive_path_prefixes"])
        self.rate_limiter = _FixedWindowRateLimiter(int(http["requests_per_minute"]))

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = self._request_id(request)
        host = (request.url.hostname or "").lower()
        if host not in self.allowed_hosts:
            return self._error(400, "HOST_NOT_ALLOWED", request_id)

        origin = request.headers.get("origin")
        if origin and origin not in self.allowed_origins:
            return self._error(403, "CROSS_ORIGIN_REQUEST_DENIED", request_id)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                return self._error(400, "INVALID_CONTENT_LENGTH", request_id)
            if size < 0 or size > self.max_request_bytes:
                return self._error(413, "REQUEST_BODY_TOO_LARGE", request_id)

        client = request.client.host if request.client else "unknown"
        if not self.rate_limiter.allow(f"{client}:{host}"):
            response = self._error(429, "RATE_LIMIT_EXCEEDED", request_id)
            response.headers["Retry-After"] = "60"
            return response

        if request.method.upper() in _UNSAFE_METHODS and any(
            name in request.cookies for name in self.protected_cookies
        ):
            expected = request.cookies.get(self.csrf_cookie_name)
            supplied = request.headers.get(self.csrf_header_name)
            if not expected or not supplied or not hmac.compare_digest(expected, supplied):
                return self._error(403, "CSRF_VALIDATION_FAILED", request_id)

        response = await call_next(request)
        self._apply_headers(request, response, request_id)
        return response

    @staticmethod
    def _request_id(request: Request) -> str:
        supplied = request.headers.get("x-request-id", "")
        if supplied and _REQUEST_ID.fullmatch(supplied):
            return supplied
        return "req_" + uuid4().hex

    def _apply_headers(self, request: Request, response: Response, request_id: str) -> None:
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = self.headers["x_content_type_options"]
        response.headers["X-Frame-Options"] = self.headers["x_frame_options"]
        response.headers["Referrer-Policy"] = self.headers["referrer_policy"]
        response.headers["Permissions-Policy"] = self.headers["permissions_policy"]
        response.headers["Content-Security-Policy"] = self.headers["content_security_policy"]
        response.headers["Cross-Origin-Opener-Policy"] = self.headers["cross_origin_opener_policy"]
        response.headers["Cross-Origin-Resource-Policy"] = self.headers["cross_origin_resource_policy"]
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = self.headers[
                "strict_transport_security"
            ]
        if request.url.path.startswith(self.sensitive_prefixes):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        if "server" in response.headers:
            del response.headers["server"]

    def _error(self, status_code: int, code: str, request_id: str) -> JSONResponse:
        response = JSONResponse(
            status_code=status_code,
            content={
                "detail": {
                    "code": code,
                    "message": "Request denied by the AIGC security boundary.",
                    "request_id": request_id,
                    "external_action_performed": False,
                }
            },
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response


def security_status() -> dict[str, Any]:
    policy = load_security_policy()
    evaluation = evaluate_security_policy(policy)
    return {
        **evaluation.to_dict(),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
