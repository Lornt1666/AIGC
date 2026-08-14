from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable


REGION = "northamerica-northeast1"
_REGIONAL_SECRET = re.compile(
    r"^projects/(?P<project>[a-z][a-z0-9-]{4,28}[a-z0-9])/"
    r"locations/(?P<location>[a-z0-9-]+)/secrets/"
    r"(?P<secret>[A-Za-z0-9_-]{1,255})/versions/(?P<version>[1-9][0-9]*)$"
)
_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


class RegionalSecretError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegionalSecretMetadata:
    project_id: str
    location: str
    secret_id: str
    version: str


def _crc32c(data: bytes) -> int:
    """Return Castagnoli CRC-32C without adding a runtime dependency."""

    checksum = 0xFFFFFFFF
    for octet in data:
        checksum ^= octet
        for _ in range(8):
            checksum = (checksum >> 1) ^ (0x82F63B78 if checksum & 1 else 0)
    return (~checksum) & 0xFFFFFFFF


class RegionalSecretManagerResolver:
    """Exact-version Montréal Secret Manager data-plane resolver.

    Regional secret values stay inside the infrastructure boundary. Callers receive
    only the requested runtime value and must never place it in Nexus contracts,
    logs, prompts, receipts, or deployment metadata.
    """

    def __init__(
        self,
        *,
        location: str = REGION,
        expected_project_id: str | None = None,
        client_factory: Callable[[str], Any] | None = None,
    ) -> None:
        if location != REGION:
            raise ValueError(f"Nexus V1 regional secrets must use {REGION}")
        if expected_project_id is not None and not _PROJECT.fullmatch(expected_project_id):
            raise ValueError("expected_project_id must be an exact Google Cloud project ID")
        self.location = location
        self.expected_project_id = expected_project_id
        self.endpoint = f"secretmanager.{location}.rep.googleapis.com"
        self._client_factory = client_factory
        self._client: Any | None = None
        self.access_calls = 0

    def parse_reference(self, reference: str) -> RegionalSecretMetadata:
        match = _REGIONAL_SECRET.fullmatch(reference.strip())
        if match is None:
            raise RegionalSecretError(
                "regional secret reference must use an exact numeric version"
            )
        if match.group("location") != self.location:
            raise RegionalSecretError("regional secret reference location mismatch")
        if (
            self.expected_project_id is not None
            and match.group("project") != self.expected_project_id
        ):
            raise RegionalSecretError("regional secret reference project mismatch")
        return RegionalSecretMetadata(
            project_id=match.group("project"),
            location=match.group("location"),
            secret_id=match.group("secret"),
            version=match.group("version"),
        )

    def _client_for_endpoint(self) -> Any:
        if self._client is not None:
            return self._client
        if self._client_factory is not None:
            self._client = self._client_factory(self.endpoint)
            return self._client
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import secretmanager_v1
        except ImportError as exc:
            raise RegionalSecretError(
                "google-cloud-secret-manager is required for regional secret access"
            ) from exc
        self._client = secretmanager_v1.SecretManagerServiceClient(
            client_options=ClientOptions(api_endpoint=self.endpoint)
        )
        return self._client

    def resolve_text(self, reference: str) -> str:
        self.parse_reference(reference)
        exact_reference = reference.strip()
        self.access_calls += 1
        try:
            response = self._client_for_endpoint().access_secret_version(
                request={"name": exact_reference}
            )
            if str(response.name) != exact_reference:
                raise RegionalSecretError("regional secret response name mismatch")
            data = bytes(response.payload.data)
            observed_checksum = response.payload.data_crc32c
            if not isinstance(observed_checksum, int) or observed_checksum != _crc32c(data):
                raise RegionalSecretError("regional secret payload checksum mismatch")
            value = data.decode("utf-8")
        except RegionalSecretError:
            raise
        except Exception as exc:
            raise RegionalSecretError(
                f"regional secret access failed: {type(exc).__name__}"
            ) from None
        if not value:
            raise RegionalSecretError("regional secret value is empty")
        return value
