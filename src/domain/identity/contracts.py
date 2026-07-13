from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso(value: datetime | None) -> str | None:
    return utc(value).isoformat() if value is not None else None


class IdentityProviderClass(str, Enum):
    LOCAL_DEVELOPMENT = "LOCAL_DEVELOPMENT"
    OIDC = "OIDC"
    WORKLOAD_IDENTITY = "WORKLOAD_IDENTITY"


class IdentityAssuranceLevel(str, Enum):
    IAL0 = "IAL0"
    IAL1 = "IAL1"
    IAL2 = "IAL2"
    IAL3 = "IAL3"


class AuthenticationAssuranceLevel(str, Enum):
    AAL0 = "AAL0"
    AAL1 = "AAL1"
    AAL2 = "AAL2"
    AAL3 = "AAL3"


class FederationAssuranceLevel(str, Enum):
    FAL0 = "FAL0"
    FAL1 = "FAL1"
    FAL2 = "FAL2"
    FAL3 = "FAL3"


class EvidenceMaturity(str, Enum):
    EA0_CLAIMED = "EA0_CLAIMED"
    EA1_SCHEMA_VALID = "EA1_SCHEMA_VALID"
    EA2_SEMANTICALLY_TESTED = "EA2_SEMANTICALLY_TESTED"
    EA3_CI_EXECUTED = "EA3_CI_EXECUTED"
    EA4_STAGING_OBSERVED = "EA4_STAGING_OBSERVED"
    EA5_PRODUCTION_OBSERVED = "EA5_PRODUCTION_OBSERVED"


class RuntimeAuthority(str, Enum):
    LOCAL_SIMULATION = "LOCAL_SIMULATION"
    PRODUCTION_VERIFIED = "PRODUCTION_VERIFIED"


class MembershipState(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    REVOKED = "REVOKED"


class SessionState(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    INVALID = "INVALID"


class IdentityDecision(str, Enum):
    PERMIT = "PERMIT"
    DENY = "DENY"


class IdentityDenialReason(str, Enum):
    MALFORMED_ASSERTION = "MALFORMED_ASSERTION"
    PROVIDER_VERIFICATION_FAILED = "PROVIDER_VERIFICATION_FAILED"
    PROVIDER_CLASS_MISMATCH = "PROVIDER_CLASS_MISMATCH"
    LOCAL_PROVIDER_PROHIBITED = "LOCAL_PROVIDER_PROHIBITED"
    PROVIDER_NOT_ALLOWED = "PROVIDER_NOT_ALLOWED"
    ISSUER_NOT_ALLOWED = "ISSUER_NOT_ALLOWED"
    AUDIENCE_NOT_ALLOWED = "AUDIENCE_NOT_ALLOWED"
    UNVERIFIED_EVIDENCE = "UNVERIFIED_EVIDENCE"
    PROVIDER_ASSERTION_EXPIRED = "PROVIDER_ASSERTION_EXPIRED"
    INSUFFICIENT_IAL = "INSUFFICIENT_IAL"
    INSUFFICIENT_AAL = "INSUFFICIENT_AAL"
    INSUFFICIENT_FAL = "INSUFFICIENT_FAL"
    INSUFFICIENT_EVIDENCE_MATURITY = "INSUFFICIENT_EVIDENCE_MATURITY"
    MEMBERSHIP_MISSING = "MEMBERSHIP_MISSING"
    MEMBERSHIP_INACTIVE = "MEMBERSHIP_INACTIVE"
    MEMBERSHIP_REVOKED = "MEMBERSHIP_REVOKED"
    MEMBERSHIP_EXPIRED = "MEMBERSHIP_EXPIRED"
    MEMBERSHIP_PRINCIPAL_MISMATCH = "MEMBERSHIP_PRINCIPAL_MISMATCH"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    PROJECT_MEMBERSHIP_MISSING = "PROJECT_MEMBERSHIP_MISSING"
    SESSION_MISSING = "SESSION_MISSING"
    SESSION_INACTIVE = "SESSION_INACTIVE"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_REVOKED = "SESSION_REVOKED"
    SESSION_PRINCIPAL_MISMATCH = "SESSION_PRINCIPAL_MISMATCH"
    SESSION_MEMBERSHIP_MISMATCH = "SESSION_MEMBERSHIP_MISMATCH"
    SESSION_TENANT_MISMATCH = "SESSION_TENANT_MISMATCH"
    SESSION_PROJECT_MISMATCH = "SESSION_PROJECT_MISMATCH"
    SESSION_ASSURANCE_MISMATCH = "SESSION_ASSURANCE_MISMATCH"
    SESSION_TOO_OLD = "SESSION_TOO_OLD"
    REVISION_UNBOUND = "REVISION_UNBOUND"
    REQUEST_DIGEST_MISMATCH = "REQUEST_DIGEST_MISMATCH"
    REPLAY_CONFLICT = "REPLAY_CONFLICT"
    ROLE_SOURCE_UNTRUSTED = "ROLE_SOURCE_UNTRUSTED"
    CONTEXT_SCHEMA_INVALID = "CONTEXT_SCHEMA_INVALID"
    RECEIPT_SCHEMA_INVALID = "RECEIPT_SCHEMA_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class ProviderVerification:
    provider_class: IdentityProviderClass
    provider_binding_id: str
    assertion_id: str
    issuer: str
    subject: str
    principal_id: str | None
    audiences: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    nonce_digest: str | None
    claims_digest: str
    identity_assurance: IdentityAssuranceLevel
    authentication_assurance: AuthenticationAssuranceLevel
    federation_assurance: FederationAssuranceLevel
    evidence_maturity: EvidenceMaturity
    runtime_authority: RuntimeAuthority
    verified: bool
    evidence_ids: tuple[str, ...]
    denial_reasons: tuple[IdentityDenialReason, ...] = ()


@dataclass(frozen=True)
class MembershipBinding:
    membership_id: str
    principal_id: str
    tenant_id: str
    project_ids: tuple[str, ...]
    roles: tuple[str, ...]
    granted_scopes: tuple[str, ...]
    state: MembershipState
    valid_from: datetime
    expires_at: datetime
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SessionBinding:
    session_id: str
    principal_id: str
    membership_id: str
    tenant_id: str
    project_id: str
    state: SessionState
    issued_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    authentication_assurance: AuthenticationAssuranceLevel
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class IdentityContext:
    principal_id: str
    provider_class: IdentityProviderClass
    provider_binding_id: str
    membership_id: str
    tenant_id: str
    project_id: str
    roles: tuple[str, ...]
    granted_scopes: tuple[str, ...]
    session_id: str
    session_state: SessionState
    identity_assurance: IdentityAssuranceLevel
    authentication_assurance: AuthenticationAssuranceLevel
    federation_assurance: FederationAssuranceLevel
    evidence_maturity: EvidenceMaturity
    runtime_authority: RuntimeAuthority
    exact_revision: str
    issued_at: datetime
    expires_at: datetime
    evidence_ids: tuple[str, ...]
    verified: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": "AIGC-PIBC-001",
            "contract_version": "1.0.0",
            "principal_id": self.principal_id,
            "provider_class": self.provider_class.value,
            "provider_binding_id": self.provider_binding_id,
            "membership_id": self.membership_id,
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "roles": list(self.roles),
            "granted_scopes": list(self.granted_scopes),
            "session_id": self.session_id,
            "session_state": self.session_state.value,
            "identity_assurance": self.identity_assurance.value,
            "authentication_assurance": self.authentication_assurance.value,
            "federation_assurance": self.federation_assurance.value,
            "evidence_maturity": self.evidence_maturity.value,
            "runtime_authority": self.runtime_authority.value,
            "exact_revision": self.exact_revision,
            "issued_at": iso(self.issued_at),
            "expires_at": iso(self.expires_at),
            "evidence_ids": list(self.evidence_ids),
            "verified": self.verified,
            "external_action_performed": False,
        }


@dataclass(frozen=True)
class IdentityEvidenceReceipt:
    receipt_id: str
    request_digest: str
    replay_key_digest: str
    result: IdentityDecision
    reason_codes: tuple[IdentityDenialReason, ...]
    provider_class: IdentityProviderClass | None
    provider_binding_id: str | None
    assertion_id: str | None
    principal_id: str | None
    membership_id: str | None
    session_id: str | None
    tenant_id: str | None
    project_id: str | None
    identity_assurance: IdentityAssuranceLevel | None
    authentication_assurance: AuthenticationAssuranceLevel | None
    federation_assurance: FederationAssuranceLevel | None
    evidence_maturity: EvidenceMaturity | None
    runtime_authority: RuntimeAuthority | None
    exact_revision: str
    evidence_ids: tuple[str, ...]
    production_mode: bool
    created_at: datetime
    expires_at: datetime | None
    retention_class: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": "AIGC-PIBC-RECEIPT-001",
            "contract_version": "1.0.0",
            "receipt_id": self.receipt_id,
            "request_digest": self.request_digest,
            "replay_key_digest": self.replay_key_digest,
            "result": self.result.value,
            "reason_codes": [item.value for item in self.reason_codes],
            "provider_class": self.provider_class.value if self.provider_class else None,
            "provider_binding_id": self.provider_binding_id,
            "assertion_id": self.assertion_id,
            "principal_id": self.principal_id,
            "membership_id": self.membership_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "identity_assurance": self.identity_assurance.value if self.identity_assurance else None,
            "authentication_assurance": self.authentication_assurance.value if self.authentication_assurance else None,
            "federation_assurance": self.federation_assurance.value if self.federation_assurance else None,
            "evidence_maturity": self.evidence_maturity.value if self.evidence_maturity else None,
            "runtime_authority": self.runtime_authority.value if self.runtime_authority else None,
            "exact_revision": self.exact_revision,
            "evidence_ids": list(self.evidence_ids),
            "production_mode": self.production_mode,
            "created_at": iso(self.created_at),
            "expires_at": iso(self.expires_at),
            "retention_class": self.retention_class,
            "operator_review_required": True,
            "state_changed": False,
            "external_action_performed": False,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IdentityEvidenceReceipt":
        return cls(
            receipt_id=str(value["receipt_id"]),
            request_digest=str(value["request_digest"]),
            replay_key_digest=str(value["replay_key_digest"]),
            result=IdentityDecision(str(value["result"])),
            reason_codes=tuple(IdentityDenialReason(str(item)) for item in value.get("reason_codes", ())),
            provider_class=IdentityProviderClass(str(value["provider_class"])) if value.get("provider_class") else None,
            provider_binding_id=str(value["provider_binding_id"]) if value.get("provider_binding_id") else None,
            assertion_id=str(value["assertion_id"]) if value.get("assertion_id") else None,
            principal_id=str(value["principal_id"]) if value.get("principal_id") else None,
            membership_id=str(value["membership_id"]) if value.get("membership_id") else None,
            session_id=str(value["session_id"]) if value.get("session_id") else None,
            tenant_id=str(value["tenant_id"]) if value.get("tenant_id") else None,
            project_id=str(value["project_id"]) if value.get("project_id") else None,
            identity_assurance=IdentityAssuranceLevel(str(value["identity_assurance"])) if value.get("identity_assurance") else None,
            authentication_assurance=AuthenticationAssuranceLevel(str(value["authentication_assurance"])) if value.get("authentication_assurance") else None,
            federation_assurance=FederationAssuranceLevel(str(value["federation_assurance"])) if value.get("federation_assurance") else None,
            evidence_maturity=EvidenceMaturity(str(value["evidence_maturity"])) if value.get("evidence_maturity") else None,
            runtime_authority=RuntimeAuthority(str(value["runtime_authority"])) if value.get("runtime_authority") else None,
            exact_revision=str(value["exact_revision"]),
            evidence_ids=tuple(str(item) for item in value.get("evidence_ids", ())),
            production_mode=bool(value["production_mode"]),
            created_at=datetime.fromisoformat(str(value["created_at"]).replace("Z", "+00:00")),
            expires_at=datetime.fromisoformat(str(value["expires_at"]).replace("Z", "+00:00")) if value.get("expires_at") else None,
            retention_class=str(value["retention_class"]),
        )


@dataclass(frozen=True)
class IdentityEvaluation:
    permitted: bool
    result: IdentityDecision
    reason_codes: tuple[IdentityDenialReason, ...]
    context: IdentityContext | None
    receipt: IdentityEvidenceReceipt

    def to_dict(self) -> dict[str, Any]:
        return {
            "permitted": self.permitted,
            "result": self.result.value,
            "reason_codes": [item.value for item in self.reason_codes],
            "context": self.context.to_dict() if self.context else None,
            "receipt": self.receipt.to_dict(),
            "operator_review_required": True,
            "external_action_performed": False,
        }


class IdentityEvidenceReceiptRepository(Protocol):
    def append(self, receipt: IdentityEvidenceReceipt) -> IdentityEvidenceReceipt: ...
    def get(self, receipt_id: str) -> IdentityEvidenceReceipt | None: ...
    def get_by_replay_key(self, replay_key_digest: str) -> IdentityEvidenceReceipt | None: ...


class MembershipResolver(Protocol):
    def resolve_membership(self, *, principal_id: str, membership_id: str, tenant_id: str, project_id: str, now: datetime) -> MembershipBinding | None: ...


class SessionVerifier(Protocol):
    def verify_session(self, *, session_id: str, principal_id: str, membership_id: str, tenant_id: str, project_id: str, now: datetime) -> SessionBinding | None: ...
