from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Mapping


class SecretBrokerError(RuntimeError):
    """Raised when governed exact-version secret access fails closed."""


_EXACT_SECRET_REF = re.compile(
    r"^projects/(?P<project>[a-z][a-z0-9-]{4,28}[a-z0-9])/"
    r"secrets/(?P<secret>[A-Za-z0-9_-]{1,255})/"
    r"versions/(?P<version>[1-9][0-9]*)$"
)
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_REQUIRED_CHAIN = (
    "Omega-X Orchestrator",
    "Ultra-Secrets Agent",
    "Secret Broker",
    "Google Cloud Secret Manager",
)
DEFAULT_SECRET_MANIFEST_PATH = Path(
    "config/gemini_secret_access_manifest.json"
)


@dataclass(frozen=True)
class SecretAccessReceipt:
    reference_sha256: str
    purpose: str
    exact_version: str
    manifest_sha256: str
    deployment_authorization_sha256: str
    chain: tuple[str, ...] = _REQUIRED_CHAIN
    audit_sink: str = "cloud_logging_metadata_only"
    value_logged: bool = False


@dataclass(frozen=True)
class SecretAccessManifest:
    bindings: Mapping[str, str]
    manifest_sha256: str
    chain: tuple[str, ...]
    audit_sink: str

    @classmethod
    def load(cls, path: Path) -> "SecretAccessManifest":
        try:
            raw_bytes = path.read_bytes()
            payload = json.loads(raw_bytes)
        except Exception as exc:
            raise SecretBrokerError(
                "Secret access manifest could not be loaded"
            ) from exc
        if payload.get("schema_version") != (
            "aigc.gemini-secret-access-manifest.v1"
        ):
            raise SecretBrokerError("Secret access manifest schema is invalid")
        chain = tuple(payload.get("required_chain") or ())
        if chain != _REQUIRED_CHAIN:
            raise SecretBrokerError(
                "Secret access manifest does not require the approved chain"
            )
        if payload.get("audit_sink") != "cloud_logging_metadata_only":
            raise SecretBrokerError(
                "Secret access manifest requires a durable metadata-only audit"
            )
        raw_bindings = payload.get("bindings")
        if not isinstance(raw_bindings, list) or not raw_bindings:
            raise SecretBrokerError("Secret access manifest has no bindings")
        bindings: dict[str, str] = {}
        for item in raw_bindings:
            if not isinstance(item, dict):
                raise SecretBrokerError(
                    "Secret access manifest binding is invalid"
                )
            purpose = str(item.get("purpose", "")).strip()
            env_name = str(item.get("reference_env", "")).strip()
            if (
                not re.fullmatch(r"[a-z][a-z0-9-]{2,119}", purpose)
                or not re.fullmatch(r"AIGC_[A-Z0-9_]{3,100}", env_name)
                or purpose in bindings
            ):
                raise SecretBrokerError(
                    "Secret access manifest binding is invalid"
                )
            bindings[purpose] = env_name
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return cls(
            bindings=bindings,
            manifest_sha256=hashlib.sha256(canonical).hexdigest(),
            chain=chain,
            audit_sink=payload["audit_sink"],
        )


class SecretBroker:
    """Low-level GSM broker callable only by the Ultra-Secrets Agent."""

    def __init__(
        self,
        *,
        project_id: str,
        client: Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.project_id = project_id.strip()
        self._client = client
        self._logger = logger or logging.getLogger(
            "aigc.gemini.secret_broker"
        )

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import secretmanager
            except ImportError as exc:
                raise SecretBrokerError(
                    "google-cloud-secret-manager is required by SecretBroker"
                ) from exc
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def resolve_text(
        self,
        reference: str,
        *,
        purpose: str,
        delegated_by: str,
        manifest_sha256: str,
        deployment_authorization_sha256: str,
    ) -> tuple[str, SecretAccessReceipt]:
        if delegated_by != "Ultra-Secrets Agent":
            raise SecretBrokerError(
                "SecretBroker accepts only Ultra-Secrets Agent delegation"
            )
        if not _SHA256.fullmatch(manifest_sha256):
            raise SecretBrokerError("Secret manifest binding is invalid")
        if not _SHA256.fullmatch(deployment_authorization_sha256):
            raise SecretBrokerError(
                "Deployment authorization binding is invalid"
            )
        match = _EXACT_SECRET_REF.fullmatch(reference.strip())
        if match is None:
            raise SecretBrokerError(
                "Secret references must use an exact numeric Secret Manager "
                "version; aliases such as latest are forbidden"
            )
        if match.group("project") != self.project_id:
            raise SecretBrokerError(
                "Secret reference project does not match the configured project"
            )
        normalized_purpose = purpose.strip()
        if len(normalized_purpose) < 3 or len(normalized_purpose) > 120:
            raise SecretBrokerError(
                "Secret access purpose must contain 3-120 characters"
            )
        try:
            response = self._get_client().access_secret_version(
                request={"name": reference}
            )
            value = bytes(response.payload.data).decode("utf-8")
        except Exception as exc:
            raise SecretBrokerError(
                f"SecretBroker access failed: {type(exc).__name__}"
            ) from exc
        if not value:
            raise SecretBrokerError("SecretBroker returned an empty secret")
        receipt = SecretAccessReceipt(
            reference_sha256=hashlib.sha256(
                reference.encode("utf-8")
            ).hexdigest(),
            purpose=normalized_purpose,
            exact_version=match.group("version"),
            manifest_sha256=manifest_sha256,
            deployment_authorization_sha256=(
                deployment_authorization_sha256
            ),
        )
        self._logger.info(
            "secret_access_audit chain=omega_x>ultra_secrets>broker>gsm "
            "reference_sha256=%s purpose=%s exact_version=%s "
            "manifest_sha256=%s authorization_sha256=%s "
            "audit_sink=cloud_logging_metadata_only value_logged=false",
            receipt.reference_sha256,
            receipt.purpose,
            receipt.exact_version,
            receipt.manifest_sha256,
            receipt.deployment_authorization_sha256,
        )
        return value, receipt


class UltraSecretsAgent:
    """Manifest-enforcing delegation layer; never returns audit-free access."""

    def __init__(
        self,
        *,
        manifest: SecretAccessManifest,
        broker: SecretBroker,
        environ: Mapping[str, str],
        deployment_authorization_sha256: str,
    ) -> None:
        self._manifest = manifest
        self._broker = broker
        self._environ = environ
        self._authorization_sha256 = deployment_authorization_sha256

    def resolve_for_omega_x(
        self,
        *,
        requested_by: str,
        phase: str,
        purpose: str,
    ) -> tuple[str, SecretAccessReceipt]:
        if requested_by != "Omega-X Orchestrator":
            raise SecretBrokerError(
                "Ultra-Secrets accepts only Omega-X requests"
            )
        if phase != "runtime_secret_access":
            raise SecretBrokerError("Secret access phase is not authorized")
        try:
            env_name = self._manifest.bindings[purpose]
        except KeyError as exc:
            raise SecretBrokerError(
                "Secret purpose is not present in the approved manifest"
            ) from exc
        reference = self._environ.get(env_name, "").strip()
        if not reference:
            raise SecretBrokerError(
                "Approved secret reference environment binding is missing"
            )
        return self._broker.resolve_text(
            reference,
            purpose=purpose,
            delegated_by="Ultra-Secrets Agent",
            manifest_sha256=self._manifest.manifest_sha256,
            deployment_authorization_sha256=self._authorization_sha256,
        )


class OmegaXSecretAccess:
    """Approved runtime entrypoint for the complete secret-access chain."""

    def __init__(self, *, ultra_secrets: UltraSecretsAgent) -> None:
        self._ultra_secrets = ultra_secrets

    @classmethod
    def from_environment(
        cls,
        *,
        project_id: str,
        environ: Mapping[str, str] | None = None,
        manifest_path: Path | None = None,
        client: Any | None = None,
    ) -> "OmegaXSecretAccess":
        values = environ if environ is not None else os.environ
        configured_path = values.get(
            "AIGC_SECRET_ACCESS_MANIFEST_PATH",
            "",
        ).strip()
        selected_path = (
            manifest_path
            or (Path(configured_path) if configured_path else None)
            or DEFAULT_SECRET_MANIFEST_PATH
        )
        manifest = SecretAccessManifest.load(selected_path)
        authorization_sha256 = values.get(
            "AIGC_DEPLOYMENT_AUTHORIZATION_SHA256",
            "",
        ).strip().lower()
        if not _SHA256.fullmatch(authorization_sha256):
            raise SecretBrokerError(
                "Secret access requires a deployment authorization digest"
            )
        return cls(
            ultra_secrets=UltraSecretsAgent(
                manifest=manifest,
                broker=SecretBroker(
                    project_id=project_id,
                    client=client,
                ),
                environ=values,
                deployment_authorization_sha256=authorization_sha256,
            )
        )

    def resolve(
        self,
        purpose: str,
    ) -> tuple[str, SecretAccessReceipt]:
        return self._ultra_secrets.resolve_for_omega_x(
            requested_by="Omega-X Orchestrator",
            phase="runtime_secret_access",
            purpose=purpose,
        )
