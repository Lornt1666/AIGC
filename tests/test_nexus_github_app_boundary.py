from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.domain.nexus.contracts import ExecutionPermit
from src.infrastructure.github.app_credential_boundary import (
    GitHubAppInstallationConfig,
    GitHubAppInstallationReadBoundary,
)


NOW = datetime(2026, 8, 8, 5, 30, tzinfo=timezone.utc)
REPO = "Lornt1666/AIGC"
REVISION = "a" * 40


def private_key() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def permit() -> ExecutionPermit:
    return ExecutionPermit(
        permit_id="PERMIT-GHAPP-TEST01",
        governance_decision_id="GOV-GHAPP-TEST01",
        principal="principal:github-app-test",
        capability="READ_REPOSITORY_STATE",
        resource_scope=(f"github://{REPO}",),
        exact_revision=REVISION,
        change_set_hash="b" * 64,
        request_digest="c" * 64,
        expires_at=NOW + timedelta(minutes=20),
        maximum_invocations=1,
    )


class Response:
    def __init__(self, payload): self._payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self._payload).encode("utf-8")


class FakeGitHub:
    def __init__(self, *, write_permission=False):
        self.requests = []
        self.write_permission = write_permission

    def __call__(self, request, timeout=30):
        self.requests.append(request)
        if request.method == "POST":
            permissions = {
                "contents": "read",
                **({"issues": "write"} if self.write_permission else {}),
            }
            return Response(
                {
                    "token": "fixture-installation-token",
                    "expires_at": (NOW + timedelta(minutes=55)).isoformat(),
                    "permissions": permissions,
                    "repositories": [{"full_name": REPO}],
                }
            )
        raw = b"repository evidence"
        return Response(
            {
                "type": "file",
                "encoding": "base64",
                "content": b64encode(raw).decode("ascii"),
            }
        )


def boundary(fake: FakeGitHub):
    key = private_key()
    return GitHubAppInstallationReadBoundary(
        config=GitHubAppInstallationConfig(
            app_id="123456",
            installation_id=987654,
            repository=REPO,
        ),
        private_key_supplier=lambda: key,
        opener=fake,
        clock=lambda: NOW,
    )


def test_github_app_token_request_is_repository_scoped_and_read_only():
    fake = FakeGitHub()
    value = boundary(fake)
    capability = value.resolve(
        permit=permit(),
        repository=REPO,
        authoritative_now=NOW,
    )
    assert capability.repository == REPO
    assert capability.live_credential is True
    assert "fixture-installation-token" not in repr(capability)
    assert "fixture-installation-token" not in json.dumps(value.repository_health())
    assert value.credential_network_calls == 1
    token_request = fake.requests[0]
    body = json.loads(token_request.data)
    assert body == {
        "repositories": ["AIGC"],
        "permissions": {"contents": "read"},
    }
    assert token_request.method == "POST"


def test_github_app_boundary_rejects_non_read_installation_permission():
    fake = FakeGitHub(write_permission=True)
    value = boundary(fake)
    with pytest.raises(PermissionError, match="non-read permission"):
        value.resolve(
            permit=permit(),
            repository=REPO,
            authoritative_now=NOW,
        )


def test_github_app_read_consumes_token_without_exposing_it():
    fake = FakeGitHub()
    value = boundary(fake)
    capability = value.resolve(
        permit=permit(),
        repository=REPO,
        authoritative_now=NOW,
    )
    result = value.read_state(
        {
            "repository": REPO,
            "exact_revision": REVISION,
            "operation": "READ_FILE",
            "path_or_query": "README.md",
            "sensitivity": "INTERNAL",
            "mutation": False,
        }
    )
    assert result["repository"] == REPO
    assert result["observed_revision"] == REVISION
    assert result["raw_content"] == "repository evidence"
    assert result["source_type"] == "GITHUB_APP_CONTENTS_API_EXACT_REF"
    assert value.network_calls == 1
    assert value.real_github_calls == 1
    assert value.credentials_used == 1
    assert value.repository_writes == 0
    serialized = json.dumps(result, sort_keys=True)
    assert "fixture-installation-token" not in serialized
    assert "fixture-installation-token" not in repr(capability)
    with pytest.raises(Exception, match="has not been resolved"):
        value.read_state(
            {
                "repository": REPO,
                "exact_revision": REVISION,
                "operation": "READ_FILE",
                "path_or_query": "README.md",
                "sensitivity": "INTERNAL",
                "mutation": False,
            }
        )


def test_github_app_boundary_rejects_repository_and_mutation_mismatch_before_read():
    fake = FakeGitHub()
    value = boundary(fake)
    value.resolve(permit=permit(), repository=REPO, authoritative_now=NOW)
    with pytest.raises(Exception, match="mutation"):
        value.read_state(
            {
                "repository": REPO,
                "exact_revision": REVISION,
                "operation": "READ_FILE",
                "path_or_query": "README.md",
                "mutation": True,
            }
        )
    assert value.network_calls == 0
