from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

DENY = "DENY"
PERMIT = "PERMIT"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
NOT_APPLICABLE = "NOT_APPLICABLE"
INDETERMINATE = "INDETERMINATE"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = PROJECT_ROOT / "governance" / "schemas" / "identity"

SCHEMA_FILES = {
    "principal": "principal_record.schema.json",
    "membership": "membership_binding.schema.json",
    "session": "session_binding.schema.json",
    "policy": "access_policy.schema.json",
    "request": "authorization_request.schema.json",
    "receipt": "authorization_decision_receipt.schema.json",
}

ASSURANCE_RANKS = {
    "ial": {"IAL0": 0, "IAL1": 1, "IAL2": 2, "IAL3": 3},
    "aal": {"AAL0": 0, "AAL1": 1, "AAL2": 2, "AAL3": 3},
    "fal": {"FAL0": 0, "FAL1": 1, "FAL2": 2, "FAL3": 3},
    "evidence_maturity": {
        "EA0_CLAIMED": 0,
        "EA1_SCHEMA_VALID": 1,
        "EA2_SEMANTICALLY_TESTED": 2,
        "EA3_CI_EXECUTED": 3,
        "EA4_STAGING_OBSERVED": 4,
        "EA5_PRODUCTION_OBSERVED": 5,
    },
}

Adapter = Callable[[Mapping[str, Any]], "AdapterDecision"]


@dataclass(frozen=True)
class AdapterDecision:
    result: str
    reason_codes: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthorityDecision:
    passed: bool
    result: str
    reason_codes: tuple[str, ...]
    receipt: dict[str, Any]


class IdentityContractValidator:
    """Draft 2020-12 validator for the procured v1.1 identity contracts."""

    def __init__(self, schema_root: Path = SCHEMA_ROOT) -> None:
        self._validators: dict[str, Draft202012Validator] = {}
        for name, filename in SCHEMA_FILES.items():
            schema_path = schema_root / filename
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            self._validators[name] = Draft202012Validator(
                schema,
                format_checker=FormatChecker(),
            )

    def errors(self, contract: str, value: Any) -> tuple[str, ...]:
        validator = self._validators[contract]
        messages: list[str] = []
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path)):
            location = "$"
            if error.absolute_path:
                location += "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error.absolute_path
                )
            messages.append(f"{location}: {error.message}")
        return tuple(messages)

    def is_valid(self, contract: str, value: Any) -> bool:
        return not self.errors(contract, value)


class PrincipalAuthorityBindingKernel:
    """Fail-closed, subject-bound local authorization simulator.

    The kernel resolves synthetic principal, membership, session and policy
    records, validates them against the procured v1.1 contracts, and emits a
    schema-valid minimum-necessary decision receipt. It does not authenticate
    live users, issue tokens, use credentials, persist sessions, grant access,
    deploy, or execute external actions.
    """

    def __init__(self, validator: IdentityContractValidator | None = None) -> None:
        self.validator = validator or IdentityContractValidator()

    def evaluate(
        self,
        *,
        request: Mapping[str, Any],
        principals: Sequence[Mapping[str, Any]],
        memberships: Sequence[Mapping[str, Any]],
        sessions: Sequence[Mapping[str, Any]],
        policies: Sequence[Mapping[str, Any]],
        approvals: Sequence[Mapping[str, Any]] = (),
        revocations: Sequence[Mapping[str, Any]] = (),
        security_privacy_adapter: Adapter | None = None,
        observer_authority_adapter: Adapter | None = None,
        now: datetime | None = None,
    ) -> AuthorityDecision:
        current = self._utc(now or datetime.now(timezone.utc))
        deny_reasons: list[str] = []
        review_reasons: list[str] = []
        obligations: list[str] = []
        approval_obligations: list[dict[str, Any]] = []

        if not isinstance(request, Mapping):
            request = {}
            deny_reasons.append("MALFORMED_REQUEST")
        request_dict = dict(request)

        self._validate_bundle(
            request_dict,
            principals,
            memberships,
            sessions,
            policies,
            deny_reasons,
        )

        computed_digest = self.request_digest(request_dict)
        if request_dict.get("request_digest") != computed_digest:
            deny_reasons.append("REQUEST_DIGEST_MISMATCH")

        principal = self._by_id(principals, "principal_id", request_dict.get("principal_id"))
        if principal is None:
            deny_reasons.append("UNKNOWN_PRINCIPAL")
        else:
            principal_state = str(principal.get("principal_status", "INVALID")).upper()
            if principal_state != "ACTIVE":
                deny_reasons.append("PRINCIPAL_NOT_ACTIVE")
            if principal_state == "REVOKED" or bool(principal.get("revoked", False)):
                deny_reasons.append("PRINCIPAL_REVOKED")
            if self._not_yet_valid(principal.get("valid_from"), current) or self._expired(
                principal.get("expires_at"), current
            ):
                deny_reasons.append("PRINCIPAL_NOT_ACTIVE")

        membership = self._by_id(memberships, "membership_id", request_dict.get("membership_id"))
        if membership is None:
            deny_reasons.append("TENANT_MEMBERSHIP_MISSING")
        else:
            if principal and membership.get("principal_id") != principal.get("principal_id"):
                deny_reasons.extend(
                    ["TENANT_MEMBERSHIP_MISSING", "MEMBERSHIP_PRINCIPAL_MISMATCH"]
                )
            membership_state = str(membership.get("status", "INVALID")).upper()
            if membership_state != "ACTIVE":
                deny_reasons.append("TENANT_MEMBERSHIP_INACTIVE")
            if membership_state == "REVOKED" or membership.get("revoked") is True:
                deny_reasons.append("MEMBERSHIP_REVOKED")
            if membership.get("tenant_id") != request_dict.get("tenant_id"):
                deny_reasons.append("TENANT_MEMBERSHIP_MISSING")
            if request_dict.get("project_id") not in self._string_set(
                membership.get("project_ids")
            ):
                deny_reasons.append("PROJECT_MEMBERSHIP_MISSING")
            if self._not_yet_valid(membership.get("valid_from"), current) or self._expired(
                membership.get("expires_at"), current
            ):
                deny_reasons.append("TENANT_MEMBERSHIP_INACTIVE")

        session = self._by_id(sessions, "session_id", request_dict.get("session_id"))
        if session is None:
            deny_reasons.append("SESSION_NOT_ACTIVE")
        else:
            if principal and session.get("principal_id") != principal.get("principal_id"):
                deny_reasons.append("SESSION_PRINCIPAL_MISMATCH")
            if membership and session.get("membership_id") != membership.get("membership_id"):
                deny_reasons.append("SESSION_MEMBERSHIP_MISMATCH")
            if session.get("tenant_id") != request_dict.get("tenant_id"):
                deny_reasons.append("SESSION_TENANT_MISMATCH")
            if session.get("active_project_id") != request_dict.get("project_id"):
                deny_reasons.append("SESSION_PROJECT_MISMATCH")

            state = str(session.get("session_state", "INVALID")).upper()
            if state == "STEP_UP_REQUIRED":
                review_reasons.append("SESSION_NOT_ACTIVE")
                obligations.append("step_up_authentication")
            elif state != "ACTIVE":
                deny_reasons.append("SESSION_NOT_ACTIVE")

            if self._expired(session.get("idle_expires_at"), current) or self._expired(
                session.get("absolute_expires_at"), current
            ):
                deny_reasons.append("SESSION_NOT_ACTIVE")

        policy = self._resolve_policy(policies, membership)
        if policy is None:
            deny_reasons.append("POLICY_NOT_APPLICABLE")
        else:
            self._evaluate_policy(
                request_dict,
                principal,
                membership,
                session,
                policy,
                approvals,
                current,
                deny_reasons,
                review_reasons,
                obligations,
                approval_obligations,
            )

        self._evaluate_revocations(
            principal,
            membership,
            session,
            policy,
            approvals,
            revocations,
            deny_reasons,
        )
        self._evaluate_adapters(
            request_dict,
            security_privacy_adapter,
            observer_authority_adapter,
            deny_reasons,
            review_reasons,
            obligations,
        )

        return self._decision(
            request=request_dict,
            current=current,
            computed_digest=computed_digest,
            deny_reasons=deny_reasons,
            review_reasons=review_reasons,
            principal=principal,
            membership=membership,
            session=session,
            policy=policy,
            obligations=obligations,
            approval_obligations=approval_obligations,
        )

    def _validate_bundle(
        self,
        request: Mapping[str, Any],
        principals: Sequence[Mapping[str, Any]],
        memberships: Sequence[Mapping[str, Any]],
        sessions: Sequence[Mapping[str, Any]],
        policies: Sequence[Mapping[str, Any]],
        reasons: list[str],
    ) -> None:
        if self.validator.errors("request", request):
            reasons.append("MALFORMED_REQUEST")
        for contract, records in (
            ("principal", principals),
            ("membership", memberships),
            ("session", sessions),
            ("policy", policies),
        ):
            if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
                reasons.append("MALFORMED_REQUEST")
                continue
            for record in records:
                if self.validator.errors(contract, record):
                    reasons.append("MALFORMED_REQUEST")

    def _evaluate_policy(
        self,
        request: Mapping[str, Any],
        principal: Mapping[str, Any] | None,
        membership: Mapping[str, Any] | None,
        session: Mapping[str, Any] | None,
        policy: Mapping[str, Any],
        approvals: Sequence[Mapping[str, Any]],
        current: datetime,
        deny_reasons: list[str],
        review_reasons: list[str],
        obligations: list[str],
        approval_obligations: list[dict[str, Any]],
    ) -> None:
        if policy.get("revoked") is True:
            deny_reasons.append("POLICY_REVOKED")

        if membership and policy.get("policy_revision") != membership.get("policy_revision"):
            deny_reasons.append("POLICY_REVISION_MISMATCH")
        if policy.get("tenant_id") != request.get("tenant_id"):
            deny_reasons.append("POLICY_TENANT_MISMATCH")

        project_selectors = self._string_set(policy.get("project_selectors"))
        if project_selectors and request.get("project_id") not in project_selectors:
            deny_reasons.append("POLICY_PROJECT_MISMATCH")

        selectors = policy.get("subject_selectors")
        if not isinstance(selectors, Mapping):
            deny_reasons.append("MALFORMED_REQUEST")
        else:
            principal_ids = self._string_set(selectors.get("principal_ids"))
            role_ids = self._string_set(selectors.get("role_ids"))
            membership_roles = self._string_set(
                membership.get("roles") if membership else ()
            )
            principal_match = bool(
                principal and principal.get("principal_id") in principal_ids
            )
            role_match = bool(role_ids & membership_roles)
            if not principal_match and not role_match:
                deny_reasons.append("POLICY_SUBJECT_MISMATCH")

        membership_roles = self._string_set(membership.get("roles") if membership else ())
        allowed_roles = self._string_set(policy.get("allowed_roles"))
        if allowed_roles and not (membership_roles & allowed_roles):
            deny_reasons.append("POLICY_SUBJECT_MISMATCH")

        if request.get("action") not in self._string_set(policy.get("allowed_actions")):
            deny_reasons.append("ACTION_NOT_ALLOWED")
        if not self._string_set(request.get("scopes")).issubset(
            self._string_set(policy.get("granted_scopes"))
        ):
            deny_reasons.append("SCOPE_NOT_GRANTED")
        if request.get("purpose") not in self._string_set(
            policy.get("permitted_purposes")
        ):
            deny_reasons.append("PURPOSE_NOT_ALLOWED")

        context = request.get("context")
        if not isinstance(context, Mapping) or not {
            "channel",
            "jurisdiction",
            "operator_mode",
        }.issubset(context):
            deny_reasons.append("CONTEXT_NOT_ALLOWED")

        resource = request.get("resource")
        if not isinstance(resource, Mapping):
            deny_reasons.append("MALFORMED_REQUEST")
        else:
            if resource.get("tenant_id") != request.get("tenant_id"):
                deny_reasons.append("RESOURCE_TENANT_MISMATCH")
            if resource.get("project_id") != request.get("project_id"):
                deny_reasons.append("RESOURCE_PROJECT_MISMATCH")
            if resource.get("sensitivity") not in self._string_set(
                policy.get("permitted_sensitivity")
            ):
                deny_reasons.append("RESOURCE_SENSITIVITY_NOT_PERMITTED")

        self._evaluate_assurance(
            request,
            principal,
            session,
            policy,
            deny_reasons,
        )
        self._evaluate_approvals(
            request,
            principal,
            policy,
            approvals,
            current,
            deny_reasons,
            review_reasons,
            approval_obligations,
        )
        obligations.extend(
            item
            for item in policy.get("obligations", [])
            if isinstance(item, str) and item
        )

    def _evaluate_assurance(
        self,
        request: Mapping[str, Any],
        principal: Mapping[str, Any] | None,
        session: Mapping[str, Any] | None,
        policy: Mapping[str, Any],
        reasons: list[str],
    ) -> None:
        requested = request.get("assurance")
        minimum = policy.get("minimum_assurance")
        if not isinstance(requested, Mapping) or not isinstance(minimum, Mapping):
            reasons.append("MALFORMED_REQUEST")
            return

        observed = {
            "ial": self._least_assurance(
                "ial",
                requested.get("ial"),
                principal.get("identity_assurance") if principal else None,
            ),
            "aal": self._least_assurance(
                "aal",
                requested.get("aal"),
                session.get("authentication_assurance") if session else None,
            ),
            "fal": self._least_assurance(
                "fal",
                requested.get("fal"),
                principal.get("federation_assurance") if principal else None,
            ),
            "evidence_maturity": requested.get("evidence_maturity"),
        }

        for axis, reason in (
            ("ial", "INSUFFICIENT_IAL"),
            ("aal", "INSUFFICIENT_AAL"),
            ("fal", "INSUFFICIENT_FAL"),
            ("evidence_maturity", "INSUFFICIENT_EVIDENCE_MATURITY"),
        ):
            observed_rank = ASSURANCE_RANKS[axis].get(observed.get(axis), -1)
            minimum_rank = ASSURANCE_RANKS[axis].get(minimum.get(axis), 99)
            if observed_rank < minimum_rank:
                reasons.append(reason)

    def _evaluate_approvals(
        self,
        request: Mapping[str, Any],
        principal: Mapping[str, Any] | None,
        policy: Mapping[str, Any],
        approvals: Sequence[Mapping[str, Any]],
        current: datetime,
        deny_reasons: list[str],
        review_reasons: list[str],
        approval_obligations: list[dict[str, Any]],
    ) -> None:
        rules = policy.get("approval_rules", [])
        if not isinstance(rules, list):
            deny_reasons.append("MALFORMED_REQUEST")
            return

        requested_ids = self._string_set(request.get("approval_reference_ids"))
        for rule in rules:
            if not isinstance(rule, Mapping):
                deny_reasons.append("MALFORMED_REQUEST")
                continue
            if not bool(rule.get("required", False)):
                continue

            obligation = {
                "approval_class": str(rule.get("approval_class", "")),
                "independent": bool(rule.get("independent", False)),
                "exact_revision": str(request.get("exact_revision", "")),
                "request_digest": str(request.get("request_digest", "")),
            }
            approval_obligations.append(obligation)

            candidate = next(
                (
                    item
                    for item in approvals
                    if isinstance(item, Mapping)
                    and item.get("approval_id") in requested_ids
                    and item.get("approval_class") == rule.get("approval_class")
                ),
                None,
            )
            if candidate is None:
                any_referenced = next(
                    (
                        item
                        for item in approvals
                        if isinstance(item, Mapping)
                        and item.get("approval_id") in requested_ids
                    ),
                    None,
                )
                if any_referenced is not None:
                    deny_reasons.append("APPROVAL_CLASS_MISMATCH")
                else:
                    review_reasons.append("APPROVAL_MISSING")
                continue

            status = str(candidate.get("status", "")).upper()
            if status != "ACTIVE" or self._expired(candidate.get("expires_at"), current):
                deny_reasons.append("APPROVAL_EXPIRED")
            if candidate.get("revision") != request.get("exact_revision"):
                deny_reasons.append("APPROVAL_REVISION_MISMATCH")
            if candidate.get("request_digest") != request.get("request_digest"):
                deny_reasons.append("APPROVAL_REQUEST_DIGEST_MISMATCH")
            if (
                rule.get("independent") is True
                and principal
                and candidate.get("actor_id") == principal.get("principal_id")
            ):
                deny_reasons.append("SELF_APPROVAL_NOT_INDEPENDENT")

    @staticmethod
    def _evaluate_revocations(
        principal: Mapping[str, Any] | None,
        membership: Mapping[str, Any] | None,
        session: Mapping[str, Any] | None,
        policy: Mapping[str, Any] | None,
        approvals: Sequence[Mapping[str, Any]],
        revocations: Sequence[Mapping[str, Any]],
        reasons: list[str],
    ) -> None:
        approval_ids = {
            item.get("approval_id")
            for item in approvals
            if isinstance(item, Mapping) and item.get("approval_id")
        }
        targets = {
            ("principal", principal.get("principal_id") if principal else None):
                "PRINCIPAL_REVOKED",
            ("membership", membership.get("membership_id") if membership else None):
                "MEMBERSHIP_REVOKED",
            ("session", session.get("session_id") if session else None):
                "SESSION_REVOKED",
            ("policy", policy.get("policy_id") if policy else None):
                "POLICY_REVOKED",
        }
        for record in revocations:
            if not isinstance(record, Mapping):
                continue
            if str(record.get("status", "")).upper() != "ACTIVE":
                continue
            key = (
                str(record.get("target_type", "")).lower(),
                record.get("target_id"),
            )
            if key in targets:
                reasons.append(targets[key])
            elif key[0] == "approval" and key[1] in approval_ids:
                reasons.append("APPROVAL_REVOKED")

    def _evaluate_adapters(
        self,
        request: Mapping[str, Any],
        security_privacy_adapter: Adapter | None,
        observer_authority_adapter: Adapter | None,
        deny_reasons: list[str],
        review_reasons: list[str],
        obligations: list[str],
    ) -> None:
        context = request.get("context")
        operator_mode = (
            str(context.get("operator_mode", ""))
            if isinstance(context, Mapping)
            else ""
        )
        purpose = str(request.get("purpose", ""))

        if operator_mode in {"staging", "production"}:
            self._apply_adapter(
                security_privacy_adapter,
                request,
                "SECURITY_PRIVACY_REVIEW_REQUIRED",
                deny_reasons,
                review_reasons,
                obligations,
            )
        if purpose == "observer_access":
            self._apply_adapter(
                observer_authority_adapter,
                request,
                "OBSERVER_AUTHORITY_REQUIRED",
                deny_reasons,
                review_reasons,
                obligations,
            )

    @staticmethod
    def _apply_adapter(
        adapter: Adapter | None,
        request: Mapping[str, Any],
        missing_reason: str,
        deny_reasons: list[str],
        review_reasons: list[str],
        obligations: list[str],
    ) -> None:
        if adapter is None:
            review_reasons.append(missing_reason)
            return
        decision = adapter(request)
        obligations.extend(decision.obligations)
        if decision.result == DENY:
            deny_reasons.extend(decision.reason_codes or (missing_reason,))
        elif decision.result == REVIEW_REQUIRED:
            review_reasons.extend(decision.reason_codes or (missing_reason,))
        elif decision.result not in {PERMIT, NOT_APPLICABLE}:
            deny_reasons.append("INDETERMINATE_AUTHORITY")

    @staticmethod
    def request_digest(request: Mapping[str, Any]) -> str:
        canonical = dict(request)
        canonical.pop("request_digest", None)
        encoded = json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def _decision(
        self,
        *,
        request: Mapping[str, Any],
        current: datetime,
        computed_digest: str,
        deny_reasons: Sequence[str],
        review_reasons: Sequence[str],
        principal: Mapping[str, Any] | None,
        membership: Mapping[str, Any] | None,
        session: Mapping[str, Any] | None,
        policy: Mapping[str, Any] | None,
        obligations: Sequence[str],
        approval_obligations: Sequence[Mapping[str, Any]],
    ) -> AuthorityDecision:
        deny = tuple(sorted(set(deny_reasons)))
        review = tuple(sorted(set(review_reasons)))
        if deny:
            result = DENY
            reasons = deny
        elif review:
            result = REVIEW_REQUIRED
            reasons = review
        else:
            result = PERMIT
            reasons = ()

        request_id = self._safe_identifier(request.get("request_id"), "REQUEST-UNKNOWN")
        exact_revision = self._safe_revision(request.get("exact_revision"))
        evidence_ids = self._evidence_ids(
            request,
            principal,
            membership,
        )
        receipt = {
            "decision_id": f"AUTHZ-{request_id}",
            "request_id": request_id,
            "request_digest": computed_digest,
            "exact_revision": exact_revision,
            "principal_id": self._safe_identifier(
                principal.get("principal_id") if principal else request.get("principal_id"),
                "PRINCIPAL-UNKNOWN",
            ),
            "membership_id": self._safe_identifier(
                membership.get("membership_id") if membership else request.get("membership_id"),
                "MEMBERSHIP-UNKNOWN",
            ),
            "session_id": self._safe_identifier(
                session.get("session_id") if session else request.get("session_id"),
                "SESSION-UNKNOWN",
            ),
            "tenant_id": self._safe_identifier(
                request.get("tenant_id"),
                "TENANT-UNKNOWN",
            ),
            "project_id": self._safe_identifier(
                request.get("project_id"),
                "PROJECT-UNKNOWN",
            ),
            "policy_id": self._safe_identifier(
                policy.get("policy_id") if policy else None,
                "POLICY-UNKNOWN",
            ),
            "policy_revision": self._safe_revision(
                policy.get("policy_revision") if policy else None
            ),
            "result": result,
            "reason_codes": list(reasons),
            "obligations": sorted(set(item for item in obligations if item)),
            "approval_obligations": [dict(item) for item in approval_obligations],
            "evidence_ids": evidence_ids,
            "data_accessed": False,
            "state_changed": False,
            "external_action_performed": False,
            "evaluated_at": current.isoformat().replace("+00:00", "Z"),
        }
        receipt_errors = self.validator.errors("receipt", receipt)
        if receipt_errors:
            raise RuntimeError(
                "Authorization decision receipt violated its contract: "
                + "; ".join(receipt_errors[:5])
            )
        return AuthorityDecision(
            passed=result == PERMIT,
            result=result,
            reason_codes=reasons,
            receipt=receipt,
        )

    @staticmethod
    def _resolve_policy(
        policies: Sequence[Mapping[str, Any]],
        membership: Mapping[str, Any] | None,
    ) -> Mapping[str, Any] | None:
        candidates = [item for item in policies if isinstance(item, Mapping)]
        if not candidates:
            return None
        required_revision = membership.get("policy_revision") if membership else None
        for policy in candidates:
            if policy.get("policy_revision") == required_revision:
                return policy
        return candidates[0]

    @staticmethod
    def _by_id(
        records: Sequence[Mapping[str, Any]],
        field: str,
        value: Any,
    ) -> Mapping[str, Any] | None:
        if not isinstance(value, str) or not value:
            return None
        for record in records:
            if isinstance(record, Mapping) and record.get(field) == value:
                return record
        return None

    @staticmethod
    def _least_assurance(axis: str, first: Any, second: Any) -> Any:
        ranks = ASSURANCE_RANKS[axis]
        if first not in ranks or second not in ranks:
            return None
        return first if ranks[first] <= ranks[second] else second

    @staticmethod
    def _string_set(value: Any) -> set[str]:
        if not isinstance(value, (list, tuple, set)):
            return set()
        return {item for item in value if isinstance(item, str) and item}

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return PrincipalAuthorityBindingKernel._utc(parsed)

    @classmethod
    def _expired(cls, value: Any, now: datetime) -> bool:
        if value is None:
            return False
        parsed = cls._parse_time(value)
        return parsed is None or parsed <= now

    @classmethod
    def _not_yet_valid(cls, value: Any, now: datetime) -> bool:
        parsed = cls._parse_time(value)
        return parsed is None or parsed > now

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _safe_identifier(value: Any, fallback: str) -> str:
        return value if isinstance(value, str) and value else fallback

    @staticmethod
    def _safe_revision(value: Any) -> str:
        if (
            isinstance(value, str)
            and len(value) == 40
            and all(character in "0123456789abcdef" for character in value)
        ):
            return value
        return "0" * 40

    @staticmethod
    def _evidence_ids(
        request: Mapping[str, Any],
        principal: Mapping[str, Any] | None,
        membership: Mapping[str, Any] | None,
    ) -> list[str]:
        values: list[str] = []
        for source in (
            request.get("evidence_ids"),
            principal.get("evidence_ids") if principal else None,
            membership.get("evidence_ids") if membership else None,
        ):
            if isinstance(source, list):
                values.extend(item for item in source if isinstance(item, str) and item)
        unique = sorted(set(values))
        return unique or ["EVIDENCE-NOT-PROVIDED"]
