from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from src.domain.identity import (
    AuthenticationAssuranceLevel,
    EvidenceMaturity,
    FederationAssuranceLevel,
    IdentityAssuranceLevel,
    IdentityContext,
    IdentityContractError,
    IdentityDecision,
    IdentityDenialReason,
    IdentityEvaluation,
    IdentityEvidenceReceipt,
    IdentityEvidenceReceiptRepository,
    IdentityProviderClass,
    MembershipBinding,
    MembershipResolver,
    MembershipState,
    ProviderVerification,
    RuntimeAuthority,
    SessionBinding,
    SessionState,
    SessionVerifier,
)
from src.infrastructure.identity.provider_protocol import IdentityProviderProtocol


_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_ASSURANCE_RANKS = {
    "ial": {"IAL0": 0, "IAL1": 1, "IAL2": 2, "IAL3": 3},
    "aal": {"AAL0": 0, "AAL1": 1, "AAL2": 2, "AAL3": 3},
    "fal": {"FAL0": 0, "FAL1": 1, "FAL2": 2, "FAL3": 3},
    "evidence": {
        "EA0_CLAIMED": 0,
        "EA1_SCHEMA_VALID": 1,
        "EA2_SEMANTICALLY_TESTED": 2,
        "EA3_CI_EXECUTED": 3,
        "EA4_STAGING_OBSERVED": 4,
        "EA5_PRODUCTION_OBSERVED": 5,
    },
}


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


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _unique_reasons(
    reasons: Sequence[IdentityDenialReason],
) -> tuple[IdentityDenialReason, ...]:
    return tuple(dict.fromkeys(reasons))


class IdentityBoundaryService:
    """PIBC-v1 trust boundary.

    This service accepts an untrusted provider assertion, resolves repository-owned
    membership and session evidence, enforces assurance and exact-revision policy,
    emits a strict normalized context only on permit, and persists a redacted,
    immutable receipt for every decision. It performs no external action.
    """

    def __init__(
        self,
        *,
        provider: IdentityProviderProtocol,
        membership_resolver: MembershipResolver,
        session_verifier: SessionVerifier,
        receipt_repository: IdentityEvidenceReceiptRepository,
        config_path: str | Path,
        context_schema_path: str | Path,
        receipt_schema_path: str | Path,
    ) -> None:
        self.provider = provider
        self.membership_resolver = membership_resolver
        self.session_verifier = session_verifier
        self.receipt_repository = receipt_repository
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self._validate_config()
        self.context_validator = self._validator(context_schema_path)
        self.receipt_validator = self._validator(receipt_schema_path)

    @staticmethod
    def _validator(path: str | Path) -> Draft202012Validator:
        schema = json.loads(Path(path).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def _validate_config(self) -> None:
        if self.config.get("contract_id") != "AIGC-PIBC-CONFIG-001":
            raise ValueError("Unsupported identity-boundary configuration")
        if self.config.get("version") != "1.0.0":
            raise ValueError("Unsupported identity-boundary configuration version")
        required_false = {
            "persist_raw_assertions",
            "persist_raw_tokens",
            "persist_raw_nonce",
            "external_action_performed",
        }
        weakened = sorted(
            key for key in required_false if self.config.get(key) is not False
        )
        if weakened:
            raise ValueError(
                "Identity-boundary privacy controls cannot be weakened: "
                + ", ".join(weakened)
            )
        if self.config.get("operator_review_required") is not True:
            raise ValueError("Identity-boundary decisions require operator review")

    def evaluate(
        self,
        *,
        provider_type: str,
        raw_assertion: Mapping[str, Any],
        membership_id: str,
        session_id: str,
        tenant_id: str,
        project_id: str,
        exact_revision: str,
        production_mode: bool = False,
        now: datetime | None = None,
    ) -> IdentityEvaluation:
        current = _utc(now or datetime.now(timezone.utc))
        reasons: list[IdentityDenialReason] = []

        try:
            verification = self.provider.verify(raw_assertion, now=current)
        except Exception:
            verification = self._failed_verification(raw_assertion, current)
            reasons.append(IdentityDenialReason.INTERNAL_ERROR)

        reasons.extend(verification.denial_reasons)
        if not verification.verified:
            reasons.append(IdentityDenialReason.UNVERIFIED_EVIDENCE)

        try:
            requested_provider = IdentityProviderClass(str(provider_type))
        except ValueError:
            requested_provider = None
            reasons.append(IdentityDenialReason.PROVIDER_CLASS_MISMATCH)
        if requested_provider is not None and requested_provider != self.provider.provider_class:
            reasons.append(IdentityDenialReason.PROVIDER_CLASS_MISMATCH)

        mode_key = "production" if production_mode else "local"
        allowed_classes = {
            str(item)
            for item in self.config["allowed_provider_classes"][mode_key]
        }
        if verification.provider_class.value not in allowed_classes:
            reasons.append(IdentityDenialReason.PROVIDER_NOT_ALLOWED)
        if (
            production_mode
            and verification.provider_class
            is IdentityProviderClass.LOCAL_DEVELOPMENT
        ):
            reasons.append(IdentityDenialReason.LOCAL_PROVIDER_PROHIBITED)

        if verification.expires_at <= current:
            reasons.append(IdentityDenialReason.PROVIDER_ASSERTION_EXPIRED)

        if production_mode:
            allowed_issuers = {
                str(item) for item in self.config["production_allowed_issuers"]
            }
            allowed_audiences = {
                str(item) for item in self.config["production_allowed_audiences"]
            }
            if not allowed_issuers or verification.issuer not in allowed_issuers:
                reasons.append(IdentityDenialReason.ISSUER_NOT_ALLOWED)
            if not allowed_audiences or not (
                allowed_audiences & set(verification.audiences)
            ):
                reasons.append(IdentityDenialReason.AUDIENCE_NOT_ALLOWED)
            if verification.runtime_authority is not RuntimeAuthority.PRODUCTION_VERIFIED:
                reasons.append(IdentityDenialReason.UNVERIFIED_EVIDENCE)

        minimums = self.config["minimum_assurance"][mode_key]
        if (
            _ASSURANCE_RANKS["ial"][verification.identity_assurance.value]
            < _ASSURANCE_RANKS["ial"][str(minimums["ial"])]
        ):
            reasons.append(IdentityDenialReason.INSUFFICIENT_IAL)
        if (
            _ASSURANCE_RANKS["aal"][
                verification.authentication_assurance.value
            ]
            < _ASSURANCE_RANKS["aal"][str(minimums["aal"])]
        ):
            reasons.append(IdentityDenialReason.INSUFFICIENT_AAL)
        if (
            _ASSURANCE_RANKS["fal"][verification.federation_assurance.value]
            < _ASSURANCE_RANKS["fal"][str(minimums["fal"])]
        ):
            reasons.append(IdentityDenialReason.INSUFFICIENT_FAL)
        minimum_evidence = str(
            self.config["minimum_evidence_maturity"][mode_key]
        )
        if (
            _ASSURANCE_RANKS["evidence"][verification.evidence_maturity.value]
            < _ASSURANCE_RANKS["evidence"][minimum_evidence]
        ):
            reasons.append(
                IdentityDenialReason.INSUFFICIENT_EVIDENCE_MATURITY
            )

        if not tenant_id:
            reasons.append(IdentityDenialReason.TENANT_MISMATCH)
        if self.config.get("require_project_binding") and not project_id:
            reasons.append(IdentityDenialReason.PROJECT_MEMBERSHIP_MISSING)
        if (
            production_mode
            and self.config.get("require_exact_revision_in_production")
            and not _HEX40.fullmatch(str(exact_revision))
        ):
            reasons.append(IdentityDenialReason.REVISION_UNBOUND)
        elif not exact_revision:
            reasons.append(IdentityDenialReason.REVISION_UNBOUND)

        membership: MembershipBinding | None = None
        session: SessionBinding | None = None
        principal_id = verification.principal_id
        if principal_id:
            membership = self.membership_resolver.resolve_membership(
                principal_id=principal_id,
                membership_id=membership_id,
                tenant_id=tenant_id,
                project_id=project_id,
                now=current,
            )
            self._evaluate_membership(
                membership,
                principal_id=principal_id,
                tenant_id=tenant_id,
                project_id=project_id,
                current=current,
                reasons=reasons,
            )
            session = self.session_verifier.verify_session(
                session_id=session_id,
                principal_id=principal_id,
                membership_id=membership_id,
                tenant_id=tenant_id,
                project_id=project_id,
                now=current,
            )
            self._evaluate_session(
                session,
                principal_id=principal_id,
                membership_id=membership_id,
                tenant_id=tenant_id,
                project_id=project_id,
                minimum_aal=str(minimums["aal"]),
                mode_key=mode_key,
                current=current,
                reasons=reasons,
            )
        else:
            reasons.extend(
                [
                    IdentityDenialReason.PROVIDER_VERIFICATION_FAILED,
                    IdentityDenialReason.MEMBERSHIP_MISSING,
                    IdentityDenialReason.SESSION_MISSING,
                ]
            )

        evidence_ids = tuple(
            dict.fromkeys(
                [
                    *verification.evidence_ids,
                    *(membership.evidence_ids if membership else ()),
                    *(session.evidence_ids if session else ()),
                ]
            )
        )
        request_material = self._request_material(
            verification=verification,
            membership=membership,
            session=session,
            membership_id=membership_id,
            session_id=session_id,
            tenant_id=tenant_id,
            project_id=project_id,
            exact_revision=exact_revision,
            production_mode=production_mode,
        )
        request_digest = _digest(request_material)
        replay_key_digest = _digest(
            {
                "provider_binding_id": verification.provider_binding_id,
                "assertion_id": verification.assertion_id,
            }
        )

        existing = self.receipt_repository.get_by_replay_key(replay_key_digest)
        if existing is not None:
            if existing.request_digest == request_digest:
                return IdentityEvaluation(
                    permitted=existing.result is IdentityDecision.PERMIT,
                    result=existing.result,
                    reason_codes=existing.reason_codes,
                    context=None,
                    receipt=existing,
                )
            reasons.append(IdentityDenialReason.REPLAY_CONFLICT)
            replay_key_digest = _digest(
                {
                    "original_replay_key_digest": replay_key_digest,
                    "conflicting_request_digest": request_digest,
                }
            )

        reason_tuple = _unique_reasons(reasons)
        context: IdentityContext | None = None
        if not reason_tuple and membership and session and principal_id:
            context = self._context(
                verification=verification,
                membership=membership,
                session=session,
                exact_revision=exact_revision,
                evidence_ids=evidence_ids,
            )
            context_errors = self._schema_errors(
                self.context_validator,
                context.to_dict(),
            )
            if context_errors:
                reason_tuple = (
                    IdentityDenialReason.CONTEXT_SCHEMA_INVALID,
                )
                context = None

        result = (
            IdentityDecision.PERMIT
            if context is not None and not reason_tuple
            else IdentityDecision.DENY
        )
        receipt_id = "IDR-" + sha256(
            (
                request_digest
                + "|"
                + result.value
                + "|"
                + ",".join(item.value for item in reason_tuple)
            ).encode("utf-8")
        ).hexdigest()[:24].upper()
        receipt = IdentityEvidenceReceipt(
            receipt_id=receipt_id,
            request_digest=request_digest,
            replay_key_digest=replay_key_digest,
            result=result,
            reason_codes=reason_tuple,
            provider_class=verification.provider_class,
            provider_binding_id=verification.provider_binding_id,
            assertion_id=verification.assertion_id,
            principal_id=principal_id,
            membership_id=membership.membership_id if membership else membership_id or None,
            session_id=session.session_id if session else session_id or None,
            tenant_id=tenant_id or None,
            project_id=project_id or None,
            identity_assurance=verification.identity_assurance,
            authentication_assurance=verification.authentication_assurance,
            federation_assurance=verification.federation_assurance,
            evidence_maturity=verification.evidence_maturity,
            runtime_authority=verification.runtime_authority,
            exact_revision=exact_revision or "unbound",
            evidence_ids=evidence_ids,
            production_mode=production_mode,
            created_at=current,
            expires_at=verification.expires_at,
            retention_class=str(self.config["retention_class"]),
        )
        receipt_errors = self._schema_errors(
            self.receipt_validator,
            receipt.to_dict(),
        )
        if receipt_errors:
            raise IdentityContractError(
                "Identity evidence receipt violates its contract: "
                + "; ".join(receipt_errors[:5])
            )
        stored = self.receipt_repository.append(receipt)
        return IdentityEvaluation(
            permitted=result is IdentityDecision.PERMIT,
            result=result,
            reason_codes=reason_tuple,
            context=context,
            receipt=stored,
        )

    def get_receipt(
        self,
        receipt_id: str,
    ) -> IdentityEvidenceReceipt | None:
        return self.receipt_repository.get(receipt_id)

    def _evaluate_membership(
        self,
        membership: MembershipBinding | None,
        *,
        principal_id: str,
        tenant_id: str,
        project_id: str,
        current: datetime,
        reasons: list[IdentityDenialReason],
    ) -> None:
        if membership is None:
            reasons.append(IdentityDenialReason.MEMBERSHIP_MISSING)
            return
        if membership.principal_id != principal_id:
            reasons.append(
                IdentityDenialReason.MEMBERSHIP_PRINCIPAL_MISMATCH
            )
        if membership.tenant_id != tenant_id:
            reasons.append(IdentityDenialReason.TENANT_MISMATCH)
        if project_id not in membership.project_ids:
            reasons.append(IdentityDenialReason.PROJECT_MEMBERSHIP_MISSING)
        if membership.state is MembershipState.REVOKED:
            reasons.append(IdentityDenialReason.MEMBERSHIP_REVOKED)
        elif membership.state is not MembershipState.ACTIVE:
            reasons.append(IdentityDenialReason.MEMBERSHIP_INACTIVE)
        if current < membership.valid_from or current >= membership.expires_at:
            reasons.append(IdentityDenialReason.MEMBERSHIP_EXPIRED)

    def _evaluate_session(
        self,
        session: SessionBinding | None,
        *,
        principal_id: str,
        membership_id: str,
        tenant_id: str,
        project_id: str,
        minimum_aal: str,
        mode_key: str,
        current: datetime,
        reasons: list[IdentityDenialReason],
    ) -> None:
        if session is None:
            reasons.append(IdentityDenialReason.SESSION_MISSING)
            return
        if session.principal_id != principal_id:
            reasons.append(IdentityDenialReason.SESSION_PRINCIPAL_MISMATCH)
        if session.membership_id != membership_id:
            reasons.append(
                IdentityDenialReason.SESSION_MEMBERSHIP_MISMATCH
            )
        if session.tenant_id != tenant_id:
            reasons.append(IdentityDenialReason.SESSION_TENANT_MISMATCH)
        if session.project_id != project_id:
            reasons.append(IdentityDenialReason.SESSION_PROJECT_MISMATCH)
        if session.state is SessionState.REVOKED:
            reasons.append(IdentityDenialReason.SESSION_REVOKED)
        elif session.state is not SessionState.ACTIVE:
            reasons.append(IdentityDenialReason.SESSION_INACTIVE)
        if current >= session.idle_expires_at or current >= session.absolute_expires_at:
            reasons.append(IdentityDenialReason.SESSION_EXPIRED)
        if (
            _ASSURANCE_RANKS["aal"][session.authentication_assurance.value]
            < _ASSURANCE_RANKS["aal"][minimum_aal]
        ):
            reasons.append(IdentityDenialReason.SESSION_ASSURANCE_MISMATCH)
        max_age_seconds = int(self.config["session_max_age_seconds"][mode_key])
        if (current - session.issued_at).total_seconds() > max_age_seconds:
            reasons.append(IdentityDenialReason.SESSION_TOO_OLD)

    @staticmethod
    def _context(
        *,
        verification: ProviderVerification,
        membership: MembershipBinding,
        session: SessionBinding,
        exact_revision: str,
        evidence_ids: tuple[str, ...],
    ) -> IdentityContext:
        issued_at = max(
            verification.issued_at,
            membership.valid_from,
            session.issued_at,
        )
        expires_at = min(
            verification.expires_at,
            membership.expires_at,
            session.idle_expires_at,
            session.absolute_expires_at,
        )
        effective_aal = min(
            verification.authentication_assurance,
            session.authentication_assurance,
            key=lambda item: _ASSURANCE_RANKS["aal"][item.value],
        )
        return IdentityContext(
            principal_id=str(verification.principal_id),
            provider_class=verification.provider_class,
            provider_binding_id=verification.provider_binding_id,
            membership_id=membership.membership_id,
            tenant_id=membership.tenant_id,
            project_id=session.project_id,
            roles=membership.roles,
            granted_scopes=membership.granted_scopes,
            session_id=session.session_id,
            session_state=SessionState.ACTIVE,
            identity_assurance=verification.identity_assurance,
            authentication_assurance=effective_aal,
            federation_assurance=verification.federation_assurance,
            evidence_maturity=verification.evidence_maturity,
            runtime_authority=verification.runtime_authority,
            exact_revision=exact_revision,
            issued_at=issued_at,
            expires_at=expires_at,
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def _request_material(
        *,
        verification: ProviderVerification,
        membership: MembershipBinding | None,
        session: SessionBinding | None,
        membership_id: str,
        session_id: str,
        tenant_id: str,
        project_id: str,
        exact_revision: str,
        production_mode: bool,
    ) -> dict[str, Any]:
        return {
            "provider_class": verification.provider_class.value,
            "provider_binding_id": verification.provider_binding_id,
            "assertion_id": verification.assertion_id,
            "claims_digest": verification.claims_digest,
            "principal_id": verification.principal_id,
            "membership_id": membership_id,
            "resolved_membership": (
                {
                    "membership_id": membership.membership_id,
                    "principal_id": membership.principal_id,
                    "tenant_id": membership.tenant_id,
                    "project_ids": list(membership.project_ids),
                    "roles": list(membership.roles),
                    "granted_scopes": list(membership.granted_scopes),
                    "state": membership.state.value,
                    "evidence_ids": list(membership.evidence_ids),
                }
                if membership
                else None
            ),
            "session_id": session_id,
            "resolved_session": (
                {
                    "session_id": session.session_id,
                    "principal_id": session.principal_id,
                    "membership_id": session.membership_id,
                    "tenant_id": session.tenant_id,
                    "project_id": session.project_id,
                    "state": session.state.value,
                    "authentication_assurance": (
                        session.authentication_assurance.value
                    ),
                    "evidence_ids": list(session.evidence_ids),
                }
                if session
                else None
            ),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "exact_revision": exact_revision,
            "production_mode": production_mode,
        }

    @staticmethod
    def _schema_errors(
        validator: Draft202012Validator,
        value: Mapping[str, Any],
    ) -> tuple[str, ...]:
        messages: list[str] = []
        for error in sorted(
            validator.iter_errors(dict(value)),
            key=lambda item: list(item.absolute_path),
        ):
            location = "$"
            if error.absolute_path:
                location += "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error.absolute_path
                )
            messages.append(f"{location}: {error.message}")
        return tuple(messages)

    def _failed_verification(
        self,
        raw_assertion: Mapping[str, Any],
        current: datetime,
    ) -> ProviderVerification:
        assertion = (
            dict(raw_assertion)
            if isinstance(raw_assertion, Mapping)
            else {}
        )
        assertion_digest = _digest(assertion)
        return ProviderVerification(
            provider_class=self.provider.provider_class,
            provider_binding_id=self.provider.provider_binding_id,
            assertion_id="invalid-" + assertion_digest[:16],
            issuer="",
            subject="unknown",
            principal_id=None,
            audiences=(),
            issued_at=current,
            expires_at=current,
            nonce_digest=None,
            claims_digest=assertion_digest,
            identity_assurance=IdentityAssuranceLevel.IAL0,
            authentication_assurance=AuthenticationAssuranceLevel.AAL0,
            federation_assurance=FederationAssuranceLevel.FAL0,
            evidence_maturity=EvidenceMaturity.EA0_CLAIMED,
            runtime_authority=RuntimeAuthority.LOCAL_SIMULATION,
            verified=False,
            evidence_ids=(),
            denial_reasons=(
                IdentityDenialReason.PROVIDER_VERIFICATION_FAILED,
            ),
        )
