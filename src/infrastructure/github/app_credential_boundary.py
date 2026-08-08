from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import jwt

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.nexus.contracts import ExecutionPermit
from src.infrastructure.github.repository_read_port import (
    RepositoryCredentialCapability,
    RepositoryTransportError,
)


@dataclass(frozen=True)
class GitHubAppInstallationConfig:
    app_id: str
    installation_id: int
    repository: str
    api_version: str = "2026-03-10"

    def __post_init__(self) -> None:
        if not self.app_id.strip():
            raise ValueError("GitHub App app_id is required")
        if self.installation_id <= 0:
            raise ValueError("GitHub App installation_id must be positive")
        if self.repository.count("/") != 1:
            raise ValueError("GitHub App repository must be owner/name")


class GitHubAppInstallationReadBoundary:
    """Production credential + READ_FILE boundary for a repository-scoped GitHub App.

    The private key and installation token never leave this infrastructure object.
    `resolve()` returns only an opaque capability reference. The installation token is
    restricted to the configured repository and read-only contents permission.
    """

    live_credential_resolution = True

    def __init__(
        self,
        *,
        config: GitHubAppInstallationConfig,
        private_key_supplier: Callable[[], str],
        opener: Callable[..., Any] = urlopen,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._config = config
        self._private_key_supplier = private_key_supplier
        self._opener = opener
        self._clock = clock
        self._installation_token = ""
        self._installation_token_expires_at: datetime | None = None
        self.credential_network_calls = 0
        self.network_calls = 0
        self.real_github_calls = 0
        self.credentials_used = 0
        self.repository_writes = 0
        self.resolution_calls = 0

    def repository_health(self):
        return {
            "status": "GITHUB_APP_INSTALLATION_READ_ONLY",
            "repository": self._config.repository,
            "write_capability_present": False,
            "credential_network_calls": self.credential_network_calls,
            "network_calls": self.network_calls,
        }

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("GitHub App credential clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    def _app_jwt(self, *, now: datetime, permit: ExecutionPermit) -> str:
        private_key = self._private_key_supplier()
        if not private_key.strip():
            raise PermissionError("GitHub App private key is unavailable")
        expiry = min(now + timedelta(minutes=9), permit.expires_at.astimezone(timezone.utc))
        token = jwt.encode(
            {
                "iat": int((now - timedelta(seconds=60)).timestamp()),
                "exp": int(expiry.timestamp()),
                "iss": self._config.app_id,
            },
            private_key,
            algorithm="RS256",
        )
        private_key = ""
        return token

    def resolve(
        self,
        *,
        permit: ExecutionPermit,
        repository: str,
        authoritative_now: datetime,
    ) -> RepositoryCredentialCapability:
        self.resolution_calls += 1
        permit.verify_temporal_validity(authoritative_now=authoritative_now)
        if repository != self._config.repository:
            raise PermissionError("GitHub App installation repository mismatch")
        now = authoritative_now.astimezone(timezone.utc)
        app_jwt = self._app_jwt(now=now, permit=permit)
        owner, repo = repository.split("/", 1)
        endpoint = (
            "https://api.github.com/app/installations/"
            f"{self._config.installation_id}/access_tokens"
        )
        body = json.dumps(
            {
                "repositories": [repo],
                "permissions": {"contents": "read"},
            },
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {app_jwt}",
                "X-GitHub-Api-Version": self._config.api_version,
                "Content-Type": "application/json",
                "User-Agent": "AIGC-Nexus-GitHub-App-Credential-Boundary",
            },
        )
        self.credential_network_calls += 1
        try:
            with self._opener(request, timeout=30) as response:
                payload = json.loads(response.read())
        except HTTPError as exc:
            raise PermissionError(f"GitHub App token endpoint returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise PermissionError(
                f"GitHub App token endpoint unavailable: {type(exc).__name__}"
            ) from None
        finally:
            app_jwt = ""

        token = str(payload.get("token") or "")
        expires_at_raw = str(payload.get("expires_at") or "").replace("Z", "+00:00")
        if not token or not expires_at_raw:
            raise PermissionError("GitHub App token endpoint returned incomplete credential data")
        try:
            expires_at = datetime.fromisoformat(expires_at_raw).astimezone(timezone.utc)
        except ValueError:
            raise PermissionError("GitHub App token expiry is invalid") from None
        if expires_at <= now or expires_at > now + timedelta(hours=1, minutes=1):
            raise PermissionError("GitHub App installation token expiry is outside the allowed window")
        permissions = payload.get("permissions") or {}
        if not isinstance(permissions, dict):
            raise PermissionError("GitHub App token permissions are malformed")
        for name, value in permissions.items():
            if str(value).lower() not in {"read", "none"}:
                raise PermissionError(f"GitHub App token exposes non-read permission: {name}")
        if str(permissions.get("contents", "")).lower() != "read":
            raise PermissionError("GitHub App installation token lacks contents:read")

        repositories = payload.get("repositories")
        if repositories is not None:
            names = {
                str(item.get("full_name") or "")
                for item in repositories
                if isinstance(item, dict)
            }
            if names and repository not in names:
                raise PermissionError("GitHub App token is not bound to the requested repository")

        self._installation_token = token
        self._installation_token_expires_at = expires_at
        return RepositoryCredentialCapability(
            capability_ref="GHAPP-" + canonical_sha256(
                {
                    "permit_id": permit.permit_id,
                    "repository": repository,
                    "installation_id": self._config.installation_id,
                    "expires_at": expires_at.isoformat(),
                }
            )[:24].upper(),
            repository=repository,
            expires_at=min(expires_at, permit.expires_at),
            live_credential=True,
        )

    def read_state(self, query):
        token = self._installation_token
        expires_at = self._installation_token_expires_at
        if not token or expires_at is None:
            raise RepositoryTransportError(
                "GitHub App installation credential has not been resolved",
                network_attempted=False,
                outcome_known=True,
            )
        if expires_at <= self._now():
            self._installation_token = ""
            raise RepositoryTransportError(
                "GitHub App installation credential is expired",
                network_attempted=False,
                outcome_known=True,
            )
        if query.get("mutation") not in {None, False}:
            raise RepositoryTransportError(
                "GitHub App read boundary prohibits mutation",
                network_attempted=False,
                outcome_known=True,
            )
        repository = str(query.get("repository") or "")
        revision = str(query.get("exact_revision") or "")
        operation = str(query.get("operation") or "")
        path = str(query.get("path_or_query") or "")
        sensitivity = str(query.get("sensitivity") or "INTERNAL")
        if repository != self._config.repository:
            raise RepositoryTransportError(
                "GitHub App repository mismatch",
                network_attempted=False,
                outcome_known=True,
            )
        if operation != "READ_FILE":
            raise RepositoryTransportError(
                "GitHub App read boundary supports READ_FILE only",
                network_attempted=False,
                outcome_known=True,
            )
        if len(revision) not in {40, 64} or any(ch not in "0123456789abcdef" for ch in revision):
            raise RepositoryTransportError(
                "GitHub App read boundary requires exact hexadecimal revision",
                network_attempted=False,
                outcome_known=True,
            )
        owner, repo = repository.split("/", 1)
        url = (
            "https://api.github.com/repos/"
            f"{quote(owner, safe='')}/{quote(repo, safe='')}/contents/"
            f"{quote(path, safe='/')}?ref={quote(revision, safe='')}"
        )
        request = Request(
            url,
            method="GET",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": self._config.api_version,
                "User-Agent": "AIGC-Nexus-GitHub-App-Read",
            },
        )
        self.network_calls += 1
        self.real_github_calls += 1
        self.credentials_used += 1
        try:
            with self._opener(request, timeout=30) as response:
                payload = json.loads(response.read())
        except HTTPError as exc:
            raise RepositoryTransportError(
                f"GitHub returned HTTP {exc.code}",
                network_attempted=True,
                outcome_known=True,
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise RepositoryTransportError(
                f"GitHub transport outcome is unknown: {type(exc).__name__}",
                network_attempted=True,
                outcome_known=False,
            ) from None
        finally:
            self._installation_token = ""
            token = ""

        try:
            encoded = str(payload.get("content") or "").replace("\n", "")
            raw_bytes = b64decode(encoded, validate=True)
            raw_content = raw_bytes.decode("utf-8")
        except Exception as exc:
            raise RepositoryTransportError(
                f"GitHub returned invalid READ_FILE content: {type(exc).__name__}",
                network_attempted=True,
                outcome_known=True,
            ) from None
        return {
            "repository": repository,
            "observed_revision": revision,
            "operation": operation,
            "path_or_query": path,
            "retrieved_at": self._now().isoformat(),
            "raw_content": raw_content,
            "raw_content_sha256": sha256(raw_bytes).hexdigest(),
            "source_type": "GITHUB_APP_CONTENTS_API_EXACT_REF",
            "sensitivity": sensitivity,
        }
