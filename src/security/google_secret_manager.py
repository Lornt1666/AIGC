from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecretReference:
    name: str
    resource: str
    purpose: str
    risk_level: str


class GoogleSecretManagerClient:
    """Minimal Google Cloud Secret Manager reader with lazy dependency import."""

    def __init__(self):
        try:
            from google.cloud import secretmanager  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-secret-manager is not installed. Install it only when live secret retrieval is approved."
            ) from exc
        self.client = secretmanager.SecretManagerServiceClient()

    def access_secret(self, resource_name: str) -> str:
        response = self.client.access_secret_version(request={"name": resource_name})
        return response.payload.data.decode("UTF-8")
