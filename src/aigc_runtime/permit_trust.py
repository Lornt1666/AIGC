"""Fail-closed EdDSA permit verifier; trust material must come from managed key storage."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import jwt

from .governed_runtime import GovernanceError, ToolPermit, parse_utc


@dataclass(frozen=True)
class TrustedIssuerKey:
    issuer_id: str
    key_id: str
    public_key_pem: str
    status: str = "ACTIVE"
    not_before: int = 0
    not_after: int = 4102444800


class EdDsaPermitVerifier:
    """Verifies compact EdDSA JWT permits against an explicit issuer/key allowlist."""
    def __init__(self, trusted_issuers: Iterable[str], keys: Iterable[TrustedIssuerKey],
                 revoked_permit_ids: Iterable[str] = (), revoked_keys: Iterable[tuple[str, str]] = ()):
        self.trusted_issuers = frozenset(trusted_issuers)
        self.keys = {(k.issuer_id, k.key_id): k for k in keys}
        self.revoked_permit_ids = frozenset(revoked_permit_ids)
        self.revoked_keys = frozenset(revoked_keys)

    def __call__(self, permit: ToolPermit) -> bool:
        if not permit.issuer_id or not permit.key_id or not permit.signature:
            return False
        if permit.issuer_id not in self.trusted_issuers or permit.permit_id in self.revoked_permit_ids:
            return False
        key_ref = (permit.issuer_id, permit.key_id)
        key = self.keys.get(key_ref)
        if key is None or key_ref in self.revoked_keys or key.status not in {"ACTIVE", "VERIFY_ONLY"}:
            return False
        try:
            now = datetime.now(timezone.utc).timestamp()
            if now < key.not_before or now >= key.not_after:
                return False
            claims = jwt.decode(
                permit.signature, key.public_key_pem, algorithms=["EdDSA"],
                issuer=permit.issuer_id, options={"require": ["iss", "jti", "sub", "iat", "exp", "aud"]},
                audience=permit.tool_name,
            )
            return (
                claims.get("jti") == permit.permit_id
                and claims.get("sub") == permit.agent_id
                and claims.get("task_id") == permit.task_id
                and claims.get("tool") == permit.tool_name
                and claims.get("action") == permit.action
                and claims.get("resource") == permit.resource
                and claims.get("policy_version") == permit.policy_version
                and claims.get("key_id") == permit.key_id
                and claims.get("max_uses") == permit.max_uses
                and claims.get("human_approval_ref") == permit.human_approval_ref
                and claims.get("iat") == int(parse_utc(permit.issued_at).timestamp())
                and claims.get("exp") == int(parse_utc(permit.expires_at).timestamp())
            )
        except (jwt.PyJWTError, TypeError, ValueError):
            return False
