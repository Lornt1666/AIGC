from __future__ import annotations

from dataclasses import dataclass
import os
import re


class RuntimeLimitConfigurationError(ValueError):
    """Raised when runtime limits would not provide a bounded execution policy."""


_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$")
_PRINCIPAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{7,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeLimitConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise RuntimeLimitConfigurationError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class RuntimeLimits:
    """Application-side request and token reservations.

    These limits are deterministic safety guardrails. They are not a substitute
    for Google Cloud quotas, billing budgets, alerts, or an approved spend cap.
    """

    principal_runs_per_minute: int = 3
    principal_runs_per_day: int = 50
    principal_reserved_tokens_per_day: int = 100_000
    global_runs_per_minute: int = 6
    global_runs_per_day: int = 100
    global_reserved_tokens_per_day: int = 200_000
    max_tokens_per_run: int = 16_384

    def __post_init__(self) -> None:
        values = {
            "principal_runs_per_minute": self.principal_runs_per_minute,
            "principal_runs_per_day": self.principal_runs_per_day,
            "principal_reserved_tokens_per_day": (
                self.principal_reserved_tokens_per_day
            ),
            "global_runs_per_minute": self.global_runs_per_minute,
            "global_runs_per_day": self.global_runs_per_day,
            "global_reserved_tokens_per_day": self.global_reserved_tokens_per_day,
            "max_tokens_per_run": self.max_tokens_per_run,
        }
        invalid = sorted(name for name, value in values.items() if value <= 0)
        if invalid:
            raise RuntimeLimitConfigurationError(
                "Runtime limits must be greater than zero: " + ", ".join(invalid)
            )
        if self.global_runs_per_minute < self.principal_runs_per_minute:
            raise RuntimeLimitConfigurationError(
                "global_runs_per_minute cannot be lower than the principal limit"
            )
        if self.global_runs_per_day < self.principal_runs_per_day:
            raise RuntimeLimitConfigurationError(
                "global_runs_per_day cannot be lower than the principal limit"
            )
        if (
            self.global_reserved_tokens_per_day
            < self.principal_reserved_tokens_per_day
        ):
            raise RuntimeLimitConfigurationError(
                "The global token reservation cannot be lower than the "
                "principal token reservation"
            )
        if self.max_tokens_per_run > self.principal_reserved_tokens_per_day:
            raise RuntimeLimitConfigurationError(
                "max_tokens_per_run cannot exceed the principal daily reservation"
            )

    @classmethod
    def from_env(cls) -> "RuntimeLimits":
        return cls(
            principal_runs_per_minute=_positive_int(
                "AIGC_GEMINI_PRINCIPAL_RUNS_PER_MINUTE", 3
            ),
            principal_runs_per_day=_positive_int(
                "AIGC_GEMINI_PRINCIPAL_RUNS_PER_DAY", 50
            ),
            principal_reserved_tokens_per_day=_positive_int(
                "AIGC_GEMINI_PRINCIPAL_RESERVED_TOKENS_PER_DAY", 100_000
            ),
            global_runs_per_minute=_positive_int(
                "AIGC_GEMINI_GLOBAL_RUNS_PER_MINUTE", 6
            ),
            global_runs_per_day=_positive_int(
                "AIGC_GEMINI_GLOBAL_RUNS_PER_DAY", 100
            ),
            global_reserved_tokens_per_day=_positive_int(
                "AIGC_GEMINI_GLOBAL_RESERVED_TOKENS_PER_DAY", 200_000
            ),
            max_tokens_per_run=_positive_int(
                "AIGC_GEMINI_MAX_TOKENS_PER_RUN", 16_384
            ),
        )

    def validate_reservation(self, reserved_tokens: int) -> None:
        if reserved_tokens <= 0:
            raise RuntimeLimitConfigurationError(
                "reserved_tokens must be greater than zero"
            )
        if reserved_tokens > self.max_tokens_per_run:
            raise RuntimeLimitConfigurationError(
                "reserved_tokens exceeds max_tokens_per_run"
            )


def validate_principal_id(value: str) -> str:
    normalized = value.strip()
    if not _PRINCIPAL_ID.fullmatch(normalized):
        raise ValueError(
            "principal_id must be 8..128 characters from the approved identifier set"
        )
    return normalized


def validate_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not _IDEMPOTENCY_KEY.fullmatch(normalized):
        raise ValueError(
            "idempotency_key must be 16..128 characters and use only "
            "letters, digits, dot, underscore, colon, or hyphen"
        )
    return normalized


def validate_sha256(value: str, *, field_name: str = "request_sha256") -> str:
    normalized = value.strip().lower()
    if not _SHA256.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return normalized
