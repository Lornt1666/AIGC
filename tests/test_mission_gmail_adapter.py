from __future__ import annotations

from base64 import urlsafe_b64decode
from hashlib import sha256
import json
from pathlib import Path

import pytest

from src.mission_os.gmail_adapter import (
    GMAIL_COMPOSE_SCOPE,
    EnvironmentCredentialResolver,
    GovernedGmailDraftProvider,
    connector_status,
    load_runtime_config,
)


def _fingerprint(email: str) -> str:
    return sha256(email.lower().encode()).hexdigest()


def _config(tmp_path: Path, *, enabled: bool = True, environment: str = "TEST", test_mode: bool = True) -> Path:
    email = "aigc-canary@example.test"
    activation = tmp_path / "activation.json"
    activation.write_text(json.dumps({
        "status": "ACTIVATED_DRAFT_ONLY",
        "account_fingerprint": _fingerprint(email),
        "scope": GMAIL_COMPOSE_SCOPE,
        "send_capability_present": False,
        "emergency_stop_required": True,
        "test_canary_verified": environment == "TEST",
    }))
    config = tmp_path / "gmail.json"
    config.write_text(json.dumps({
        "schema_version": "1.0.0",
        "enabled": enabled,
        "environment": environment,
        "test_account_mode": test_mode,
        "account_email": email,
        "account_fingerprint": _fingerprint(email),
        "oauth_scopes": [GMAIL_COMPOSE_SCOPE],
        "credential_environment_variable": "AIGC_GMAIL_ACCESS_CREDENTIAL",
        "activation_record_path": str(activation),
        "canary_receipt_path": str(tmp_path / "canary.json"),
    }))
    return config


class Resolver:
    def __init__(self) -> None:
        self.revoked = False

    def resolve_access_credential(self) -> str:
        return "x" * 32

    def revoke(self) -> None:
        self.revoked = True


class Transport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.raw = ""

    def request(self, *, method: str, url: str, access_credential: str, body=None):
        assert access_credential == "x" * 32
        self.calls.append((method, url))
        if url.endswith("/profile"):
            return {"emailAddress": "aigc-canary@example.test"}
        if method == "POST":
            self.raw = body["message"]["raw"]
            return {"id": "draft-1"}
        padded = self.raw + "=" * (-len(self.raw) % 4)
        assert b"X-AIGC-Idempotency-Key" in urlsafe_b64decode(padded.encode())
        return {"id": "draft-1", "message": {"raw": self.raw}}


def test_config_is_disabled_by_default_and_exact_scope_only(tmp_path: Path) -> None:
    config = _config(tmp_path, enabled=False)
    status = connector_status(config)
    assert status["enabled"] is False
    assert status["oauth_scopes"] == [GMAIL_COMPOSE_SCOPE]
    assert status["send_scope_requested"] is False
    assert status["send_method_present"] is False


def test_broad_or_send_scope_is_rejected(tmp_path: Path) -> None:
    config = _config(tmp_path)
    value = json.loads(config.read_text())
    value["oauth_scopes"] = ["https://www.googleapis.com/auth/gmail.send"]
    config.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="exactly"):
        load_runtime_config(config)


def test_exact_account_fingerprint_is_enforced(tmp_path: Path) -> None:
    config = _config(tmp_path)
    value = json.loads(config.read_text())
    value["account_fingerprint"] = "0" * 64
    config.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="fingerprint"):
        load_runtime_config(config)


def test_non_test_activation_requires_canary(tmp_path: Path) -> None:
    config = _config(tmp_path, environment="PRODUCTION", test_mode=False)
    with pytest.raises(PermissionError, match="canary"):
        load_runtime_config(config)


def test_create_and_read_back_draft_without_send_method(tmp_path: Path) -> None:
    config = load_runtime_config(_config(tmp_path))
    resolver = Resolver()
    transport = Transport()
    provider = GovernedGmailDraftProvider(config, resolver, transport)
    health = provider.health()
    assert health["send_capability_present"] is False
    created = provider.create_draft(to="client@example.test", subject="Proposal", body="Reviewed body", idempotency_key="a" * 64)
    fetched = provider.get_draft(created["draft_id"])
    assert fetched == {"to": "client@example.test", "subject": "Proposal", "body": "Reviewed body", "sent": False}
    assert not hasattr(provider, "send")
    assert all("/send" not in url for _, url in transport.calls)


def test_authenticated_account_mismatch_fails_closed(tmp_path: Path) -> None:
    class WrongTransport(Transport):
        def request(self, **kwargs):
            if kwargs["url"].endswith("/profile"):
                return {"emailAddress": "wrong@example.test"}
            return super().request(**kwargs)

    provider = GovernedGmailDraftProvider(load_runtime_config(_config(tmp_path)), Resolver(), WrongTransport())
    with pytest.raises(PermissionError, match="fingerprint"):
        provider.health()


def test_revoke_removes_runtime_credential_without_external_send(tmp_path: Path) -> None:
    resolver = Resolver()
    provider = GovernedGmailDraftProvider(load_runtime_config(_config(tmp_path)), resolver, Transport())
    receipt = provider.revoke()
    assert resolver.revoked is True
    assert receipt["send_performed"] is False


def test_environment_resolver_never_persists_credential(monkeypatch) -> None:
    monkeypatch.setenv("AIGC_GMAIL_ACCESS_CREDENTIAL", "y" * 32)
    resolver = EnvironmentCredentialResolver("AIGC_GMAIL_ACCESS_CREDENTIAL")
    assert resolver.resolve_access_credential() == "y" * 32
    resolver.revoke()
    with pytest.raises(PermissionError):
        resolver.resolve_access_credential()
