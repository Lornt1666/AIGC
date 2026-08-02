"""Production-oriented Gmail draft adapter with governed activation and no send method."""
from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
FORBIDDEN_SCOPES = frozenset({
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
})
ALLOWED_METHODS = frozenset({"users.drafts.create", "users.drafts.get", "users.getProfile"})


def _digest_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _load_json(path: Path | str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Gmail runtime configuration must be an object")
    return value


def _remove_single_terminal_line_ending(value: str) -> str:
    """Remove the MIME serializer's one terminal line ending without trimming body content."""
    if value.endswith("\r\n"):
        return value[:-2]
    if value.endswith(("\n", "\r")):
        return value[:-1]
    return value


class CredentialResolver(Protocol):
    def resolve_access_credential(self) -> str: ...
    def revoke(self) -> None: ...


class GmailHttpTransport(Protocol):
    def request(self, *, method: str, url: str, access_credential: str, body: Mapping[str, Any] | None = None) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class GmailRuntimeConfig:
    enabled: bool
    environment: str
    test_account_mode: bool
    account_email: str
    account_fingerprint: str
    oauth_scopes: tuple[str, ...]
    credential_environment_variable: str
    activation_record_path: str
    canary_receipt_path: str


class EnvironmentCredentialResolver:
    """Resolves one runtime credential from an environment variable; never persists it."""

    def __init__(self, environment_variable: str) -> None:
        if not environment_variable or not environment_variable.replace("_", "").isalnum():
            raise ValueError("credential environment variable name is invalid")
        self._environment_variable = environment_variable

    def resolve_access_credential(self) -> str:
        value = os.environ.get(self._environment_variable, "").strip()
        if len(value) < 20:
            raise PermissionError("Gmail access credential is unavailable")
        return value

    def revoke(self) -> None:
        os.environ.pop(self._environment_variable, None)


class UrllibGmailTransport:
    """Minimal Gmail REST transport; only callers define permitted endpoints."""

    def request(self, *, method: str, url: str, access_credential: str, body: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = None if body is None else json.dumps(dict(body), separators=(",", ":")).encode("utf-8")
        request = Request(
            url,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {access_credential}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed Google endpoint only
                value = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("Gmail provider request failed") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Gmail provider returned a non-object response")
        return value


def load_runtime_config(path: Path | str) -> GmailRuntimeConfig:
    value = _load_json(path)
    scopes = tuple(str(item) for item in value.get("oauth_scopes", []))
    if scopes != (GMAIL_COMPOSE_SCOPE,):
        raise ValueError("runtime must request exactly the least-privilege gmail.compose scope")
    if FORBIDDEN_SCOPES.intersection(scopes):
        raise ValueError("forbidden Gmail scope configured")
    email = str(value.get("account_email") or "").strip().lower()
    fingerprint = str(value.get("account_fingerprint") or "").strip()
    if not email or fingerprint != _digest_text(email):
        raise ValueError("account fingerprint does not match configured Gmail account")
    environment = str(value.get("environment") or "").upper()
    test_mode = value.get("test_account_mode") is True
    enabled = value.get("enabled") is True
    if enabled and environment != "TEST" and not Path(str(value.get("canary_receipt_path") or "")).is_file():
        raise PermissionError("non-test activation requires a controlled test-account canary receipt")
    return GmailRuntimeConfig(
        enabled=enabled,
        environment=environment,
        test_account_mode=test_mode,
        account_email=email,
        account_fingerprint=fingerprint,
        oauth_scopes=scopes,
        credential_environment_variable=str(value.get("credential_environment_variable") or ""),
        activation_record_path=str(value.get("activation_record_path") or ""),
        canary_receipt_path=str(value.get("canary_receipt_path") or ""),
    )


def _verified_activation(config: GmailRuntimeConfig) -> dict[str, Any]:
    if not config.enabled:
        raise PermissionError("Gmail connector is disabled")
    path = Path(config.activation_record_path)
    if not path.is_file():
        raise PermissionError("governed Gmail activation record is unavailable")
    record = _load_json(path)
    required = {
        "status": "ACTIVATED_DRAFT_ONLY",
        "account_fingerprint": config.account_fingerprint,
        "scope": GMAIL_COMPOSE_SCOPE,
        "send_capability_present": False,
        "emergency_stop_required": True,
    }
    if any(record.get(key) != expected for key, expected in required.items()):
        raise PermissionError("Gmail activation record is invalid")
    if config.environment != "TEST" and record.get("test_canary_verified") is not True:
        raise PermissionError("non-test connector activation requires a verified test canary")
    return record


class GovernedGmailDraftProvider:
    """Implements only the Increment 8 create/get draft provider contract."""

    def __init__(self, config: GmailRuntimeConfig, resolver: CredentialResolver, transport: GmailHttpTransport | None = None) -> None:
        _verified_activation(config)
        self._config = config
        self._resolver = resolver
        self._transport = transport or UrllibGmailTransport()
        self.account_fingerprint = config.account_fingerprint

    @property
    def supported_methods(self) -> frozenset[str]:
        return ALLOWED_METHODS

    def _credential(self) -> str:
        return self._resolver.resolve_access_credential()

    def health(self) -> dict[str, Any]:
        profile = self._transport.request(
            method="GET",
            url="https://gmail.googleapis.com/gmail/v1/users/me/profile",
            access_credential=self._credential(),
        )
        observed_email = str(profile.get("emailAddress") or "").strip().lower()
        if _digest_text(observed_email) != self.account_fingerprint:
            raise PermissionError("authenticated Gmail account does not match the governed fingerprint")
        return {
            "status": "HEALTHY_DRAFT_ONLY",
            "account_fingerprint": self.account_fingerprint,
            "scope": GMAIL_COMPOSE_SCOPE,
            "test_account_mode": self._config.test_account_mode,
            "send_capability_present": False,
        }

    def create_draft(self, *, to: str, subject: str, body: str, idempotency_key: str) -> Mapping[str, Any]:
        self.health()
        if not to or not body or len(idempotency_key) != 64:
            raise ValueError("exact draft payload and idempotency key are required")
        message = EmailMessage()
        message["To"] = to
        message["From"] = self._config.account_email
        message["Subject"] = subject
        message["X-AIGC-Idempotency-Key"] = idempotency_key
        message.set_content(body)
        raw = urlsafe_b64encode(message.as_bytes(policy=policy.SMTP)).decode("ascii").rstrip("=")
        value = self._transport.request(
            method="POST",
            url="https://gmail.googleapis.com/gmail/v1/users/me/drafts",
            access_credential=self._credential(),
            body={"message": {"raw": raw}},
        )
        draft_id = str(value.get("id") or "")
        if not draft_id:
            raise RuntimeError("Gmail did not return a draft identifier")
        return {"draft_id": draft_id}

    def get_draft(self, draft_id: str) -> Mapping[str, Any]:
        if not draft_id:
            raise ValueError("draft identifier is required")
        value = self._transport.request(
            method="GET",
            url=f"https://gmail.googleapis.com/gmail/v1/users/me/drafts/{quote(draft_id, safe='')}?format=raw",
            access_credential=self._credential(),
        )
        raw = str((value.get("message") or {}).get("raw") or "")
        padded = raw + "=" * (-len(raw) % 4)
        try:
            message = BytesParser(policy=policy.default).parsebytes(urlsafe_b64decode(padded.encode("ascii")))
        except Exception as exc:
            raise RuntimeError("Gmail draft content could not be decoded") from exc
        body = message.get_body(preferencelist=("plain",))
        text = body.get_content() if body is not None else message.get_content()
        return {
            "to": str(message.get("To") or ""),
            "subject": str(message.get("Subject") or ""),
            "body": _remove_single_terminal_line_ending(str(text)),
            "sent": False,
        }

    def revoke(self) -> dict[str, Any]:
        self._resolver.revoke()
        return {"status": "LOCAL_CREDENTIAL_REMOVED", "account_fingerprint": self.account_fingerprint, "send_performed": False}


def connector_status(config_path: Path | str) -> dict[str, Any]:
    config = load_runtime_config(config_path)
    return {
        "enabled": config.enabled,
        "environment": config.environment,
        "test_account_mode": config.test_account_mode,
        "account_fingerprint": config.account_fingerprint,
        "oauth_scopes": list(config.oauth_scopes),
        "send_scope_requested": False,
        "send_method_present": False,
        "canary_required_for_non_test": True,
    }
