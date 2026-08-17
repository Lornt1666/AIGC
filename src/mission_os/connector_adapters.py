from __future__ import annotations

"""Closed connector adapters used by governed AIGC execution paths."""

from collections.abc import Mapping
from hashlib import sha256
from typing import Any, Protocol


class RepositoryReadProvider(Protocol):
    def repository_health(self) -> Mapping[str, Any]: ...

    def read_state(self, query: Mapping[str, Any]) -> Mapping[str, Any]: ...


class GmailDraftProvider(Protocol):
    def health(self) -> Mapping[str, Any]: ...

    def create_draft(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        idempotency_key: str,
    ) -> Mapping[str, Any]: ...

    def get_draft(self, draft_id: str) -> Mapping[str, Any]: ...


class GovernedGmailKernelAdapter:
    """Create and verify one unsent draft without exposing a send primitive."""

    CAPABILITY = "CREATE_DRAFT_VERIFIED"
    connector_id = "gmail"
    capabilities = frozenset({CAPABILITY})

    def __init__(self, provider: GmailDraftProvider) -> None:
        for method in ("health", "create_draft", "get_draft"):
            if not callable(getattr(provider, method, None)):
                raise TypeError(f"Gmail provider must implement {method}")
        self._provider = provider

    def execute(
        self,
        capability: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if capability != self.CAPABILITY:
            raise PermissionError("unsupported Gmail adapter capability")
        if not isinstance(payload, Mapping):
            raise TypeError("Gmail adapter payload must be a mapping")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("Gmail adapter idempotency key is required")
        if payload.get("send") is not False:
            raise PermissionError("Gmail send capability is prohibited")
        if payload.get("production_activation_authorized") not in {None, False}:
            raise PermissionError("Gmail adapter cannot authorize production activation")
        if payload.get("external_send_authorized") not in {None, False}:
            raise PermissionError("Gmail adapter cannot authorize external send")

        expected: dict[str, Any] = {}
        for field in ("to", "subject", "body"):
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Gmail draft {field} is required")
            expected[field] = value
        expected["sent"] = False

        created = self._provider.create_draft(
            to=expected["to"],
            subject=expected["subject"],
            body=expected["body"],
            idempotency_key=idempotency_key,
        )
        if not isinstance(created, Mapping):
            raise TypeError("Gmail provider create_draft must return a mapping")
        draft_id = created.get("draft_id")
        if not isinstance(draft_id, str) or not draft_id:
            raise RuntimeError("Gmail provider did not return a draft identifier")

        observed = self._provider.get_draft(draft_id)
        if not isinstance(observed, Mapping):
            raise TypeError("Gmail provider get_draft must return a mapping")
        if any(observed.get(field) != value for field, value in expected.items()):
            raise RuntimeError("Gmail draft read-back verification failed")
        return {
            "status": "UNSENT_DRAFT_VERIFIED",
            "sent": False,
            "provider_object_id_sha256": sha256(draft_id.encode()).hexdigest(),
            "idempotency_key": idempotency_key,
            "send_capability_present": False,
            "production_activation_authorized": False,
            "external_authority_granted": False,
        }

    def health(self) -> dict[str, Any]:
        provider_health = self._provider.health()
        if not isinstance(provider_health, Mapping):
            raise TypeError("Gmail provider health must be a mapping")
        return {
            **dict(provider_health),
            "capabilities": tuple(sorted(self.capabilities)),
            "send_capability_present": False,
            "production_activation_authorized": False,
            "external_authority_granted": False,
        }


class GovernedGitHubKernelAdapter:
    """Expose one semantic read operation and no generic GitHub primitive.

    Authority is verified by the caller's execution boundary.  This adapter
    still enforces its own closed capability and mutation denial so it cannot
    be repurposed as a write-capable transport.
    """

    CAPABILITY = "READ_REPOSITORY_STATE"
    connector_id = "github"
    capabilities = frozenset({CAPABILITY})

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
