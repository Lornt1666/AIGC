from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from src.application.identity_authorization_bridge import (
    IdentityAuthorizationBridge,
    IdentityBoundAuthorization,
)
from src.domain.quests import QuestStateError, WorkSourcePolicyError


class ReviewAuthorizationBridge(IdentityAuthorizationBridge):
    """Authorizes review-gate actions through the existing AIGC kernel."""

    _ALLOWED_ACTIONS = {
        "submit_review": ("quest:review_submit", "review_submission"),
        "judge_review": ("quest:review_judge", "review_judgment"),
    }

    def authorize_review_action(
        self,
        *,
        quest_id: str,
        expected_revision: int,
        identity_receipt_id: str,
        exact_revision: str,
        required_states: Sequence[str],
        action: str,
        evidence_ids: Sequence[str],
        risk_signals: Sequence[str] = (),
        now: datetime | None = None,
    ) -> IdentityBoundAuthorization:
        if action not in self._ALLOWED_ACTIONS:
            raise WorkSourcePolicyError(
                "Unsupported review authorization action"
            )
        scope, purpose = self._ALLOWED_ACTIONS[action]
        current = self._utc(now or datetime.now(timezone.utc))
        identity_receipt = self._require_identity_receipt(
            identity_receipt_id,
            current=current,
        )
        if identity_receipt.exact_revision != exact_revision:
            raise WorkSourcePolicyError(
                "Review identity receipt is not bound to the required revision"
            )

        quest = self.quest_service.get(quest_id)
        if quest.revision != expected_revision:
            raise QuestStateError(
                f"Expected Quest revision {expected_revision}, found {quest.revision}"
            )
        state = str(quest.payload.get("lifecycle_state") or "")
        if state not in set(required_states):
            raise QuestStateError(
                f"Quest {quest_id} cannot authorize {action} from {state}"
            )

        bundle = self._selected_fixture(identity_receipt)
        principals = [dict(item) for item in bundle["principals"]]
        memberships = [dict(item) for item in bundle["memberships"]]
        sessions = [dict(item) for item in bundle["sessions"]]
        policies = [dict(item) for item in bundle["policies"]]
        membership = memberships[0]
        membership["roles"] = sorted(
            set(membership.get("roles") or []) | {"operator"}
        )
        membership["granted_scopes"] = sorted(
            set(membership.get("granted_scopes") or []) | {scope}
        )

        for policy in policies:
            selectors = dict(policy.get("subject_selectors") or {})
            selectors["principal_ids"] = sorted(
                set(selectors.get("principal_ids") or [])
                | {str(identity_receipt.principal_id)}
            )
            selectors["role_ids"] = sorted(
                set(selectors.get("role_ids") or []) | {"operator"}
            )
            policy["subject_selectors"] = selectors
            policy["allowed_roles"] = sorted(
                set(policy.get("allowed_roles") or []) | {"operator"}
            )
            policy["allowed_actions"] = sorted(
                set(policy.get("allowed_actions") or []) | {action}
            )
            policy["granted_scopes"] = sorted(
                set(policy.get("granted_scopes") or []) | {scope}
            )
            policy["permitted_purposes"] = sorted(
                set(policy.get("permitted_purposes") or []) | {purpose}
            )

        pibc_evidence_id = (
            f"AIGC-PIBC-RECEIPT:{identity_receipt.receipt_id}"
        )
        resolved_evidence = list(
            dict.fromkeys(
                [
                    *(str(item) for item in evidence_ids if str(item)),
                    pibc_evidence_id,
                ]
            )
        )
        request: dict[str, Any] = {
            "request_id": (
                f"REQ-REVIEW-{action.upper()}-{quest_id}-{expected_revision}"
            ),
            "exact_revision": exact_revision,
            "principal_id": identity_receipt.principal_id,
            "membership_id": identity_receipt.membership_id,
            "session_id": identity_receipt.session_id,
            "tenant_id": identity_receipt.tenant_id,
            "project_id": identity_receipt.project_id,
            "resource": {
                "resource_id": quest_id,
                "tenant_id": identity_receipt.tenant_id,
                "project_id": identity_receipt.project_id,
                "sensitivity": "internal",
            },
            "action": action,
            "scopes": [scope],
            "purpose": purpose,
            "context": {
                "channel": "pibc-review-evidence-gate",
                "jurisdiction": ["CA-AB"],
                "operator_mode": (
                    identity_receipt.runtime_authority.value.lower()
                ),
                "risk_signals": list(
                    dict.fromkeys(
                        [
                            f"quest-risk:{quest.payload.get('risk_class', 'unassessed')}",
                            *(str(item) for item in risk_signals if str(item)),
                        ]
                    )
                ),
            },
            "assurance": {
                "ial": identity_receipt.identity_assurance.value,
                "aal": identity_receipt.authentication_assurance.value,
                "fal": identity_receipt.federation_assurance.value,
                "evidence_maturity": identity_receipt.evidence_maturity.value,
            },
            "approval_reference_ids": [],
            "evidence_ids": resolved_evidence,
        }
        request["request_digest"] = (
            self.authorization_service.kernel.request_digest(request)
        )
        authorization = self.authorization_service.authorize(
            request=request,
            principals=principals,
            memberships=memberships,
            sessions=sessions,
            policies=policies,
            approvals=bundle["approvals"],
            revocations=bundle["revocations"],
            now=current,
        )
        if (
            authorization.get("result") != "PERMIT"
            or authorization.get("passed") is not True
        ):
            reasons = ", ".join(
                authorization.get("reason_codes") or []
            )
            raise WorkSourcePolicyError(
                "Review authorization denied"
                + (f": {reasons}" if reasons else "")
            )
        receipt = dict(authorization["receipt"])
        if pibc_evidence_id not in set(receipt.get("evidence_ids") or []):
            raise WorkSourcePolicyError(
                "Review authorization receipt is not bound to PIBC evidence"
            )
        if not set(resolved_evidence).issubset(
            set(receipt.get("evidence_ids") or [])
        ):
            raise WorkSourcePolicyError(
                "Review authorization receipt lacks required evidence"
            )
        return IdentityBoundAuthorization(
            identity_receipt_id=identity_receipt.receipt_id,
            authorization_receipt_id=str(authorization["receipt_id"]),
            authorization_request=request,
            authorization_receipt=receipt,
        )
