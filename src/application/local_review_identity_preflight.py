from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from src.application.local_operator_identity_preflight import (
    LocalOperatorIdentityPreflightService,
)
from src.domain.identity import IdentityEvaluation
from src.domain.quests import (
    QuestConflict,
    QuestLifecycleState,
    QuestStateError,
    WorkSourcePolicyError,
)


class LocalReviewIdentityPreflightService(LocalOperatorIdentityPreflightService):
    """Issues local-simulation PIBC evidence for review operations.

    Identity, membership, session, tenant, project, and assurance are selected
    only from the repository-owned fixture. The caller supplies only the Quest,
    expected revision, and accountable-operator role.
    """

    _ALLOWED_STATES = {
        QuestLifecycleState.WORK_ACCEPTED.value,
        QuestLifecycleState.REWORK_REQUIRED.value,
        QuestLifecycleState.REVIEW_REQUIRED.value,
    }

    def issue_for_review(
        self,
        *,
        quest_id: str,
        expected_revision: int,
        operator_role: str,
        now: datetime | None = None,
    ) -> IdentityEvaluation:
        if operator_role != "ACCOUNTABLE_OPERATOR":
            raise WorkSourcePolicyError(
                "Only the accountable operator may request review identity preflight"
            )
        record = self.quest_service.get(quest_id)
        if record.revision != expected_revision:
            raise QuestConflict(
                f"Expected Quest revision {expected_revision}, found {record.revision}"
            )
        state = str(record.payload.get("lifecycle_state") or "")
        if state not in self._ALLOWED_STATES:
            raise QuestStateError(
                f"Quest {quest_id} is not in a review-capable lifecycle state"
            )
        work_acceptance = dict(record.payload.get("work_acceptance") or {})
        if work_acceptance.get("decision") != "WORK_ACCEPTED":
            raise QuestStateError(
                "Review identity preflight requires prior WORK_ACCEPTED evidence"
            )

        binding = self._trusted_local_binding()
        exact_revision, _ = self.quest_service._authorization_revision()
        assertion_material = "|".join(
            [
                "review",
                quest_id,
                str(expected_revision),
                state,
                str(binding["principal_id"]),
                str(binding["membership_id"]),
                str(binding["session_id"]),
                str(binding["tenant_id"]),
                str(binding["project_id"]),
                exact_revision,
            ]
        )
        assertion_id = "local-review-preflight-" + sha256(
            assertion_material.encode("utf-8")
        ).hexdigest()[:24]

        evaluation = self.identity_boundary_service.evaluate(
            provider_type="LOCAL_DEVELOPMENT",
            raw_assertion={
                "assertion_id": assertion_id,
                "principal_id": binding["principal_id"],
                "issuer": binding["issuer"],
                "audience": "aigc-local-operator",
            },
            membership_id=str(binding["membership_id"]),
            session_id=str(binding["session_id"]),
            tenant_id=str(binding["tenant_id"]),
            project_id=str(binding["project_id"]),
            exact_revision=exact_revision,
            production_mode=False,
            now=now or datetime.now(timezone.utc),
        )
        if not evaluation.permitted:
            reasons = ", ".join(
                item.value for item in evaluation.reason_codes
            )
            raise WorkSourcePolicyError(
                "Local review PIBC preflight denied"
                + (f": {reasons}" if reasons else "")
            )
        return evaluation
