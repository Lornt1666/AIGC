from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re


class GeminiWorkflowConfigurationError(RuntimeError):
    """Raised when the live Gemini workflow is not safely configured."""


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise GeminiWorkflowConfigurationError(
            f"{name} must be an integer"
        ) from exc


@dataclass(frozen=True)
class GeminiWorkflowSettings:
    enabled: bool
    project_id: str
    location: str
    model: str
    evidence_backend: str
    evidence_path: Path | None
    evidence_bucket: str
    evidence_prefix: str
    environment: str
    timeout_seconds: int
    max_output_tokens: int
    max_attempts: int
    source_revision: str
    runtime_revision: str
    control_dsn: str = ""
    control_dsn_secret_ref: str = ""
    surface: str = "operator"
    image_digest: str = ""

    @classmethod
    def from_env(cls) -> "GeminiWorkflowSettings":
        path_value = os.environ.get("AIGC_GEMINI_EVIDENCE_PATH", "").strip()
        settings = cls(
            enabled=_enabled(os.environ.get("AIGC_GEMINI_ENABLED")),
            project_id=os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip(),
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "").strip(),
            model=os.environ.get("AIGC_GEMINI_MODEL", "").strip(),
            evidence_backend=os.environ.get(
                "AIGC_GEMINI_EVIDENCE_BACKEND", "jsonl"
            ).strip().lower(),
            evidence_path=Path(path_value) if path_value else None,
            evidence_bucket=os.environ.get(
                "AIGC_GEMINI_EVIDENCE_BUCKET", ""
            ).strip(),
            evidence_prefix=(
                os.environ.get(
                    "AIGC_GEMINI_EVIDENCE_PREFIX", "product-evidence/gemini"
                ).strip("/")
                or "product-evidence/gemini"
            ),
            environment=os.environ.get("AIGC_ENV", "development").strip().lower(),
            timeout_seconds=_int_env("AIGC_GEMINI_TIMEOUT_SECONDS", 30),
            max_output_tokens=_int_env(
                "AIGC_GEMINI_MAX_OUTPUT_TOKENS", 1200
            ),
            max_attempts=_int_env("AIGC_GEMINI_MAX_ATTEMPTS", 1),
            source_revision=os.environ.get(
                "AIGC_RELEASE_REVISION", ""
            ).strip().lower(),
            runtime_revision=os.environ.get("K_REVISION", "").strip(),
            control_dsn=os.environ.get(
                "AIGC_GEMINI_CONTROL_DSN",
                "",
            ).strip(),
            control_dsn_secret_ref=os.environ.get(
                "AIGC_GEMINI_CONTROL_DSN_SECRET_REF",
                "",
            ).strip(),
            surface=os.environ.get(
                "AIGC_SURFACE",
                "operator",
            ).strip().lower(),
            image_digest=os.environ.get(
                "AIGC_IMAGE_DIGEST",
                "",
            ).strip().lower(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.enabled:
            return
        missing = [
            name
            for name, value in (
                ("GOOGLE_CLOUD_PROJECT", self.project_id),
                ("GOOGLE_CLOUD_LOCATION", self.location),
                ("AIGC_GEMINI_MODEL", self.model),
            )
            if not value
        ]
        if missing:
            raise GeminiWorkflowConfigurationError(
                "Live Gemini workflow configuration is incomplete: "
                + ", ".join(missing)
            )
        if self.evidence_backend not in {"jsonl", "gcs"}:
            raise GeminiWorkflowConfigurationError(
                "AIGC_GEMINI_EVIDENCE_BACKEND must be jsonl or gcs"
            )
        if self.evidence_backend == "jsonl" and self.evidence_path is None:
            raise GeminiWorkflowConfigurationError(
                "AIGC_GEMINI_EVIDENCE_PATH is required for the jsonl backend"
            )
        if self.evidence_backend == "gcs" and not self.evidence_bucket:
            raise GeminiWorkflowConfigurationError(
                "AIGC_GEMINI_EVIDENCE_BUCKET is required for the gcs backend"
            )
        if self.environment == "production" and self.evidence_backend != "gcs":
            raise GeminiWorkflowConfigurationError(
                "Production requires the durable gcs evidence backend"
            )
        if self.environment == "production" and not re.fullmatch(
            r"[a-f0-9]{40}",
            self.source_revision,
        ):
            raise GeminiWorkflowConfigurationError(
                "Production requires AIGC_RELEASE_REVISION as an exact "
                "40-character Git SHA"
            )
        if self.environment == "production" and not self.runtime_revision:
            raise GeminiWorkflowConfigurationError(
                "Production requires the Cloud Run K_REVISION runtime value"
            )
        if self.environment == "production" and not re.fullmatch(
            r"sha256:[a-f0-9]{64}",
            self.image_digest,
        ):
            raise GeminiWorkflowConfigurationError(
                "Production requires AIGC_IMAGE_DIGEST as an immutable "
                "sha256 image digest"
            )
        if (
            self.environment == "production"
            and self.location != "northamerica-northeast1"
        ):
            raise GeminiWorkflowConfigurationError(
                "Production requires the currently supported Canadian regional "
                "Gemini endpoint northamerica-northeast1"
            )
        if self.surface not in {"operator", "judge"}:
            raise GeminiWorkflowConfigurationError(
                "AIGC_SURFACE must be operator or judge"
            )
        if (
            self.environment == "production"
            and self.surface == "operator"
            and not self.control_dsn_secret_ref
        ):
            raise GeminiWorkflowConfigurationError(
                "Production operator surface requires the durable Cloud SQL "
                "runtime-control Secret Manager reference"
            )
        if (
            self.environment == "production"
            and self.surface == "operator"
            and self.control_dsn
        ):
            raise GeminiWorkflowConfigurationError(
                "Production must configure the runtime-control connection by "
                "exact Secret Manager version reference, not a raw environment "
                "value"
            )
        if not 5 <= self.timeout_seconds <= 120:
            raise GeminiWorkflowConfigurationError(
                "AIGC_GEMINI_TIMEOUT_SECONDS must be between 5 and 120"
            )
        if not 256 <= self.max_output_tokens <= 4_096:
            raise GeminiWorkflowConfigurationError(
                "AIGC_GEMINI_MAX_OUTPUT_TOKENS must be between 256 and 4096"
            )
        if not 1 <= self.max_attempts <= 3:
            raise GeminiWorkflowConfigurationError(
                "AIGC_GEMINI_MAX_ATTEMPTS must be between 1 and 3"
            )
        if self.environment == "production" and self.max_attempts != 1:
            raise GeminiWorkflowConfigurationError(
                "Production permits exactly one provider transport attempt so "
                "the emergency-stop epoch covers every dispatch"
            )
