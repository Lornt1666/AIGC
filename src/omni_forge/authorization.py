from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hmac
import re

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class AuthorityDecision(str, Enum):
    DENY = "DENY"
    ALLOW_REPOSITORY_ONLY = "ALLOW_REPOSITORY_ONLY"
    ALLOW_STAGING_EXTERNAL_EFFECT = "ALLOW_STAGING_EXTERNAL_EFFECT"


@dataclass(frozen=True)
class AuthorizationPacket:
    packet_id: str
    actor_id: str
    environment: str
    action: str
    target: str
    repository_sha: str
    repository_tree_sha: str
    schema_digest: str
    policy_digest: str
    idempotency_key_digest: str
    expires_at: str
    decision: AuthorityDecision
    production_activation: bool = False
    public_access: bool = False
    live_model_call: bool = False
    financial_action: bool = False
    automatic_merge: bool = False

    def verify(self, *, now: datetime | None = None) -> None:
        if not all((self.packet_id, self.actor_id, self.action, self.target)):
            raise ValueError("authorization identity, action and target are required")
        for name, value, length in (
            ("repository_sha", self.repository_sha, 40),
            ("repository_tree_sha", self.repository_tree_sha, 40),
        ):
            if len(value) != length or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError(f"{name} must be a lowercase Git SHA")
        for name, value in (
            ("schema_digest", self.schema_digest),
            ("policy_digest", self.policy_digest),
            ("idempotency_key_digest", self.idempotency_key_digest),
        ):
            if not _SHA256.fullmatch(value):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            raise ValueError("authorization expiry must include a timezone")
        if expiry.astimezone(timezone.utc) <= (now or datetime.now(timezone.utc)):
            raise PermissionError("authorization packet is expired")
        if any(
            (
                self.production_activation,
                self.public_access,
                self.live_model_call,
                self.financial_action,
                self.automatic_merge,
            )
        ):
            raise PermissionError("initial kernel cannot grant consequential authority")
        if self.environment == "PRODUCTION":
            raise PermissionError("production authorization is prohibited")
        if self.decision is AuthorityDecision.ALLOW_STAGING_EXTERNAL_EFFECT:
            raise PermissionError("external staging effect is not enabled in this slice")

    def matches(
        self,
        *,
        action: str,
        target: str,
        repository_sha: str,
        idempotency_key_digest: str,
    ) -> bool:
        return all(
            (
                hmac.compare_digest(self.action, action),
                hmac.compare_digest(self.target, target),
                hmac.compare_digest(self.repository_sha, repository_sha),
                hmac.compare_digest(
                    self.idempotency_key_digest,
                    idempotency_key_digest,
                ),
            )
        )
