from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from src.application.identity_boundary import IdentityBoundaryService
from src.application.quests import QuestApplicationService
from src.domain.identity import IdentityEvaluation
from src.domain.quests import QuestConflict, QuestLifecycleState, QuestStateError, WorkSourcePolicyError


class LocalOperatorIdentityPreflightService:
    """Issues a local-simulation PIBC receipt from repository-owned bindings.

    The caller supplies no principal, role, assurance, tenant, project, session,
    provider claim, or credential. All identity material is selected from the
    reviewed local fixture and verified by PIBC-v1.
    """

    def __init__(
        self,
        *,
        identity_boundary_service: IdentityBoundaryService,
        quest_service: QuestApplicationService,
        identity_fixture_path: str | Path,
    ) -> None:
        self.identity_boundary_service = identity_boundary_service
        self.quest_service = quest_service
        self.identity_fixture_path = Path(identity_fixture_path)

    def issue_for_quest(
        self,
        *,
        quest_id: str,
        expected_revision: int,
        operator_role: str,
        now: datetime | None = None,
    ) -> IdentityEvaluation:
        if operator_role != "ACCOUNTABLE_OPERATOR":
            raise WorkSourcePolicyError(
                "Only the accountable operator may request local identity preflight"
            )
        record = self.quest_service.get(quest_id)
        if record.revision != expected_revision:
            raise QuestConflict(
                f"Expected Quest revision {expected_revision}, found {record.revision}"
            )
        if (
            record.payload.get("lifecycle_state")
            != QuestLifecycleState.APPROVAL_REQUIRED.value
        ):
            raise QuestStateError(
                f"Quest {quest_id} must be APPROVAL_REQUIRED before identity preflight"
            )
        approval = dict(record.payload.get("approval_request") or {})
        if approval.get("status") != "PENDING":
            raise QuestStateError("Work-approval request is not pending")
        if approval.get("quest_revision") != expected_revision:
            raise QuestStateError(
                "Work-approval request is not bound to the current Quest revision"
            )

        binding = self._trusted_local_binding()
        exact_revision = str(approval.get("exact_revision") or "")
        assertion_material = "|".join(
            [
                str(binding["principal_id"]),
                str(binding["membership_id"]),
                str(binding["session_id"]),
                str(binding["tenant_id"]),
                str(binding["project_id"]),
                exact_revision,
            ]
        )
        assertion_id = "local-preflight-" + sha256(
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
                "Local PIBC preflight denied"
                + (f": {reasons}" if reasons else "")
            )
        return evaluation

    def _trusted_local_binding(self) -> dict[str, str]:
        fixture = json.loads(
            self.identity_fixture_path.read_text(encoding="utf-8")
        )
        memberships = [
            dict(item)
            for item in fixture.get("memberships") or []
            if str(item.get("status") or "").upper() == "ACTIVE"
            and item.get("revoked") is not True
        ]
        if len(memberships) != 1:
            raise WorkSourcePolicyError(
                "Local fixture must expose exactly one active operator membership"
            )
        membership = memberships[0]
        principal = self._one(
            fixture.get("principals") or [],
            "principal_id",
            membership.get("principal_id"),
            "principal",
        )
        sessions = [
            dict(item)
            for item in fixture.get("sessions") or []
            if item.get("principal_id") == principal.get("principal_id")
            and item.get("membership_id") == membership.get("membership_id")
            and item.get("tenant_id") == membership.get("tenant_id")
            and item.get("active_project_id")
            in set(membership.get("project_ids") or [])
            and str(item.get("session_state") or "").upper() == "ACTIVE"
        ]
        if len(sessions) != 1:
            raise WorkSourcePolicyError(
                "Local fixture must expose exactly one active operator session"
            )
        session = sessions[0]
        return {
            "principal_id": str(principal["principal_id"]),
            "membership_id": str(membership["membership_id"]),
            "session_id": str(session["session_id"]),
            "tenant_id": str(membership["tenant_id"]),
            "project_id": str(session["active_project_id"]),
            "issuer": str(principal["authority_source"]),
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
                f"Local fixture {label} could not be resolved uniquely"
            )
        return found[0]
