"""Thin provider adapters for the Ω Mission OS Connector Kernel."""
from __future__ import annotations

from typing import Any, Mapping, Protocol


class GmailDraftProvider(Protocol):
    def health(self) -> Mapping[str, Any]: ...
    def create_draft(self, *, to: str, subject: str, body: str, idempotency_key: str) -> Mapping[str, Any]: ...
    def get_draft(self, draft_id: str) -> Mapping[str, Any]: ...


class GovernedGmailKernelAdapter:
    connector_id = "gmail"
    capabilities = frozenset({"CREATE_DRAFT_VERIFIED"})

    def __init__(self, provider: GmailDraftProvider) -> None:
        self.provider = provider

    def health(self) -> Mapping[str, Any]:
        value = dict(self.provider.health())
        value.update({"connector_id": self.connector_id, "send_capability_present": False})
        return value

    def execute(self, capability: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
        if capability != "CREATE_DRAFT_VERIFIED":
            raise PermissionError("Gmail adapter permits verified draft creation only")
        if payload.get("send") is not False or payload.get("production_activation_authorized") is not False:
            raise PermissionError("Gmail send and production authority are prohibited")
        to = str(payload.get("to") or "")
        subject = str(payload.get("subject") or "")
        body = str(payload.get("body") or "")
        created = self.provider.create_draft(to=to, subject=subject, body=body, idempotency_key=idempotency_key)
        draft_id = str(created.get("draft_id") or "")
        if not draft_id:
            raise RuntimeError("Gmail provider did not return a draft identifier")
        observed = dict(self.provider.get_draft(draft_id))
        expected = {"to": to, "subject": subject, "body": body, "sent": False}
        if any(observed.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Gmail provider read-back verification failed")
        return {
            "status": "DRAFT_CREATED_NOT_SENT",
            "provider_object_id": draft_id,
            "provider_verified": True,
            "sent": False,
            "send_capability_present": False,
            "production_activation_authorized": False,
        }


class GitHubReadOnlyProvider(Protocol):
    def repository_health(self) -> Mapping[str, Any]: ...
    def read_state(self, query: Mapping[str, Any]) -> Mapping[str, Any]: ...


class GovernedGitHubKernelAdapter:
    """Increment 11 migrates GitHub only as a bounded read-only adapter."""

    connector_id = "github"
    capabilities = frozenset({"READ_REPOSITORY_STATE"})

    def __init__(self, provider: GitHubReadOnlyProvider) -> None:
        self.provider = provider

    def health(self) -> Mapping[str, Any]:
        value = dict(self.provider.repository_health())
        value.update({"connector_id": self.connector_id, "write_capability_present": False})
        return value

    def execute(self, capability: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
        if capability != "READ_REPOSITORY_STATE":
            raise PermissionError("GitHub adapter is read-only in Increment 11")
        if payload.get("mutation") not in {None, False}:
            raise PermissionError("GitHub mutation is prohibited")
        result = dict(self.provider.read_state(payload))
        return {
            "status": "READ_ONLY_STATE_OBSERVED",
            "state": result,
            "write_capability_present": False,
            "production_activation_authorized": False,
        }
