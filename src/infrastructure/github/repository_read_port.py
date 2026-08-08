from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.nexus.contextualization import RepositoryReadObservation, RepositoryReadRequest
from src.domain.nexus.contracts import ExecutionPermit
from src.mission_os.connector_adapters import GovernedGitHubKernelAdapter
from src.security.redactor import Redactor


_EXACT_REVISION = re.compile(r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")


@dataclass(frozen=True)
class RepositoryCredentialCapability:
    """Opaque capability reference; contains no token, key, header, or secret material."""

    capability_ref: str
    repository: str
    expires_at: datetime
    live_credential: bool = False

    def __post_init__(self) -> None:
        if not self.capability_ref.strip():
            raise ValueError("repository credential capability_ref is required")
        if not self.repository.strip():
            raise ValueError("repository credential repository is required")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("repository credential capability expiry must be timezone-aware")


class RepositoryCredentialResolver(Protocol):
    live_credential_resolution: bool

    def resolve(
        self,
        *,
        permit: ExecutionPermit,
        repository: str,
        authoritative_now: datetime,
    ) -> RepositoryCredentialCapability: ...


class DeterministicCredentialResolver:
    """Test-only capability resolver. It never resolves real GitHub credential material."""

    live_credential_resolution = False

    def __init__(self) -> None:
        self.resolution_calls = 0
        self.credentials_used = 0

    def resolve(
        self,
        *,
        permit: ExecutionPermit,
        repository: str,
        authoritative_now: datetime,
    ) -> RepositoryCredentialCapability:
        self.resolution_calls += 1
        permit.verify_temporal_validity(authoritative_now=authoritative_now)
        return RepositoryCredentialCapability(
            capability_ref="MOCKCAP-" + canonical_sha256(
                {"permit_id": permit.permit_id, "repository": repository}
            )[:24].upper(),
            repository=repository,
            expires_at=permit.expires_at,
            live_credential=False,
        )


class UnavailableCredentialResolver:
    """Fail-closed production placeholder when live credential resolution is unavailable."""

    live_credential_resolution = False

    def __init__(self) -> None:
        self.resolution_calls = 0
        self.credentials_used = 0

    def resolve(
        self,
        *,
        permit: ExecutionPermit,
        repository: str,
        authoritative_now: datetime,
    ) -> RepositoryCredentialCapability:
        self.resolution_calls += 1
        raise PermissionError("live repository credential resolution is unavailable")


class RepositoryTransportError(RuntimeError):
    """Transport failure with explicit dispatch/outcome semantics."""

    def __init__(
        self,
        message: str,
        *,
        network_attempted: bool = False,
        outcome_known: bool = True,
    ) -> None:
        super().__init__(message)
        self.network_attempted = bool(network_attempted)
        self.outcome_known = bool(outcome_known)


class DeterministicGitHubReadProvider:
    """Mock provider behind the existing governed GitHub adapter; never touches GitHub."""

    def __init__(self, observations: tuple[RepositoryReadObservation, ...]) -> None:
        keyed = {
            (item.repository, item.observed_revision, item.operation, item.path_or_query): item
            for item in observations
        }
        if len(keyed) != len(observations):
            raise ValueError("duplicate deterministic GitHub observations are not permitted")
        self._observations = keyed
        self.calls = 0
        self.network_calls = 0
        self.real_github_calls = 0
        self.credentials_used = 0
        self.repository_writes = 0

    def repository_health(self):
        return {
            "status": "DETERMINISTIC_MOCK_READ_ONLY",
            "network_calls": 0,
            "credentials_used": 0,
        }

    def read_state(self, query):
        self.calls += 1
        key = (
            str(query.get("repository") or ""),
            str(query.get("exact_revision") or ""),
            str(query.get("operation") or ""),
            str(query.get("path_or_query") or ""),
        )
        try:
            observation = self._observations[key]
        except KeyError as exc:
            raise KeyError("deterministic GitHub read observation not found") from exc
        return {
            "repository": observation.repository,
            "observed_revision": observation.observed_revision,
            "operation": observation.operation,
            "path_or_query": observation.path_or_query,
            "retrieved_at": observation.retrieved_at.isoformat(),
            "raw_content": observation.raw_content,
            "raw_content_sha256": observation.raw_content_sha256,
            "source_type": observation.source_type,
            "sensitivity": observation.sensitivity,
        }


class GitHubActionsReadBoundary:
    """One-shot GitHub Actions credential + READ_FILE transport boundary.

    The Actions installation token is held only in this infrastructure object. It is
    never returned by `resolve`, never inserted into a Nexus contract, and is consumed
    when the single network request is attempted.
    """

    live_credential_resolution = True

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        opener: Callable[..., Any] = urlopen,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        maximum_network_requests: int = 1,
    ) -> None:
        values = environ if environ is not None else os.environ
        token = values.get("GITHUB_TOKEN", "").strip()
        repository = values.get("GITHUB_REPOSITORY", "").strip()
        if not token:
            raise PermissionError("GitHub Actions installation token is unavailable")
        if not repository:
            raise PermissionError("GitHub Actions repository binding is unavailable")
        if maximum_network_requests != 1:
            raise ValueError("live GitHub canary requires maximum_network_requests=1")
        self._token = token
        self._repository = repository
        self._opener = opener
        self._clock = clock
        self._maximum_network_requests = 1
        self.resolution_calls = 0
        self.calls = 0
        self.network_calls = 0
        self.real_github_calls = 0
        self.credentials_used = 0
        self.repository_writes = 0
        self.canary_consumed = False

    def repository_health(self):
        return {
            "status": "LIVE_GITHUB_ACTIONS_READ_ONLY_CANARY",
            "network_calls": self.network_calls,
            "credentials_used": self.credentials_used,
            "write_capability_present": False,
        }

    def resolve(
        self,
        *,
        permit: ExecutionPermit,
        repository: str,
        authoritative_now: datetime,
    ) -> RepositoryCredentialCapability:
        self.resolution_calls += 1
        permit.verify_temporal_validity(authoritative_now=authoritative_now)
        if repository != self._repository:
            raise PermissionError("GitHub Actions credential repository mismatch")
        if self.canary_consumed:
            raise PermissionError("GitHub live-read canary credential is already consumed")
        return RepositoryCredentialCapability(
            capability_ref="GHA-CANARY-" + canonical_sha256(
                {"permit_id": permit.permit_id, "repository": repository}
            )[:24].upper(),
            repository=repository,
            expires_at=permit.expires_at,
            live_credential=True,
        )

    def read_state(self, query):
        if self.canary_consumed or self.network_calls >= self._maximum_network_requests:
            raise RepositoryTransportError(
                "GitHub live-read canary has no remaining network authority",
                network_attempted=False,
                outcome_known=True,
            )
        if query.get("mutation") not in {None, False}:
            raise RepositoryTransportError(
                "GitHub live-read canary prohibits mutation",
                network_attempted=False,
                outcome_known=True,
            )
        repository = str(query.get("repository") or "")
        revision = str(query.get("exact_revision") or "")
        operation = str(query.get("operation") or "")
        path = str(query.get("path_or_query") or "")
        sensitivity = str(query.get("sensitivity") or "INTERNAL")
        if repository != self._repository:
            raise RepositoryTransportError(
                "GitHub live-read canary repository mismatch",
                network_attempted=False,
                outcome_known=True,
            )
        if operation != "READ_FILE":
            raise RepositoryTransportError(
                "GitHub live-read canary supports READ_FILE only",
                network_attempted=False,
                outcome_known=True,
            )
        if not _EXACT_REVISION.fullmatch(revision):
            raise RepositoryTransportError(
                "GitHub live-read canary requires an exact hexadecimal revision",
                network_attempted=False,
                outcome_known=True,
            )
        if not path or path.startswith("/") or ".." in path.split("/"):
            raise RepositoryTransportError(
                "GitHub live-read canary path is invalid",
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
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "AIGC-Nexus-Governed-Read-Canary",
            },
        )

        # Authority is consumed immediately before the first dispatch attempt.
        self.calls += 1
        self.network_calls += 1
        self.real_github_calls += 1
        self.credentials_used += 1
        self.canary_consumed = True
        try:
            with self._opener(request, timeout=30) as response:
                raw_response = response.read()
        except HTTPError as exc:
            self._token = ""
            raise RepositoryTransportError(
                f"GitHub returned HTTP {exc.code}",
                network_attempted=True,
                outcome_known=True,
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            self._token = ""
            raise RepositoryTransportError(
                f"GitHub transport outcome is unknown: {type(exc).__name__}",
                network_attempted=True,
                outcome_known=False,
            ) from None
        finally:
            # Never retain the credential after the single network attempt.
            self._token = ""

        try:
            payload = json.loads(raw_response)
            if not isinstance(payload, dict):
                raise ValueError("response is not an object")
            if payload.get("type") != "file" or payload.get("encoding") != "base64":
                raise ValueError("response is not a base64 file")
            encoded = str(payload.get("content") or "").replace("\n", "")
            raw_bytes = b64decode(encoded, validate=True)
            raw_content = raw_bytes.decode("utf-8")
        except Exception as exc:
            raise RepositoryTransportError(
                f"GitHub returned invalid READ_FILE content: {type(exc).__name__}",
                network_attempted=True,
                outcome_known=True,
            ) from None

        observed_at = self._clock()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise RepositoryTransportError(
                "GitHub canary clock must be timezone-aware",
                network_attempted=True,
                outcome_known=True,
            )
        return {
            "repository": repository,
            "observed_revision": revision,
            "operation": operation,
            "path_or_query": path,
            "retrieved_at": observed_at.astimezone(timezone.utc).isoformat(),
            "raw_content": raw_content,
            "raw_content_sha256": sha256(raw_bytes).hexdigest(),
            "source_type": "GITHUB_CONTENTS_API_EXACT_REF",
            "sensitivity": sensitivity,
        }


class GitHubRepositoryReadPort:
    """Closed semantic GitHub READ_FILE port bound to an opaque credential capability."""

    port_id = "github_governed_read_port"
    external_read = True
    credentials_required = True
    write_capability_present = False

    def __init__(
        self,
        *,
        adapter: GovernedGitHubKernelAdapter,
        credential_capability: RepositoryCredentialCapability,
        authoritative_now: datetime,
        live_external_reads_enabled: bool = False,
        redactor: Redactor | None = None,
    ) -> None:
        if credential_capability.live_credential and not live_external_reads_enabled:
            raise PermissionError("live GitHub credential capability requires canary activation")
        if live_external_reads_enabled and not credential_capability.live_credential:
            raise PermissionError("live GitHub canary requires a live credential capability")
        if authoritative_now.tzinfo is None or authoritative_now.utcoffset() is None:
            raise ValueError("authoritative_now must be timezone-aware")
        if credential_capability.expires_at <= authoritative_now:
            raise PermissionError("repository credential capability is expired")
        self._adapter = adapter
        self._capability = credential_capability
        self._redactor = redactor or Redactor()
        self.live_external_reads_enabled = bool(live_external_reads_enabled)

    def read(self, request: RepositoryReadRequest) -> RepositoryReadObservation:
        if request.operation != "READ_FILE":
            raise NotImplementedError("GitHubRepositoryReadPort supports READ_FILE only")
        if request.repository != self._capability.repository:
            raise PermissionError("repository credential capability repository mismatch")

        payload = {
            "repository": request.repository,
            "exact_revision": request.exact_revision,
            "operation": request.operation,
            "path_or_query": request.path_or_query,
            "sensitivity": request.sensitivity,
            "mutation": False,
            "production_activation_authorized": False,
        }
        idempotency_key = canonical_sha256(
            {
                "repository": request.repository,
                "exact_revision": request.exact_revision,
                "operation": request.operation,
                "path_or_query": request.path_or_query,
                "sensitivity": request.sensitivity,
            }
        )
        try:
            result = self._adapter.execute(
                "READ_REPOSITORY_STATE",
                payload,
                idempotency_key,
            )
        except RepositoryTransportError as exc:
            safe_message = self._redactor.redact_text(str(exc))
            raise RepositoryTransportError(
                f"repository read transport failed: {safe_message}",
                network_attempted=exc.network_attempted,
                outcome_known=exc.outcome_known,
            ) from None
        except Exception as exc:
            safe_message = self._redactor.redact_text(str(exc))
            raise RepositoryTransportError(
                f"repository read transport failed: {safe_message}",
                network_attempted=False,
                outcome_known=True,
            ) from None

        if result.get("status") != "READ_ONLY_STATE_OBSERVED":
            raise RepositoryTransportError(
                "repository adapter returned an unexpected status",
                network_attempted=self.live_external_reads_enabled,
                outcome_known=True,
            )
        if result.get("write_capability_present") is not False:
            raise RepositoryTransportError(
                "repository adapter exposed write capability",
                network_attempted=self.live_external_reads_enabled,
                outcome_known=True,
            )
        state = result.get("state")
        if not isinstance(state, dict):
            raise RepositoryTransportError(
                "repository adapter did not return structured state",
                network_attempted=self.live_external_reads_enabled,
                outcome_known=True,
            )

        retrieved_at_value = state.get("retrieved_at")
        if isinstance(retrieved_at_value, datetime):
            retrieved_at = retrieved_at_value
        else:
            raw_time = str(retrieved_at_value or "").replace("Z", "+00:00")
            try:
                retrieved_at = datetime.fromisoformat(raw_time)
            except ValueError as exc:
                raise RepositoryTransportError(
                    "repository adapter returned invalid retrieval time",
                    network_attempted=self.live_external_reads_enabled,
                    outcome_known=True,
                ) from None

        return RepositoryReadObservation(
            repository=str(state.get("repository") or ""),
            observed_revision=str(state.get("observed_revision") or ""),
            operation=str(state.get("operation") or ""),
            path_or_query=str(state.get("path_or_query") or ""),
            retrieved_at=retrieved_at,
            raw_content=str(state.get("raw_content") or ""),
            raw_content_sha256=str(state.get("raw_content_sha256") or ""),
            source_type=str(state.get("source_type") or ""),
            sensitivity=str(state.get("sensitivity") or ""),
        )
