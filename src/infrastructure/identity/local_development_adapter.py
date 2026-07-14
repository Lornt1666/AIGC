from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from src.domain.identity import (
    AuthenticationAssuranceLevel,
    EvidenceMaturity,
    FederationAssuranceLevel,
    IdentityAssuranceLevel,
    IdentityDenialReason,
    IdentityProviderClass,
    MembershipBinding,
    MembershipState,
    ProviderVerification,
    RuntimeAuthority,
    SessionBinding,
    SessionState,
)


_ALLOWED_ASSERTION_KEYS = {
    "assertion_id",
    "principal_id",
    "issuer",
    "audience",
}
_SENSITIVE_OR_AUTHORITY_KEYS = {
    "access_token",
    "refresh_token",
    "id_token",
    "client_secret",
    "credential",
    "credentials",
    "nonce",
    "provider_claims",
    "claims",
    "roles",
    "role",
    "scopes",
    "tenant_id",
    "project_id",
    "membership_id",
    "session_id",
    "assurance",
    "identity_assurance",
    "authentication_assurance",
    "federation_assurance",
    "verified",
}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _unique_strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict.fromkeys(str(item) for item in value if str(item)))


class LocalDevelopmentIdentityAdapter:
    """Fixture-backed identity adapter that can never advertise production authority.

    The adapter accepts only a minimal assertion selector. Memberships, roles,
    scopes, session bindings, assurance values, and expiry are resolved from the
    repository-owned fixture rather than from caller-controlled input.
    """

    provider_class = IdentityProviderClass.LOCAL_DEVELOPMENT
    provider_binding_id = "aigc-local-development-fixture-v1"

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path)
        self._fixture = json.loads(self.fixture_path.read_text(encoding="utf-8"))

    def verify(
        self,
        raw_assertion: Mapping[str, Any],
        *,
        now: datetime,
    ) -> ProviderVerification:
        current = now.astimezone(timezone.utc)
        assertion = dict(raw_assertion) if isinstance(raw_assertion, Mapping) else {}
        reasons: list[IdentityDenialReason] = []

        unknown = set(assertion) - _ALLOWED_ASSERTION_KEYS
        if unknown & _SENSITIVE_OR_AUTHORITY_KEYS:
            reasons.append(IdentityDenialReason.ROLE_SOURCE_UNTRUSTED)
        if unknown:
            reasons.append(IdentityDenialReason.MALFORMED_ASSERTION)

        assertion_id = str(assertion.get("assertion_id") or "")
        principal_id = str(assertion.get("principal_id") or "")
        issuer = str(assertion.get("issuer") or "")
        audience = str(assertion.get("audience") or "")
        if not assertion_id or not _ID.fullmatch(assertion_id):
            reasons.append(IdentityDenialReason.MALFORMED_ASSERTION)
            assertion_id = "invalid-" + _digest(assertion)[:16]
        if not principal_id or not _ID.fullmatch(principal_id):
            reasons.append(IdentityDenialReason.MALFORMED_ASSERTION)

        principal = next(
            (
                item
                for item in self._fixture.get("principals", [])
                if item.get("principal_id") == principal_id
            ),
            None,
        )
        if principal is None:
            reasons.append(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED)
            issued_at = current
            expires_at = current
            resolved_principal_id: str | None = None
            ial = IdentityAssuranceLevel.IAL0
            aal = AuthenticationAssuranceLevel.AAL0
            fal = FederationAssuranceLevel.FAL0
            evidence_ids: tuple[str, ...] = ()
            claims_digest = _digest({"principal_id": principal_id or "unknown"})
        else:
            expected_issuer = str(principal.get("authority_source") or "")
            if issuer != expected_issuer:
                reasons.append(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED)
            if audience != "aigc-local-operator":
                reasons.append(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED)
            if str(principal.get("principal_status") or "").upper() != "ACTIVE":
                reasons.append(IdentityDenialReason.PROVIDER_VERIFICATION_FAILED)
            issued_at = _parse_datetime(principal["valid_from"])
            expires_at = _parse_datetime(principal["expires_at"])
            resolved_principal_id = principal_id
            ial = IdentityAssuranceLevel(str(principal["identity_assurance"]))
            aal = AuthenticationAssuranceLevel(
                str(principal["authentication_assurance"])
            )
            fal = FederationAssuranceLevel(str(principal["federation_assurance"]))
            evidence_ids = _unique_strings(principal.get("evidence_ids"))
            claims_digest = _digest(
                {
                    "principal_id": principal_id,
                    "principal_status": principal.get("principal_status"),
                    "identity_assurance": ial.value,
                    "authentication_assurance": aal.value,
                    "federation_assurance": fal.value,
                    "valid_from": principal.get("valid_from"),
                    "expires_at": principal.get("expires_at"),
                    "revocation_version": principal.get("revocation_version"),
                }
            )

        if expires_at <= current:
            reasons.append(IdentityDenialReason.PROVIDER_ASSERTION_EXPIRED)

        reason_tuple = tuple(dict.fromkeys(reasons))
        return ProviderVerification(
            provider_class=self.provider_class,
            provider_binding_id=self.provider_binding_id,
            assertion_id=assertion_id,
            issuer=issuer,
            subject=principal_id or "unknown",
            principal_id=resolved_principal_id,
            audiences=(audience,) if audience else (),
            issued_at=issued_at,
            expires_at=expires_at,
            nonce_digest=None,
            claims_digest=claims_digest,
            identity_assurance=ial,
            authentication_assurance=aal,
            federation_assurance=fal,
            evidence_maturity=EvidenceMaturity.EA1_SCHEMA_VALID,
            runtime_authority=RuntimeAuthority.LOCAL_SIMULATION,
            verified=not reason_tuple,
            evidence_ids=evidence_ids,
            denial_reasons=reason_tuple,
        )

    def resolve_membership(
        self,
        *,
        principal_id: str,
        membership_id: str,
        tenant_id: str,
        project_id: str,
        now: datetime,
    ) -> MembershipBinding | None:
        del principal_id, tenant_id, project_id, now
        record = next(
            (
                item
                for item in self._fixture.get("memberships", [])
                if item.get("membership_id") == membership_id
            ),
            None,
        )
        if record is None:
            return None
        state = MembershipState(str(record.get("status") or "INACTIVE").upper())
        if record.get("revoked") is True:
            state = MembershipState.REVOKED
        return MembershipBinding(
            membership_id=str(record["membership_id"]),
            principal_id=str(record["principal_id"]),
            tenant_id=str(record["tenant_id"]),
            project_ids=_unique_strings(record.get("project_ids")),
            roles=_unique_strings(record.get("roles")),
            granted_scopes=_unique_strings(record.get("granted_scopes")),
            state=state,
            valid_from=_parse_datetime(record["valid_from"]),
            expires_at=_parse_datetime(record["expires_at"]),
            evidence_ids=_unique_strings(record.get("evidence_ids")),
        )

    def verify_session(
        self,
        *,
        session_id: str,
        principal_id: str,
        membership_id: str,
        tenant_id: str,
        project_id: str,
        now: datetime,
    ) -> SessionBinding | None:
        del principal_id, membership_id, tenant_id, project_id, now
        record = next(
            (
                item
                for item in self._fixture.get("sessions", [])
                if item.get("session_id") == session_id
            ),
            None,
        )
        if record is None:
            return None
        raw_state = str(record.get("session_state") or "INVALID").upper()
        state = (
            SessionState(raw_state)
            if raw_state in {item.value for item in SessionState}
            else SessionState.INVALID
        )
        evidence_id = "EVID-LOCAL-SESSION-" + sha256(
            str(record["session_id"]).encode("utf-8")
        ).hexdigest()[:16].upper()
        return SessionBinding(
            session_id=str(record["session_id"]),
            principal_id=str(record["principal_id"]),
            membership_id=str(record["membership_id"]),
            tenant_id=str(record["tenant_id"]),
            project_id=str(record["active_project_id"]),
            state=state,
            issued_at=_parse_datetime(record["issued_at"]),
            idle_expires_at=_parse_datetime(record["idle_expires_at"]),
            absolute_expires_at=_parse_datetime(record["absolute_expires_at"]),
            authentication_assurance=AuthenticationAssuranceLevel(
                str(record["authentication_assurance"])
            ),
            evidence_ids=(evidence_id,),
        )
