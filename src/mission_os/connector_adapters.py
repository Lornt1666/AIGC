from __future__ import annotations

"""Closed connector adapters used by governed AIGC execution paths."""

from collections.abc import Mapping
from typing import Any, Protocol


class RepositoryReadProvider(Protocol):
    def repository_health(self) -> Mapping[str, Any]: ...

    def read_state(self, query: Mapping[str, Any]) -> Mapping[str, Any]: ...


class GovernedGitHubKernelAdapter:
    """Expose one semantic read operation and no generic GitHub primitive.

    Authority is verified by the caller's execution boundary.  This adapter
    still enforces its own closed capability and mutation denial so it cannot
    be repurposed as a write-capable transport.
    """

    CAPABILITY = "READ_REPOSITORY_STATE"

    def __init__(self, provider: RepositoryReadProvider) -> None:
        if not callable(getattr(provider, "read_state", None)):
            raise TypeError("GitHub provider must implement read_state")
        if not callable(getattr(provider, "repository_health", None)):
            raise TypeError("GitHub provider must implement repository_health")
        self._provider = provider

    def execute(
        self,
        capability: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if capability != self.CAPABILITY:
            raise PermissionError("unsupported GitHub adapter capability")
        if not isinstance(payload, Mapping):
            raise TypeError("GitHub adapter payload must be a mapping")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("GitHub adapter idempotency key is required")
        if payload.get("mutation") is not False:
            raise PermissionError("repository mutation is prohibited")
        if payload.get("production_activation_authorized") not in {None, False}:
            raise PermissionError("repository adapter cannot authorize production activation")

        state = self._provider.read_state(dict(payload))
        if not isinstance(state, Mapping):
            raise TypeError("GitHub provider read_state must return a mapping")
        return {
            "status": "READ_ONLY_STATE_OBSERVED",
            "state": dict(state),
            "idempotency_key": idempotency_key,
            "write_capability_present": False,
            "production_activation_authorized": False,
            "external_authority_granted": False,
        }

    def health(self) -> dict[str, Any]:
        provider_health = self._provider.repository_health()
        if not isinstance(provider_health, Mapping):
            raise TypeError("GitHub provider health must be a mapping")
        return {
            "status": str(provider_health.get("status") or "UNKNOWN"),
            "provider": dict(provider_health),
            "capabilities": (self.CAPABILITY,),
            "write_capability_present": False,
            "production_activation_authorized": False,
            "external_authority_granted": False,
        }

