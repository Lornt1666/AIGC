from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Protocol

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.nexus.contextualization import (
    RepositoryContext,
    RepositoryContextRecord,
    RepositoryOperation,
    RepositoryReadObservation,
    RepositoryReadRequest,
)
from src.security.redactor import Redactor


_EXACT_REVISION = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


@dataclass(frozen=True)
class RepositoryGatewayPolicy:
    allowed_repositories: tuple[str, ...]
    allowed_operations: tuple[RepositoryOperation, ...]
    allowed_path_prefixes: tuple[str, ...] = ("",)
    maximum_response_bytes: int = 262144
    allowed_sensitivities: tuple[str, ...] = ("PUBLIC", "INTERNAL")
    external_reads_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.allowed_repositories:
            raise ValueError("repository gateway requires an explicit repository allowlist")
        if not self.allowed_operations:
            raise ValueError("repository gateway requires an explicit operation allowlist")
        if self.maximum_response_bytes < 1:
            raise ValueError("maximum_response_bytes must be positive")
        if not self.allowed_path_prefixes:
            raise ValueError("repository gateway requires an explicit path-prefix allowlist")


def repository_gateway_policy_hash(policy: RepositoryGatewayPolicy) -> str:
    return canonical_sha256(
        {
            "allowed_repositories": policy.allowed_repositories,
            "allowed_operations": policy.allowed_operations,
            "allowed_path_prefixes": policy.allowed_path_prefixes,
            "maximum_response_bytes": policy.maximum_response_bytes,
            "allowed_sensitivities": policy.allowed_sensitivities,
            "external_reads_enabled": policy.external_reads_enabled,
        }
    )


class RepositoryReadPort(Protocol):
    port_id: str
    external_read: bool
    credentials_required: bool
    write_capability_present: bool

    def read(self, request: RepositoryReadRequest) -> RepositoryReadObservation: ...


class DeterministicRepositoryReadPort:
    """Fixture-only repository port. It performs no GitHub/network/credential operation."""

    port_id = "deterministic_repository_read_port"
    external_read = False
    credentials_required = False
    write_capability_present = False

    def __init__(self, observations: tuple[RepositoryReadObservation, ...]) -> None:
        keyed = {
            (item.repository, item.observed_revision, item.operation, item.path_or_query): item
            for item in observations
        }
        if len(keyed) != len(observations):
            raise ValueError("duplicate deterministic repository observations are not permitted")
        self._observations = keyed
        self.network_calls = 0
        self.credentials_used = 0
        self.repository_live_reads = 0
        self.repository_writes = 0

    def read(self, request: RepositoryReadRequest) -> RepositoryReadObservation:
        key = (request.repository, request.exact_revision, request.operation, request.path_or_query)
        try:
            return self._observations[key]
        except KeyError as exc:
            raise KeyError("deterministic repository observation not found") from exc


class NexusRepositoryGateway:
    """Provider-neutral read-only repository context builder.

    This object never grants authority and never exposes repository mutation. External
    ports are accepted only by an explicitly constructed policy with external reads
    enabled; the execution/permit boundary remains outside the gateway.
    """

    def __init__(
        self,
        *,
        port: RepositoryReadPort,
        policy: RepositoryGatewayPolicy,
        redactor: Redactor | None = None,
    ) -> None:
        if port.write_capability_present:
            raise PermissionError("repository gateway rejects write-capable ports")
        if port.external_read and not policy.external_reads_enabled:
            raise PermissionError("external repository reads are disabled")
        if port.credentials_required and not policy.external_reads_enabled:
            raise PermissionError("credential-requiring repository reads are disabled")
        self._port = port
        self._policy = policy
        self._redactor = redactor or Redactor()
        self._policy_hash = repository_gateway_policy_hash(policy)

    @property
    def write_capability_present(self) -> bool:
        return False

    @property
    def policy_hash(self) -> str:
        return self._policy_hash

    @property
    def maximum_response_bytes(self) -> int:
        return self._policy.maximum_response_bytes

    @property
    def external_reads_enabled(self) -> bool:
        return self._policy.external_reads_enabled

    def read_context(self, requests: tuple[RepositoryReadRequest, ...]) -> RepositoryContext:
        if not requests:
            raise ValueError("repository context requires at least one read request")
        repository = requests[0].repository
        exact_revision = requests[0].exact_revision
        records: list[RepositoryContextRecord] = []
        for request in requests:
            self._validate_request(request, repository=repository, exact_revision=exact_revision)
            observation = self._port.read(request)
            records.append(self._record_from_observation(request, observation))

        identity = {
            "repository": repository,
            "exact_revision": exact_revision,
            "records": [record.model_dump(mode="json") for record in records],
            "policy_hash": self._policy_hash,
        }
        digest = canonical_sha256(identity)
        return RepositoryContext(
            context_id="RCTX-" + digest[:24].upper(),
            repository=repository,
            exact_revision=exact_revision,
            records=tuple(records),
            policy_hash=self._policy_hash,
            canonical_hash=digest,
        )

    def _validate_request(
        self,
        request: RepositoryReadRequest,
        *,
        repository: str,
        exact_revision: str,
    ) -> None:
        if not _EXACT_REVISION.fullmatch(request.exact_revision):
            raise ValueError("repository request requires an exact hexadecimal revision")
        if request.repository not in self._policy.allowed_repositories:
            raise PermissionError("repository is not allowlisted")
        if request.operation not in self._policy.allowed_operations:
            raise PermissionError("repository operation is not allowlisted")
        if request.sensitivity not in self._policy.allowed_sensitivities:
            raise PermissionError("repository sensitivity is not allowlisted")
        if request.repository != repository or request.exact_revision != exact_revision:
            raise ValueError("RepositoryContext cannot mix repositories or exact revisions")
        if not any(request.path_or_query.startswith(prefix) for prefix in self._policy.allowed_path_prefixes):
            raise PermissionError("repository path/query is not allowlisted")

    def _record_from_observation(
        self,
        request: RepositoryReadRequest,
        observation: RepositoryReadObservation,
    ) -> RepositoryContextRecord:
        if observation.repository != request.repository:
            raise ValueError("repository observation repository mismatch")
        if observation.observed_revision != request.exact_revision:
            raise ValueError("repository observation exact revision mismatch")
        if observation.operation != request.operation or observation.path_or_query != request.path_or_query:
            raise ValueError("repository observation request binding mismatch")
        if observation.sensitivity != request.sensitivity:
            raise ValueError("repository observation sensitivity mismatch")
        raw_bytes = observation.raw_content.encode("utf-8")
        if len(raw_bytes) > self._policy.maximum_response_bytes:
            raise ValueError("repository response-size ceiling exceeded")
        raw_digest = sha256(raw_bytes).hexdigest()
        if raw_digest != observation.raw_content_sha256:
            raise ValueError("repository raw content hash mismatch")
        projected = self._redactor.redact_text(observation.raw_content)
        return RepositoryContextRecord(
            repository=request.repository,
            exact_revision=request.exact_revision,
            operation=request.operation,
            path_or_query=request.path_or_query,
            retrieved_at=observation.retrieved_at,
            content=projected,
            raw_content_sha256=raw_digest,
            projected_content_sha256=sha256(projected.encode("utf-8")).hexdigest(),
            source_type=observation.source_type,
            sensitivity=observation.sensitivity,
            redaction_applied=projected != observation.raw_content,
        )
