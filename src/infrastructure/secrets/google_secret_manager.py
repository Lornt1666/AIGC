from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Protocol


_REFERENCE = re.compile(
    r"^gcp_secret://(?P<project>[a-z](?:[a-z0-9-]{4,28}[a-z0-9])|TBD_PROJECT)/"
    r"(?P<secret>[A-Za-z0-9._-]{1,255})/(?P<version>[A-Za-z0-9._-]{1,63})$"
)


class SecretManagerPolicyError(ValueError):
    """Raised when a secret reference or access decision is unsafe."""


class SecretManagerClientProtocol(Protocol):
    def access_secret_version(self, *, request: dict[str, str]) -> Any: ...


@dataclass(frozen=True)
class SecretReference:
    project_id: str
    secret_id: str
    version: str

    @property
    def canonical(self) -> str:
        return f"gcp_secret://{self.project_id}/{self.secret_id}/{self.version}"

    @property
    def resource_name(self) -> str:
        return (
            f"projects/{self.project_id}/secrets/{self.secret_id}/versions/{self.version}"
        )


@dataclass(frozen=True)
class SecretAccessReceipt:
    reference: str
    resource_name: str
    version_name: str
    accessed_at: datetime
    raw_value_logged: bool = False
    raw_value_persisted: bool = False
    external_action_performed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_id": "AIGC-SECRET-ACCESS-RECEIPT-001",
            "contract_version": "1.0.0",
            "reference": self.reference,
            "resource_name": self.resource_name,
            "version_name": self.version_name,
            "accessed_at": self.accessed_at.isoformat(),
            "raw_value_logged": self.raw_value_logged,
            "raw_value_persisted": self.raw_value_persisted,
            "external_action_performed": self.external_action_performed,
        }


class ResolvedSecret:
    """In-memory secret material that can be explicitly zeroized."""

    def __init__(self, material: bytes, receipt: SecretAccessReceipt) -> None:
        if not material:
            raise SecretManagerPolicyError("Resolved secret material is empty")
        self._material = bytearray(material)
        self.receipt = receipt
        self._closed = False

    def bytes(self) -> bytes:
        if self._closed:
            raise SecretManagerPolicyError("Resolved secret material is closed")
        return bytes(self._material)

    def close(self) -> None:
        if self._closed:
            return
        for index in range(len(self._material)):
            self._material[index] = 0
        self._closed = True

    def __enter__(self) -> "ResolvedSecret":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()


def parse_secret_reference(value: str) -> SecretReference:
    match = _REFERENCE.fullmatch(str(value))
    if not match:
        raise SecretManagerPolicyError("Secret Manager reference is malformed")
    return SecretReference(
        project_id=match.group("project"),
        secret_id=match.group("secret"),
        version=match.group("version"),
    )


class GoogleSecretManagerResolver:
    def __init__(
        self,
        *,
        expected_project_id: str | None,
        access_authorized: bool,
        client: SecretManagerClientProtocol | None = None,
    ) -> None:
        self.expected_project_id = expected_project_id
        self.access_authorized = access_authorized
        self._client = client

    def access(self, reference_value: str) -> ResolvedSecret:
        reference = parse_secret_reference(reference_value)
        if not self.access_authorized:
            raise SecretManagerPolicyError("Secret Manager access is not authorized")
        if self.expected_project_id is None or reference.project_id == "TBD_PROJECT":
            raise SecretManagerPolicyError("Secret Manager project remains unresolved")
        if reference.project_id != self.expected_project_id:
            raise SecretManagerPolicyError("Secret Manager project is not allowlisted")
        client = self._client or self._default_client()
        try:
            response = client.access_secret_version(
                request={"name": reference.resource_name}
            )
            material = bytes(response.payload.data)
            version_name = str(getattr(response, "name", reference.resource_name))
        except Exception as exc:
            raise SecretManagerPolicyError("Secret Manager access failed") from exc
        receipt = SecretAccessReceipt(
            reference=reference.canonical,
            resource_name=reference.resource_name,
            version_name=version_name,
            accessed_at=datetime.now(timezone.utc),
        )
        return ResolvedSecret(material, receipt)

    @staticmethod
    def _default_client() -> SecretManagerClientProtocol:
        try:
            from google.cloud import secretmanager
        except ImportError as exc:
            raise SecretManagerPolicyError(
                "Google Secret Manager client dependency is unavailable"
            ) from exc
        return secretmanager.SecretManagerServiceClient()
