from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

DENY = "deny"
PERMIT = "permit"
REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class AuthorityDecision:
    passed: bool
    result: str
    reason_codes: tuple[str, ...]
    receipt: dict[str, Any]


class PrincipalAuthorityBindingKernel:
    """Fail-closed local authorization simulator.

    This module resolves a synthetic principal, membership, session and policy
    before evaluating tenant/project/resource authority. It does not perform
    live authentication, use credentials, issue tokens or execute external actions.
    """

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
        now: datetime | None = None,
    ) -> AuthorityDecision:
        current = now or datetime.now(timezone.utc)
        reasons: list[str] = []

        if not isinstance(request, Mapping):
            return self._decision({}, ["INVALID_REQUEST"], None, None, None)

        principal = self._by_id(principals, "principal_id", request.get("principal_id"))
        if principal is None:
            reasons.append("PRINCIPAL_NOT_FOUND")
        elif principal.get("status") != "active":
            reasons.append("PRINCIPAL_NOT_ACTIVE")

        membership = self._by_id(memberships, "membership_id", request.get("membership_id"))
        if membership is None:
            reasons.append("MEMBERSHIP_NOT_FOUND")
        else:
            if principal and membership.get("principal_id") != principal.get("principal_id"):
                reasons.append("MEMBERSHIP_PRINCIPAL_MISMATCH")
            if membership.get("status") != "active":
                reasons.append("MEMBERSHIP_NOT_ACTIVE")
            if membership.get("tenant_id") != request.get("tenant_id"):
                reasons.append("TENANT_MEMBERSHIP_MISMATCH")
            if request.get("project_id") not in set(membership.get("project_ids", [])):
                reasons.append("PROJECT_MEMBERSHIP_MISSING")
            if self._expired(membership.get("expires_at"), current):
                reasons.append("MEMBERSHIP_EXPIRED")

        session = self._by_id(sessions, "session_id", request.get("session_id"))
        if session is None:
            reasons.append("SESSION_NOT_FOUND")
        else:
            if principal and session.get("principal_id") != principal.get("principal_id"):
                reasons.append("SESSION_PRINCIPAL_MISMATCH")
            if membership and session.get("membership_id") != membership.get("membership_id"):
                reasons.append("SESSION_MEMBERSHIP_MISMATCH")
            if session.get("tenant_id") != request.get("tenant_id"):
                reasons.append("SESSION_TENANT_MISMATCH")
            if session.get("active_project_id") != request.get("project_id"):
                reasons.append("SESSION_PROJECT_MISMATCH")
            if session.get("session_state") != "active":
                reasons.append("SESSION_NOT_ACTIVE")
            if self._expired(session.get("idle_expires_at"), current) or self._expired(session.get("absolute_expires_at"), current):
                reasons.append("SESSION_EXPIRED")

        policy = self._by_id(policies, "policy_id", request.get("policy_id"))
        if policy is None:
            reasons.append("POLICY_NOT_FOUND")
        else:
            if policy.get("policy_revision") != request.get("policy_revision"):
                reasons.append("POLICY_REVISION_MISMATCH")
            if policy.get("tenant_id") != request.get("tenant_id"):
                reasons.append("POLICY_TENANT_MISMATCH")
            selectors = set(policy.get("subject_principal_ids", []))
            if principal and selectors and principal.get("principal_id") not in selectors:
                reasons.append("POLICY_SUBJECT_MISMATCH")
            projects = set(policy.get("project_ids", []))
            if projects and request.get("project_id") not in projects:
                reasons.append("POLICY_PROJECT_MISMATCH")
            if request.get("action") not in set(policy.get("allowed_actions", [])):
                reasons.append("ACTION_NOT_ALLOWED")
            if not set(request.get("scopes", [])).issubset(set(policy.get("granted_scopes", []))):
                reasons.append("SCOPE_NOT_GRANTED")
            if request.get("purpose") not in set(policy.get("permitted_purposes", [])):
                reasons.append("PURPOSE_NOT_PERMITTED")
            if not isinstance(request.get("context"), Mapping):
                reasons.append("DECISION_CONTEXT_MISSING")
            self._evaluate_assurance(request, policy, reasons)
            self._evaluate_resource(request, policy, reasons)
            self._evaluate_approval(request, policy, approvals, principal, current, reasons)

        self._evaluate_revocations(request, principal, membership, session, policy, revocations, reasons)

        return self._decision(request, reasons, principal, membership, policy)

    @staticmethod
    def _by_id(records: Sequence[Mapping[str, Any]], field: str, value: Any) -> Mapping[str, Any] | None:
        if not isinstance(value, str) or not value:
            return None
        for record in records:
            if isinstance(record, Mapping) and record.get(field) == value:
                return record
        return None

    @staticmethod
    def _expired(value: Any, now: datetime) -> bool:
        if value is None:
            return False
        if not isinstance(value, str):
            return True
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return True
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc) <= now

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _evaluate_assurance(self, request: Mapping[str, Any], policy: Mapping[str, Any], reasons: list[str]) -> None:
        req = request.get("assurance", {})
        minimum = policy.get("minimum_assurance", {})
        if not isinstance(req, Mapping) or not isinstance(minimum, Mapping):
            reasons.append("ASSURANCE_INVALID")
            return
        for axis in ("ial", "aal", "fal", "evidence_maturity"):
            observed = self._safe_int(req.get(axis))
            needed = self._safe_int(minimum.get(axis))
            if observed is None or needed is None:
                reasons.append("ASSURANCE_INVALID")
            elif observed < needed:
                reasons.append(f"INSUFFICIENT_{axis.upper()}")

    @staticmethod
    def _evaluate_resource(request: Mapping[str, Any], policy: Mapping[str, Any], reasons: list[str]) -> None:
        resource = request.get("resource")
        if not isinstance(resource, Mapping):
            reasons.append("RESOURCE_INVALID")
            return
        if resource.get("tenant_id") != request.get("tenant_id"):
            reasons.append("RESOURCE_TENANT_MISMATCH")
        if resource.get("project_id") != request.get("project_id"):
            reasons.append("RESOURCE_PROJECT_MISMATCH")
        if resource.get("sensitivity") not in set(policy.get("permitted_sensitivity", [])):
            reasons.append("RESOURCE_SENSITIVITY_NOT_PERMITTED")

    def _evaluate_approval(self, request: Mapping[str, Any], policy: Mapping[str, Any], approvals: Sequence[Mapping[str, Any]], principal: Mapping[str, Any] | None, now: datetime, reasons: list[str]) -> None:
        required_class = policy.get("required_approval_class")
        if not required_class:
            return
        approval = self._by_id(approvals, "approval_id", request.get("approval_id"))
        if approval is None:
            reasons.append("REQUIRED_APPROVAL_MISSING")
            return
        if approval.get("status") != "active" or self._expired(approval.get("expires_at"), now):
            reasons.append("APPROVAL_NOT_ACTIVE")
        if approval.get("approval_class") != required_class:
            reasons.append("APPROVAL_CLASS_MISMATCH")
        if approval.get("revision") != request.get("revision"):
            reasons.append("APPROVAL_REVISION_MISMATCH")
        if approval.get("request_digest") != self._request_digest(request):
            reasons.append("APPROVAL_REQUEST_DIGEST_MISMATCH")
        if principal and approval.get("actor_id") == principal.get("principal_id"):
            reasons.append("SELF_APPROVAL_NOT_INDEPENDENT")

    @staticmethod
    def _evaluate_revocations(request: Mapping[str, Any], principal: Mapping[str, Any] | None, membership: Mapping[str, Any] | None, session: Mapping[str, Any] | None, policy: Mapping[str, Any] | None, revocations: Sequence[Mapping[str, Any]], reasons: list[str]) -> None:
        targets = {
            ("principal", principal.get("principal_id") if principal else None),
            ("membership", membership.get("membership_id") if membership else None),
            ("session", session.get("session_id") if session else None),
            ("policy", policy.get("policy_id") if policy else None),
        }
        for record in revocations:
            if not isinstance(record, Mapping) or record.get("status") != "active":
                continue
            if (record.get("target_type"), record.get("target_id")) in targets:
                reasons.append(f"{str(record.get('target_type')).upper()}_REVOKED")

    @staticmethod
    def _request_digest(request: Mapping[str, Any]) -> str:
        data = dict(request)
        data.pop("approval_id", None)
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return sha256(encoded).hexdigest()

    def _decision(self, request: Mapping[str, Any], reasons: Sequence[str], principal: Mapping[str, Any] | None, membership: Mapping[str, Any] | None, policy: Mapping[str, Any] | None) -> AuthorityDecision:
        unique = tuple(sorted(set(reasons)))
        result = DENY if unique else PERMIT
        receipt = {
            "decision_id": str(request.get("decision_id", "AUTHZ-UNKNOWN")),
            "revision": str(request.get("revision", "")),
            "request_digest": self._request_digest(request),
            "principal_id": principal.get("principal_id") if principal else None,
            "membership_id": membership.get("membership_id") if membership else None,
            "session_id": request.get("session_id"),
            "tenant_id": request.get("tenant_id"),
            "project_id": request.get("project_id"),
            "policy_id": policy.get("policy_id") if policy else None,
            "policy_revision": policy.get("policy_revision") if policy else None,
            "result": result,
            "reason_codes": list(unique),
            "evidence_ids": list(request.get("evidence_ids", [])) if isinstance(request.get("evidence_ids", []), list) else [],
            "data_accessed": False,
            "state_changed": False,
            "external_action_performed": False,
        }
        return AuthorityDecision(passed=not unique, result=result, reason_codes=unique, receipt=receipt)
