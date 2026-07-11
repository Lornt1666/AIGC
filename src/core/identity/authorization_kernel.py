from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

ALLOWED_RESULTS = {"permit", "deny"}


@dataclass(frozen=True)
class AuthorizationDecision:
    passed: bool
    result: str
    reason_codes: tuple[str, ...]
    actor_reference: dict[str, Any]
    approval_reference: dict[str, Any] | None
    receipt: dict[str, Any]


class IdentityAuthorizationKernel:
    """Deterministic deny-by-default authorization kernel.

    This local kernel validates declared actor, tenant, project, session, expiry,
    revocation, assurance, scope, and resource-sensitivity attributes. It does
    not authenticate live users, contact an identity provider, use credentials,
    grant repository access, or perform external actions.
    """

    def evaluate(
        self,
        *,
        request: dict[str, Any],
        policy: dict[str, Any],
        now: datetime | None = None,
    ) -> AuthorizationDecision:
        current = now or datetime.now(timezone.utc)
        reasons: list[str] = []

        actor = request.get("actor_reference")
        if not isinstance(actor, dict):
            actor = {}
            reasons.append("MISSING_ACTOR_REFERENCE")

        required_actor_fields = {"actor_id", "actor_type", "display_name", "authority_source"}
        if required_actor_fields - actor.keys():
            reasons.append("INVALID_ACTOR_REFERENCE")

        tenant_id = request.get("tenant_id")
        project_id = request.get("project_id")
        resource_tenant = request.get("resource", {}).get("tenant_id")
        resource_project = request.get("resource", {}).get("project_id")
        if not tenant_id or tenant_id != resource_tenant:
            reasons.append("TENANT_ISOLATION_VIOLATION")
        if not project_id or project_id != resource_project:
            reasons.append("PROJECT_SCOPE_VIOLATION")

        session = request.get("session")
        if not isinstance(session, dict):
            session = {}
            reasons.append("MISSING_SESSION")
        if session.get("revoked") is True:
            reasons.append("SESSION_REVOKED")

        expires_at = self._parse_time(session.get("expires_at"))
        if expires_at is None:
            reasons.append("INVALID_SESSION_EXPIRY")
        elif expires_at <= current:
            reasons.append("SESSION_EXPIRED")

        if request.get("revocation_id") in set(policy.get("revoked_ids", [])):
            reasons.append("AUTHORITY_REVOKED")

        requested_action = request.get("action")
        allowed_actions = set(policy.get("allowed_actions", []))
        if requested_action not in allowed_actions:
            reasons.append("ACTION_NOT_ALLOWED")

        requested_scopes = set(request.get("scopes", []))
        granted_scopes = set(policy.get("granted_scopes", []))
        if not requested_scopes or not requested_scopes.issubset(granted_scopes):
            reasons.append("SCOPE_NOT_GRANTED")

        assurance = int(request.get("assurance_level", -1))
        minimum_assurance = int(policy.get("minimum_assurance_level", 999))
        if assurance < minimum_assurance:
            reasons.append("INSUFFICIENT_ASSURANCE")

        sensitivity = request.get("resource", {}).get("sensitivity")
        permitted_sensitivity = set(policy.get("permitted_sensitivity", []))
        if sensitivity not in permitted_sensitivity:
            reasons.append("RESOURCE_SENSITIVITY_NOT_PERMITTED")

        approval_required = bool(policy.get("human_approval_required", False))
        approval = request.get("approval_reference")
        if approval_required:
            if not isinstance(approval, dict):
                reasons.append("MISSING_REQUIRED_APPROVAL")
                approval = None
            else:
                required_approval_fields = {"approval_id", "actor_id", "approval_class", "revision", "status"}
                if required_approval_fields - approval.keys() or approval.get("status") != "active":
                    reasons.append("INVALID_REQUIRED_APPROVAL")
                if approval.get("actor_id") == actor.get("actor_id"):
                    reasons.append("SELF_APPROVAL_NOT_INDEPENDENT")
        else:
            approval = approval if isinstance(approval, dict) else None

        result = "deny" if reasons else "permit"
        revision = str(request.get("revision", ""))
        if len(revision) < 7:
            reasons.append("INVALID_REVISION")
            result = "deny"

        receipt = {
            "contract_version": "1.0.0",
            "contract_type": "gate_receipt",
            "payload": {
                "receipt_id": str(request.get("decision_id", "AUTHZ-DECISION")),
                "gate_id": "identity_scope_authorization",
                "revision": revision,
                "result": result,
                "reason_codes": tuple(sorted(set(reasons))),
                "evidence_ids": list(request.get("evidence_ids", [])),
            },
        }
        return AuthorizationDecision(
            passed=not reasons,
            result=result,
            reason_codes=tuple(sorted(set(reasons))),
            actor_reference=actor,
            approval_reference=approval,
            receipt=receipt,
        )

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
