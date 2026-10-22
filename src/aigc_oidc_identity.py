"""OIDC workload identity verifier for AIGC.

Production use requires deployment-supplied issuer/audience/subject policy and durable
revocation/replay storage. Caller-provided authentication booleans are never trusted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Any

import jwt


class IdentityVerificationError(Exception):
    """Raised when workload identity cannot be authenticated and authorized."""


@dataclass(frozen=True)
class OIDCTrustPolicy:
    issuer: str
    audience: str
    jwks_uri: str
    allowed_subjects: frozenset[str]
    allowed_repositories: frozenset[str] = frozenset()
    allowed_refs: frozenset[str] = frozenset()
    allowed_workflows: frozenset[str] = frozenset()
    allowed_actions: frozenset[str] = frozenset()
    max_token_age_seconds: int = 600
    leeway_seconds: int = 30

    def __post_init__(self) -> None:
        if not self.issuer.startswith("https://"):
            raise ValueError("issuer_must_be_https")
        if not self.audience.strip():
            raise ValueError("audience_required")
        if not self.jwks_uri.startswith("https://"):
            raise ValueError("jwks_uri_must_be_https")
        if not self.allowed_subjects:
            raise ValueError("explicit_subject_allowlist_required")
        if self.max_token_age_seconds <= 0 or self.leeway_seconds < 0:
            raise ValueError("invalid_time_policy")


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    issuer: str
    subject: str
    audience: str
    repository: str | None
    ref: str | None
    workflow: str | None
    source_sha: str | None
    token_id: str
    issued_at: int
    expires_at: int
    scopes: tuple[str, ...]


class OIDCIdentityVerifier:
    """Verify issuer-signed OIDC JWTs and apply an explicit authorization allowlist.

    jti_is_revoked and consume_jti must use durable shared storage in production.
    consume_jti must be atomic and reject a token ID already consumed.
    """

    def __init__(
        self,
        policy: OIDCTrustPolicy,
        *,
        jti_is_revoked: Callable[[str], bool],
        consume_jti: Callable[[str, int], bool],
        jwks_client: Any | None = None,
    ) -> None:
        self.policy = policy
        self._jti_is_revoked = jti_is_revoked
        self._consume_jti = consume_jti
        self._jwks = jwks_client or jwt.PyJWKClient(
            policy.jwks_uri,
            cache_jwk_set=True,
            lifespan=300,
            timeout=5,
        )

    def authenticate(self, token: str, *, required_actions: set[str]) -> AuthenticatedPrincipal:
        if not isinstance(token, str) or not token.strip() or len(token) > 65536:
            raise IdentityVerificationError("invalid_token_input")
        if not required_actions or any(not isinstance(x, str) or not x.strip() or x == "*" for x in required_actions):
            raise IdentityVerificationError("explicit_non_wildcard_actions_required")

        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token).key
            verified = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "ES256"],
                issuer=self.policy.issuer,
                audience=self.policy.audience,
                leeway=self.policy.leeway_seconds,
                options={
                    "require": ["iss", "sub", "aud", "exp", "iat", "nbf", "jti"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except Exception as exc:
            raise IdentityVerificationError("oidc_token_validation_failed") from exc

        subject = verified.get("sub")
        jti = verified.get("jti")
        issued_at = verified.get("iat")
        expires_at = verified.get("exp")
        if not isinstance(subject, str) or subject not in self.policy.allowed_subjects:
            raise IdentityVerificationError("subject_not_allowlisted")
        if not isinstance(jti, str) or not jti.strip():
            raise IdentityVerificationError("token_id_missing")
        if not isinstance(issued_at, int) or not isinstance(expires_at, int):
            raise IdentityVerificationError("invalid_token_time_claims")
        if expires_at <= issued_at or expires_at - issued_at > self.policy.max_token_age_seconds:
            raise IdentityVerificationError("token_lifetime_out_of_policy")
        if self._jti_is_revoked(jti):
            raise IdentityVerificationError("token_revoked")

        repository = _optional_string(verified, "repository")
        ref = _optional_string(verified, "ref")
        workflow = _optional_string(verified, "workflow")
        source_sha = _optional_string(verified, "sha")
        if self.policy.allowed_repositories and repository not in self.policy.allowed_repositories:
            raise IdentityVerificationError("repository_not_allowlisted")
        if self.policy.allowed_refs and ref not in self.policy.allowed_refs:
            raise IdentityVerificationError("ref_not_allowlisted")
        if self.policy.allowed_workflows and workflow not in self.policy.allowed_workflows:
            raise IdentityVerificationError("workflow_not_allowlisted")

        # Authorization is derived from deployment-controlled policy, not an
        # arbitrary token claim. Bind requested actions to the configured allowlist.
        if not self.policy.allowed_actions or not required_actions.issubset(self.policy.allowed_actions):
            raise IdentityVerificationError("required_action_not_authorized")

        if not self._consume_jti(jti, expires_at):
            raise IdentityVerificationError("token_replayed_or_store_unavailable")

        return AuthenticatedPrincipal(
            issuer=self.policy.issuer,
            subject=subject,
            audience=self.policy.audience,
            repository=repository,
            ref=ref,
            workflow=workflow,
            source_sha=source_sha,
            token_id=jti,
            issued_at=issued_at,
            expires_at=expires_at,
            scopes=tuple(sorted(required_actions)),
        )


def _optional_string(claims: Mapping[str, Any], name: str) -> str | None:
    value = claims.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise IdentityVerificationError(f"claim_{name}_invalid")
    return value
