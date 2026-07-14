from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from src.application.authorization_service import AuthorizationApplicationService
from src.application.quests import QuestApplicationService
from src.domain.identity import (
    IdentityDecision,
    IdentityEvidenceReceipt,
    IdentityEvidenceReceiptRepository,
)
from src.domain.quests import QuestLifecycleState, QuestStateError, WorkSourcePolicyError


@dataclass(frozen=True)
class IdentityBoundAuthorization:
    identity_receipt_id: str
    authorization_receipt_id: str
    authorization_request: dict[str, Any]
    authorization_receipt: dict[str, Any]


class IdentityAuthorizationBridge:
    """Binds a persisted PIBC receipt to the existing authorization kernel.

    The bridge never grants authority from caller input. It retrieves the
    immutable identity receipt, reloads repository-owned local authority records,
    builds the existing authorization request, and invokes the canonical
    AuthorizationApplicationService. It performs no Quest state transition.
    """

    def __init__(
        self,
        *,
        identity_receipt_repository: IdentityEvidenceReceiptRepository,
        authorization_service: AuthorizationApplicationService,
        quest_service: QuestApplicationService,
        identity_fixture_path: str | Path,
    ) -> None:
        self.identity_receipt_repository = identity_receipt_repository
        self.authorization_service = authorization_service
        self.quest_service = quest_service
        self.identity_fixture_path = Path(identity_fixture_path)

    def authorize_work_acceptance(
        self,
        *,
        quest_id: str,
        expected_revision: int,
        identity_receipt_id: str,
        now: datetime | None = None,
    ) -> IdentityBoundAuthorization:
        current = self._utc(now or datetime.now(timezone.utc))
        identity_receipt = self._require_identity_receipt(
            identity_receipt_id,
            current=current,
        )

        quest_record = self.quest_service.get(quest_id)
        if (
            quest_record.payload.get("lifecycle_state")
            != QuestLifecycleState.APPROVAL_REQUIRED.value
        ):
            raise QuestStateError(
                f"Quest {quest_id} must be APPROVAL_REQUIRED before authorization"
            )
        if quest_record.revision != expected_revision:
            raise QuestStateError(
                f"Expected Quest revision {expected_revision}, found {quest_record.revision}"
            )

        approval = dict(quest_record.payload.get("approval_request") or {})
        if approval.get("status") != "PENDING":
            raise QuestStateError("Work-approval request is not pending")
        if approval.get("quest_revision") != expected_revision:
            raise QuestStateError(
                "Work-approval request is not bound to the current Quest revision"
            )
        approval_revision = str(approval.get("exact_revision") or "")
        if identity_receipt.exact_revision != approval_revision:
            raise WorkSourcePolicyError(
                "Identity receipt is not bound to the Quest approval revision"
            )

        fixture = self._selected_fixture(identity_receipt)
        bundle = self.quest_service.build_work_acceptance_authorization_bundle(
            quest_id,
            fixture,
        )
        request = dict(bundle["request"])
        self._require_request_identity_binding(request, identity_receipt)

        request["assurance"] = {
            "ial": identity_receipt.identity_assurance.value,
            "aal": identity_receipt.authentication_assurance.value,
            "fal": identity_receipt.federation_assurance.value,
            "evidence_maturity": identity_receipt.evidence_maturity.value,
        }
        context = dict(request.get("context") or {})
        context["channel"] = "pibc-identity-bound-quest-board"
        context["operator_mode"] = identity_receipt.runtime_authority.value.lower()
        request["context"] = context
        evidence_ids = list(request.get("evidence_ids") or [])
        pibc_evidence_id = f"AIGC-PIBC-RECEIPT:{identity_receipt.receipt_id}"
        if pibc_evidence_id not in evidence_ids:
            evidence_ids.append(pibc_evidence_id)
        request["evidence_ids"] = evidence_ids
        request["request_digest"] = (
            self.authorization_service.kernel.request_digest(request)
        )
        bundle["request"] = request

        authorization = self.authorization_service.authorize(
            request=request,
            principals=bundle["principals"],
            memberships=bundle["memberships"],
            sessions=bundle["sessions"],
            policies=bundle["policies"],
            approvals=bundle["approvals"],
            revocations=bundle["revocations"],
            now=current,
        )
        if authorization.get("result") != "PERMIT" or authorization.get("passed") is not True:
            reasons = ", ".join(authorization.get("reason_codes") or [])
            raise WorkSourcePolicyError(
                "Identity-bound authorization denied"
                + (f": {reasons}" if reasons else "")
            )

        receipt = dict(authorization["receipt"])
        if pibc_evidence_id not in set(receipt.get("evidence_ids") or []):
            raise WorkSourcePolicyError(
                "Authorization receipt is not bound to the PIBC receipt"
            )
        return IdentityBoundAuthorization(
            identity_receipt_id=identity_receipt.receipt_id,
            authorization_receipt_id=str(authorization["receipt_id"]),
            authorization_request=request,
            authorization_receipt=receipt,
        )

    def verify_existing_binding(
        self,
        *,
        authorization_receipt_id: str,
        identity_receipt_id: str,
    ) -> dict[str, Any]:
        receipt = self.authorization_service.get_receipt(authorization_receipt_id)
        if receipt is None:
            raise WorkSourcePolicyError("Authorization receipt not found")
        expected = f"AIGC-PIBC-RECEIPT:{identity_receipt_id}"
        if expected not in set(receipt.get("evidence_ids") or []):
            raise WorkSourcePolicyError(
                "Authorization receipt is not bound to the supplied PIBC receipt"
            )
        if receipt.get("result") != "PERMIT":
            raise WorkSourcePolicyError("Authorization receipt is not a PERMIT")
        return receipt

    def _require_identity_receipt(
        self,
        receipt_id: str,
        *,
        current: datetime,
    ) -> IdentityEvidenceReceipt:
        receipt = self.identity_receipt_repository.get(receipt_id)
        if receipt is None:
            raise WorkSourcePolicyError("Identity evidence receipt not found")
        if receipt.result is not IdentityDecision.PERMIT:
            raise WorkSourcePolicyError("Identity evidence receipt is not a PERMIT")
        required_values = (
            receipt.principal_id,
            receipt.membership_id,
            receipt.session_id,
            receipt.tenant_id,
            receipt.project_id,
            receipt.identity_assurance,
            receipt.authentication_assurance,
            receipt.federation_assurance,
            receipt.evidence_maturity,
            receipt.runtime_authority,
        )
        if any(value is None for value in required_values):
            raise WorkSourcePolicyError(
                "Identity evidence receipt lacks required normalized bindings"
            )
        if receipt.expires_at is None or self._utc(receipt.expires_at) <= current:
            raise WorkSourcePolicyError("Identity evidence receipt has expired")
        return receipt

    def _selected_fixture(
        self,
        receipt: IdentityEvidenceReceipt,
    ) -> dict[str, Any]:
        fixture = json.loads(
            self.identity_fixture_path.read_text(encoding="utf-8")
        )
        principal = self._one(
            fixture.get("principals") or [],
            "principal_id",
            receipt.principal_id,
            "principal",
        )
        membership = self._one(
            fixture.get("memberships") or [],
            "membership_id",
            receipt.membership_id,
            "membership",
        )
        session = self._one(
            fixture.get("sessions") or [],
            "session_id",
            receipt.session_id,
            "session",
        )

        if membership.get("principal_id") != receipt.principal_id:
            raise WorkSourcePolicyError("Membership principal does not match PIBC receipt")
        if membership.get("tenant_id") != receipt.tenant_id:
            raise WorkSourcePolicyError("Membership tenant does not match PIBC receipt")
        if receipt.project_id not in set(membership.get("project_ids") or []):
            raise WorkSourcePolicyError("Membership lacks the PIBC project")
        if session.get("principal_id") != receipt.principal_id:
            raise WorkSourcePolicyError("Session principal does not match PIBC receipt")
        if session.get("membership_id") != receipt.membership_id:
            raise WorkSourcePolicyError("Session membership does not match PIBC receipt")
        if session.get("tenant_id") != receipt.tenant_id:
            raise WorkSourcePolicyError("Session tenant does not match PIBC receipt")
        if session.get("active_project_id") != receipt.project_id:
            raise WorkSourcePolicyError("Session project does not match PIBC receipt")

        membership_roles = {
            str(value) for value in membership.get("roles") or [] if str(value)
        }
        policies: list[dict[str, Any]] = []
        for value in fixture.get("policies") or []:
            policy = dict(value)
            if policy.get("tenant_id") != receipt.tenant_id:
                continue
            selectors = dict(policy.get("subject_selectors") or {})
            principal_match = receipt.principal_id in set(
                selectors.get("principal_ids") or []
            )
            role_match = bool(
                membership_roles & set(selectors.get("role_ids") or [])
            )
            if principal_match or role_match:
                policies.append(policy)
        if not policies:
            raise WorkSourcePolicyError(
                "No trusted policy applies to the PIBC identity"
            )

        return {
            "principals": [principal],
            "memberships": [membership],
            "sessions": [session],
            "policies": policies,
            "approvals": [dict(item) for item in fixture.get("approvals") or []],
            "revocations": [dict(item) for item in fixture.get("revocations") or []],
            "request": {},
        }

    @staticmethod
    def _one(
        records: list[Mapping[str, Any]],
        key: str,
        expected: object,
        label: str,
    ) -> dict[str, Any]:
        found = [dict(item) for item in records if item.get(key) == expected]
        if len(found) != 1:
            raise WorkSourcePolicyError(
                f"Trusted {label} binding could not be resolved uniquely"
            )
        return found[0]

    @staticmethod
    def _require_request_identity_binding(
        request: Mapping[str, Any],
        receipt: IdentityEvidenceReceipt,
    ) -> None:
        expected = {
            "principal_id": receipt.principal_id,
            "membership_id": receipt.membership_id,
            "session_id": receipt.session_id,
            "tenant_id": receipt.tenant_id,
            "project_id": receipt.project_id,
        }
        for key, value in expected.items():
            if request.get(key) != value:
                raise WorkSourcePolicyError(
                    f"Authorization request {key} does not match PIBC receipt"
                )
        resource = request.get("resource")
        if not isinstance(resource, Mapping):
            raise WorkSourcePolicyError("Authorization request lacks resource binding")
        if resource.get("tenant_id") != receipt.tenant_id:
            raise WorkSourcePolicyError("Resource tenant does not match PIBC receipt")
        if resource.get("project_id") != receipt.project_id:
            raise WorkSourcePolicyError("Resource project does not match PIBC receipt")

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
