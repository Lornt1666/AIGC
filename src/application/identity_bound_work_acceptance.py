from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.application.identity_authorization_bridge import (
    IdentityAuthorizationBridge,
)
from src.application.quests import QuestApplicationService
from src.domain.quests import QuestConflict, QuestLifecycleState, WorkSourcePolicyError
from src.domain.repositories import StoredRecord


@dataclass(frozen=True)
class IdentityBoundWorkAcceptanceResult:
    quest: StoredRecord
    identity_receipt_id: str
    authorization_receipt_id: str
    authorization_request_digest: str


class IdentityBoundWorkAcceptanceHandler:
    """Coordinates PIBC identity, authorization, and the canonical Quest transition."""

    def __init__(
        self,
        *,
        identity_authorization_bridge: IdentityAuthorizationBridge,
        quest_service: QuestApplicationService,
    ) -> None:
        self.identity_authorization_bridge = identity_authorization_bridge
        self.quest_service = quest_service

    def execute(
        self,
        *,
        quest_id: str,
        expected_revision: int,
        identity_receipt_id: str,
        operator_role: str,
        reason: str | None = None,
    ) -> IdentityBoundWorkAcceptanceResult:
        record = self.quest_service.get(quest_id)
        normalized_reason = str(reason).strip() if reason else None

        if (
            record.payload.get("lifecycle_state")
            == QuestLifecycleState.WORK_ACCEPTED.value
        ):
            acceptance = dict(record.payload.get("work_acceptance") or {})
            if record.revision != expected_revision + 1:
                raise QuestConflict(
                    "Quest already contains a different work-acceptance revision"
                )
            if acceptance.get("reason") != normalized_reason:
                raise QuestConflict(
                    "Quest already contains a different work-acceptance reason"
                )
            authorization_receipt_id = str(
                acceptance.get("authorization_receipt_id") or ""
            )
            authorization_receipt = (
                self.identity_authorization_bridge.verify_existing_binding(
                    authorization_receipt_id=authorization_receipt_id,
                    identity_receipt_id=identity_receipt_id,
                )
            )
            return IdentityBoundWorkAcceptanceResult(
                quest=record,
                identity_receipt_id=identity_receipt_id,
                authorization_receipt_id=authorization_receipt_id,
                authorization_request_digest=str(
                    authorization_receipt.get("request_digest") or ""
                ),
            )

        authorization = (
            self.identity_authorization_bridge.authorize_work_acceptance(
                quest_id=quest_id,
                expected_revision=expected_revision,
                identity_receipt_id=identity_receipt_id,
            )
        )
        quest = self.quest_service.accept_work(
            quest_id,
            expected_revision=expected_revision,
            operator_role=operator_role,
            authorization_receipt_id=(
                authorization.authorization_receipt_id
            ),
            authorization_request=authorization.authorization_request,
            reason=normalized_reason,
        )
        receipt_principal = str(
            authorization.authorization_receipt.get("principal_id") or ""
        )
        if (
            quest.payload.get("work_acceptance", {}).get("principal_id")
            != receipt_principal
        ):
            raise WorkSourcePolicyError(
                "Quest acceptance is not bound to the authorized principal"
            )
        return IdentityBoundWorkAcceptanceResult(
            quest=quest,
            identity_receipt_id=authorization.identity_receipt_id,
            authorization_receipt_id=(
                authorization.authorization_receipt_id
            ),
            authorization_request_digest=str(
                authorization.authorization_receipt.get("request_digest")
                or ""
            ),
        )
