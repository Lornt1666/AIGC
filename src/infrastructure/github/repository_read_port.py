from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.nexus.contextualization import RepositoryReadObservation, RepositoryReadRequest
from src.domain.nexus.contracts import ExecutionPermit
from src.mission_os.connector_adapters import GovernedGitHubKernelAdapter
from src.security.redactor import Redactor


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
    """Fail-closed production placeholder until a separate live credential gate is admitted."""

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
    pass


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


class GitHubRepositoryReadPort:
    """Closed semantic GitHub read port bound to an opaque credential capability.

    This implementation intentionally rejects live credential capabilities and live
    transport. A later canary gate may evolve those two boundaries without adding a
    write-capable or generic GitHub request primitive.
    """

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
        if live_external_reads_enabled:
            raise PermissionError("live GitHub transport is not implemented in this release gate")
        if credential_capability.live_credential:
            raise PermissionError("live GitHub credential capability is not authorized in this release gate")
        if authoritative_now.tzinfo is None or authoritative_now.utcoffset() is None:
            raise ValueError("authoritative_now must be timezone-aware")
        if credential_capability.expires_at <= authoritative_now:
            raise PermissionError("repository credential capability is expired")
        self._adapter = adapter
        self._capability = credential_capability
        self._redactor = redactor or Redactor()
        self.live_external_reads_enabled = False

    def read(self, request: RepositoryReadRequest) -> RepositoryReadObservation:
        if request.operation != "READ_FILE":
            raise NotImplementedError("GitHubRepositoryReadPort supports READ_FILE only in this gate")
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
        except Exception as exc:
            safe_message = self._redactor.redact_text(str(exc))
            raise RepositoryTransportError(f"repository read transport failed: {safe_message}") from None

        if result.get("status") != "READ_ONLY_STATE_OBSERVED":
            raise RepositoryTransportError("repository adapter returned an unexpected status")
        if result.get("write_capability_present") is not False:
            raise RepositoryTransportError("repository adapter exposed write capability")
        state = result.get("state")
        if not isinstance(state, dict):
            raise RepositoryTransportError("repository adapter did not return structured state")

        retrieved_at_value = state.get("retrieved_at")
        if isinstance(retrieved_at_value, datetime):
            retrieved_at = retrieved_at_value
        else:
            raw_time = str(retrieved_at_value or "").replace("Z", "+00:00")
            try:
                retrieved_at = datetime.fromisoformat(raw_time)
            except ValueError as exc:
                raise RepositoryTransportError("repository adapter returned invalid retrieval time") from exc

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
