from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from src.application.authorization_service import AuthorizationApplicationService
from src.domain.quests import (
    QuestConflict,
    QuestCreationResult,
    QuestLifecycleState,
    QuestNotFound,
    QuestRepository,
    QuestStateError,
    WorkSourcePolicyError,
)
from src.domain.repositories import RecordRepository, StoredRecord


_DEFAULT_SCOPE = (
    "Research, plan, and produce the requested work internally for accountable-operator review."
)
_DEFAULT_NON_SCOPE = (
    "No application, bid, message, contract acceptance, purchase, payment, delivery, deployment, "
    "credential use, or other external action is authorized by Quest creation."
)
_DEFAULT_ACCEPTANCE_CRITERIA = (
    "The output addresses the source posting requirements.",
    "Artifacts are reviewable, versioned, and evidence-bound.",
    "No external action occurs without a separate policy decision and operator authorization.",
)
_HEX40 = re.compile(r"^[a-f0-9]{40}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


class QuestApplicationService:
    """Creates and governs canonical Quests without performing external action."""

    def __init__(
        self,
        candidate_repository: RecordRepository,
        quest_repository: QuestRepository,
        authorization_service: AuthorizationApplicationService,
        *,
        schema_path: str | Path,
        exact_revision: str = "LOCAL_UNVERIFIED",
    ) -> None:
        self.candidate_repository = candidate_repository
        self.quest_repository = quest_repository
        self.authorization_service = authorization_service
        self.exact_revision = exact_revision
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )

    def create_from_candidate(
        self,
        candidate_id: str,
        *,
        expected_candidate_revision: int,
        operator_role: str,
        purpose: str | None = None,
        scope: str | None = None,
        non_scope: str | None = None,
        acceptance_criteria: Sequence[str] | None = None,
        budget: Mapping[str, Any] | None = None,
        deadline_at: str | datetime | None = None,
    ) -> QuestCreationResult:
        self._require_operator(
            operator_role,
            "create a Quest from a qualified candidate",
        )

        candidate_record = self.candidate_repository.get(candidate_id)
        if candidate_record is None:
            raise QuestNotFound(f"Candidate not found: {candidate_id}")

        candidate = dict(candidate_record.payload)
        if candidate.get("status") != "QUALIFIED":
            raise QuestStateError(
                f"Candidate {candidate_id} must be QUALIFIED before Quest creation"
            )
        qualification = dict(candidate.get("qualification") or {})
        if qualification.get("quest_creation_authorized") is not True:
            raise QuestStateError(
                f"Candidate {candidate_id} does not contain Quest-creation authorization"
            )

        already_created = qualification.get("quest_created") is True
        permitted_revisions = {candidate_record.revision}
        if already_created:
            permitted_revisions.add(candidate_record.revision - 1)
        if expected_candidate_revision not in permitted_revisions:
            raise QuestConflict(
                f"Expected candidate revision {expected_candidate_revision}, "
                f"found {candidate_record.revision}"
            )

        suffix = candidate_id.removeprefix("cand_")
        quest_id = f"quest_{suffix}"
        if len(quest_id) > 106:
            quest_id = (
                f"quest_{sha256(candidate_id.encode('utf-8')).hexdigest()[:24]}"
            )

        resolved_deadline = _parse_datetime(deadline_at)
        if resolved_deadline is None:
            resolved_deadline = _parse_datetime(candidate.get("deadline_at"))
        if resolved_deadline is None and candidate.get("deadline_days"):
            observed = _parse_datetime(
                (candidate.get("provenance") or {}).get("observed_at")
                or candidate.get("ingested_at")
            ) or _now()
            resolved_deadline = observed + timedelta(
                days=int(candidate["deadline_days"])
            )

        criteria: list[str] = []
        seen: set[str] = set()
        for item in acceptance_criteria or _DEFAULT_ACCEPTANCE_CRITERIA:
            normalized = str(item).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                criteria.append(normalized)
        if not criteria:
            raise ValueError("At least one acceptance criterion is required")

        resolved_budget = (
            dict(budget)
            if budget is not None
            else candidate.get("budget_range")
        )
        if resolved_budget is not None:
            resolved_budget = dict(resolved_budget)
            minimum = resolved_budget.get("min")
            maximum = resolved_budget.get("max")
            if (
                minimum is not None
                and maximum is not None
                and minimum > maximum
            ):
                raise ValueError(
                    "budget.min must be less than or equal to budget.max"
                )

        resolved_title = str(
            candidate.get("proposed_quest_title")
            or candidate.get("title")
            or ""
        ).strip()
        resolved_purpose = str(
            purpose or candidate.get("description") or ""
        ).strip()
        resolved_scope = str(scope or _DEFAULT_SCOPE).strip()
        resolved_non_scope = str(non_scope or _DEFAULT_NON_SCOPE).strip()
        resolved_deadline_text = (
            _iso(resolved_deadline) if resolved_deadline else None
        )

        logical_request = {
            "candidate_id": candidate_id,
            "expected_candidate_revision": expected_candidate_revision,
            "candidate_input_digest": candidate["provenance"]["input_digest"],
            "operator_role": operator_role,
            "quest_id": quest_id,
            "title": resolved_title,
            "purpose": resolved_purpose,
            "scope": resolved_scope,
            "non_scope": resolved_non_scope,
            "acceptance_criteria": criteria,
            "budget": resolved_budget,
            "deadline_at": resolved_deadline_text,
        }
        request_digest = _digest(logical_request)

        created_at = _now()
        quest: dict[str, Any] = {
            "quest_id": quest_id,
            "source_candidate_id": candidate_id,
            "title": resolved_title,
            "purpose": resolved_purpose,
            "scope": resolved_scope,
            "non_scope": resolved_non_scope,
            "owner_role": "ACCOUNTABLE_OPERATOR",
            "authority_class": "ACCOUNTABLE_OPERATOR",
            "risk_class": str(candidate.get("risk_class") or "unassessed"),
            "lifecycle_state": QuestLifecycleState.PROPOSED.value,
            "lifecycle_contract_id": "AIGC-JOB-LIFECYCLE-001",
            "lifecycle_contract_version": "1.0.0",
            "acceptance_criteria": criteria,
            "budget": resolved_budget,
            "deadline_at": resolved_deadline_text,
            "source_snapshot": {
                "source_id": candidate["source_id"],
                "source_name": candidate["source_name"],
                "source_url": candidate["source_url"],
                "posting_title": candidate["title"],
                "rights_status": candidate["rights_status"],
                "input_digest": candidate["provenance"]["input_digest"],
            },
            "created_from_candidate_revision": expected_candidate_revision,
            "approval_request": None,
            "work_acceptance": None,
            "terminal_decision": None,
            "created_at": _iso(created_at),
            "updated_at": _iso(created_at),
            "external_action_performed": False,
        }
        self._validate(quest)

        return self.quest_repository.create_from_candidate(
            candidate_id,
            quest,
            expected_candidate_revision=expected_candidate_revision,
            idempotency_key=(
                f"quest-create:{candidate_id}:{request_digest}"
            ),
            request_digest=request_digest,
            exact_revision=self.exact_revision,
        )

    def request_work_approval(
        self,
        quest_id: str,
        *,
        expected_revision: int,
        operator_role: str,
        reason: str | None = None,
    ) -> StoredRecord:
        self._require_operator(operator_role, "request work acceptance")
        normalized_reason = str(reason).strip() if reason else None
        logical_request = {
            "quest_id": quest_id,
            "expected_revision": expected_revision,
            "operator_role": operator_role,
            "reason": normalized_reason,
            "source_state": QuestLifecycleState.PROPOSED.value,
            "target_state": QuestLifecycleState.APPROVAL_REQUIRED.value,
            "planned_decision": QuestLifecycleState.WORK_ACCEPTED.value,
        }
        request_digest = _digest(logical_request)

        record = self.get(quest_id)
        if (
            record.payload.get("lifecycle_state")
            == QuestLifecycleState.APPROVAL_REQUIRED.value
        ):
            approval = dict(record.payload.get("approval_request") or {})
            if (
                approval.get("request_digest") == request_digest
                and record.revision == expected_revision + 1
            ):
                return record
            raise QuestConflict(
                "Quest already has a different work-approval request"
            )
        if (
            record.payload.get("lifecycle_state")
            != QuestLifecycleState.PROPOSED.value
        ):
            raise QuestStateError(
                f"Quest {quest_id} must be PROPOSED before requesting work approval"
            )
        if record.revision != expected_revision:
            raise QuestConflict(
                f"Expected Quest revision {expected_revision}, found {record.revision}"
            )

        exact_revision, binding_mode = self._authorization_revision()
        approval_request_id = (
            "approval_"
            + sha256(
                f"{quest_id}|{expected_revision}|{request_digest}".encode("utf-8")
            ).hexdigest()[:24]
        )
        planned_revision = expected_revision + 1
        transition_material = {
            "quest_id": quest_id,
            "approval_request_id": approval_request_id,
            "source_state": QuestLifecycleState.APPROVAL_REQUIRED.value,
            "target_state": QuestLifecycleState.WORK_ACCEPTED.value,
            "expected_quest_revision": planned_revision,
            "exact_revision": exact_revision,
        }
        transition_digest = _digest(transition_material)
        evidence_ids = [
            f"AIGC-APPROVAL-REQUEST:{approval_request_id}",
            f"AIGC-TRANSITION-DIGEST:{transition_digest}",
        ]

        quest = dict(record.payload)
        quest["lifecycle_state"] = QuestLifecycleState.APPROVAL_REQUIRED.value
        quest["approval_request"] = {
            "approval_request_id": approval_request_id,
            "requested_at": _iso(_now()),
            "requested_by_role": "ACCOUNTABLE_OPERATOR",
            "reason": normalized_reason,
            "source_state": QuestLifecycleState.PROPOSED.value,
            "target_state": QuestLifecycleState.WORK_ACCEPTED.value,
            "quest_revision": planned_revision,
            "exact_revision": exact_revision,
            "revision_binding_mode": binding_mode,
            "transition_digest": transition_digest,
            "request_digest": request_digest,
            "required_authorization": {
                "resource_id": quest_id,
                "action": "accept_work",
                "scopes": ["quest:work_accept"],
                "purpose": "work_acceptance",
                "evidence_ids": evidence_ids,
            },
            "status": "PENDING",
            "external_action_performed": False,
        }
        quest["work_acceptance"] = None
        quest["terminal_decision"] = None
        quest["external_action_performed"] = False
        self._validate(quest)

        return self.quest_repository.transition(
            quest_id,
            quest,
            expected_revision=expected_revision,
            allowed_from=[QuestLifecycleState.PROPOSED.value],
            target_state=QuestLifecycleState.APPROVAL_REQUIRED.value,
            event_type="quest.work_approval_requested",
            idempotency_key=(
                f"work-approval:{quest_id}:{expected_revision}"
            ),
            request_digest=request_digest,
            exact_revision=self.exact_revision,
            audit_payload={
                "approval_request_id": approval_request_id,
                "transition_digest": transition_digest,
                "authorization_exact_revision": exact_revision,
                "revision_binding_mode": binding_mode,
                "work_accepted": False,
            },
        )

    def build_work_acceptance_authorization_bundle(
        self,
        quest_id: str,
        fixture: Mapping[str, Any],
    ) -> dict[str, Any]:
        record = self.get(quest_id)
        if (
            record.payload.get("lifecycle_state")
            != QuestLifecycleState.APPROVAL_REQUIRED.value
        ):
            raise QuestStateError(
                f"Quest {quest_id} must be APPROVAL_REQUIRED before authorization"
            )
        approval = dict(record.payload.get("approval_request") or {})
        if approval.get("status") != "PENDING":
            raise QuestStateError(
                f"Quest {quest_id} has no pending work-approval request"
            )
        if approval.get("quest_revision") != record.revision:
            raise QuestStateError(
                "Work-approval evidence is not bound to the current Quest revision"
            )

        bundle = deepcopy(dict(fixture))
        principals = [dict(item) for item in bundle.get("principals") or []]
        memberships = [dict(item) for item in bundle.get("memberships") or []]
        sessions = [dict(item) for item in bundle.get("sessions") or []]
        policies = [dict(item) for item in bundle.get("policies") or []]
        if not principals or not memberships or not sessions or not policies:
            raise ValueError(
                "Local authorization fixture lacks identity or policy records"
            )

        scope = "quest:work_accept"
        membership = memberships[0]
        membership["roles"] = sorted(
            set(membership.get("roles") or []) | {"operator"}
        )
        membership["granted_scopes"] = sorted(
            set(membership.get("granted_scopes") or []) | {scope}
        )

        policy = policies[0]
        selectors = dict(policy.get("subject_selectors") or {})
        selectors["principal_ids"] = sorted(
            set(selectors.get("principal_ids") or [])
            | {str(principals[0]["principal_id"])}
        )
        selectors["role_ids"] = sorted(
            set(selectors.get("role_ids") or []) | {"operator"}
        )
        policy["subject_selectors"] = selectors
        policy["allowed_roles"] = sorted(
            set(policy.get("allowed_roles") or []) | {"operator"}
        )
        policy["allowed_actions"] = sorted(
            set(policy.get("allowed_actions") or []) | {"accept_work"}
        )
        policy["granted_scopes"] = sorted(
            set(policy.get("granted_scopes") or []) | {scope}
        )
        policy["permitted_purposes"] = sorted(
            set(policy.get("permitted_purposes") or [])
            | {"work_acceptance"}
        )

        request = dict(bundle.get("request") or {})
        request["request_id"] = (
            f"REQ-WORK-ACCEPT-{quest_id}-{record.revision}"
        )
        request["exact_revision"] = approval["exact_revision"]
        request["principal_id"] = principals[0]["principal_id"]
        request["membership_id"] = membership["membership_id"]
        request["session_id"] = sessions[0]["session_id"]
        request["tenant_id"] = membership["tenant_id"]
        request["project_id"] = sessions[0]["active_project_id"]
        request["resource"] = {
            "resource_id": quest_id,
            "tenant_id": request["tenant_id"],
            "project_id": request["project_id"],
            "sensitivity": "internal",
        }
        request["action"] = "accept_work"
        request["scopes"] = [scope]
        request["purpose"] = "work_acceptance"
        request["context"] = {
            "channel": "local-quest-board",
            "jurisdiction": ["CA-AB"],
            "operator_mode": "local_simulation",
            "risk_signals": [
                f"quest-risk:{record.payload.get('risk_class', 'unassessed')}"
            ],
        }
        request["assurance"] = {
            "ial": "IAL0",
            "aal": "AAL0",
            "fal": "FAL0",
            "evidence_maturity": "EA0_CLAIMED",
        }
        request["approval_reference_ids"] = []
        request["evidence_ids"] = list(
            approval["required_authorization"]["evidence_ids"]
        )
        request["request_digest"] = (
            self.authorization_service.kernel.request_digest(request)
        )

        return {
            "principals": principals,
            "memberships": memberships,
            "sessions": sessions,
            "policies": policies,
            "approvals": [
                dict(item) for item in bundle.get("approvals") or []
            ],
            "revocations": [
                dict(item) for item in bundle.get("revocations") or []
            ],
            "request": request,
        }

    def accept_work(
        self,
        quest_id: str,
        *,
        expected_revision: int,
        operator_role: str,
        authorization_receipt_id: str,
        authorization_request: Mapping[str, Any],
        reason: str | None = None,
    ) -> StoredRecord:
        self._require_operator(operator_role, "accept work")
        normalized_reason = str(reason).strip() if reason else None
        auth_request = dict(authorization_request)
        auth_request_digest = (
            self.authorization_service.kernel.request_digest(auth_request)
        )

        record = self.get(quest_id)
        approval = dict(record.payload.get("approval_request") or {})
        logical_request = {
            "quest_id": quest_id,
            "expected_revision": expected_revision,
            "operator_role": operator_role,
            "reason": normalized_reason,
            "approval_request_id": approval.get("approval_request_id"),
            "transition_digest": approval.get("transition_digest"),
            "authorization_receipt_id": authorization_receipt_id,
            "authorization_request_digest": auth_request_digest,
            "source_state": QuestLifecycleState.APPROVAL_REQUIRED.value,
            "target_state": QuestLifecycleState.WORK_ACCEPTED.value,
        }
        request_digest = _digest(logical_request)

        if (
            record.payload.get("lifecycle_state")
            == QuestLifecycleState.WORK_ACCEPTED.value
        ):
            acceptance = dict(record.payload.get("work_acceptance") or {})
            if (
                acceptance.get("request_digest") == request_digest
                and record.revision == expected_revision + 1
            ):
                return record
            raise QuestConflict(
                "Quest already contains a different work-acceptance decision"
            )
        if (
            record.payload.get("lifecycle_state")
            != QuestLifecycleState.APPROVAL_REQUIRED.value
        ):
            raise QuestStateError(
                f"Quest {quest_id} must be APPROVAL_REQUIRED before work acceptance"
            )
        if record.revision != expected_revision:
            raise QuestConflict(
                f"Expected Quest revision {expected_revision}, found {record.revision}"
            )
        if approval.get("status") != "PENDING":
            raise QuestStateError("Work-approval request is not pending")
        if approval.get("quest_revision") != expected_revision:
            raise QuestStateError(
                "Work-approval request is not bound to the current Quest revision"
            )

        required = dict(approval["required_authorization"])
        try:
            receipt = self.authorization_service.verify_permit_receipt(
                authorization_receipt_id,
                auth_request,
                expected_exact_revision=str(approval["exact_revision"]),
                expected_resource_id=quest_id,
                expected_action=str(required["action"]),
                expected_scopes=list(required["scopes"]),
                expected_purpose=str(required["purpose"]),
                required_evidence_ids=list(required["evidence_ids"]),
            )
        except ValueError as exc:
            raise WorkSourcePolicyError(str(exc)) from exc

        quest = dict(record.payload)
        approval["status"] = "CONSUMED"
        quest["approval_request"] = approval
        quest["lifecycle_state"] = QuestLifecycleState.WORK_ACCEPTED.value
        quest["work_acceptance"] = {
            "decision": "WORK_ACCEPTED",
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": normalized_reason,
            "accepted_at": _iso(_now()),
            "approval_request_id": approval["approval_request_id"],
            "transition_digest": approval["transition_digest"],
            "request_digest": request_digest,
            "authorization_receipt_id": authorization_receipt_id,
            "authorization_decision_id": str(receipt["decision_id"]),
            "authorization_request_digest": str(receipt["request_digest"]),
            "authorization_exact_revision": str(receipt["exact_revision"]),
            "principal_id": str(receipt["principal_id"]),
            "source_state": QuestLifecycleState.APPROVAL_REQUIRED.value,
            "target_state": QuestLifecycleState.WORK_ACCEPTED.value,
            "external_action_performed": False,
        }
        quest["terminal_decision"] = None
        quest["external_action_performed"] = False
        self._validate(quest)

        return self.quest_repository.transition(
            quest_id,
            quest,
            expected_revision=expected_revision,
            allowed_from=[QuestLifecycleState.APPROVAL_REQUIRED.value],
            target_state=QuestLifecycleState.WORK_ACCEPTED.value,
            event_type="quest.work_accepted",
            idempotency_key=(
                f"work-acceptance:{quest_id}:{expected_revision}"
            ),
            request_digest=request_digest,
            exact_revision=self.exact_revision,
            audit_payload={
                "approval_request_id": approval["approval_request_id"],
                "transition_digest": approval["transition_digest"],
                "authorization_receipt_id": authorization_receipt_id,
                "authorization_request_digest": receipt["request_digest"],
                "authorization_exact_revision": receipt["exact_revision"],
                "principal_id": receipt["principal_id"],
                "work_accepted": True,
            },
        )

    def reject(
        self,
        quest_id: str,
        *,
        expected_revision: int,
        operator_role: str,
        reason: str,
    ) -> StoredRecord:
        return self._terminal_transition(
            quest_id,
            expected_revision=expected_revision,
            operator_role=operator_role,
            reason=reason,
            target_state=QuestLifecycleState.REJECTED,
            allowed_from=(
                QuestLifecycleState.PROPOSED,
                QuestLifecycleState.APPROVAL_REQUIRED,
            ),
        )

    def cancel(
        self,
        quest_id: str,
        *,
        expected_revision: int,
        operator_role: str,
        reason: str,
    ) -> StoredRecord:
        return self._terminal_transition(
            quest_id,
            expected_revision=expected_revision,
            operator_role=operator_role,
            reason=reason,
            target_state=QuestLifecycleState.CANCELLED,
            allowed_from=(
                QuestLifecycleState.PROPOSED,
                QuestLifecycleState.APPROVAL_REQUIRED,
                QuestLifecycleState.WORK_ACCEPTED,
            ),
        )

    def _terminal_transition(
        self,
        quest_id: str,
        *,
        expected_revision: int,
        operator_role: str,
        reason: str,
        target_state: QuestLifecycleState,
        allowed_from: Sequence[QuestLifecycleState],
    ) -> StoredRecord:
        self._require_operator(
            operator_role,
            f"transition a Quest to {target_state.value}",
        )
        normalized_reason = str(reason).strip()
        if not normalized_reason:
            raise ValueError(
                f"A reason is required to transition a Quest to {target_state.value}"
            )

        record = self.get(quest_id)
        previous_state = str(record.payload.get("lifecycle_state") or "")
        logical_request = {
            "quest_id": quest_id,
            "expected_revision": expected_revision,
            "operator_role": operator_role,
            "reason": normalized_reason,
            "previous_state": previous_state,
            "target_state": target_state.value,
        }
        request_digest = _digest(logical_request)

        if previous_state == target_state.value:
            terminal = dict(record.payload.get("terminal_decision") or {})
            if (
                terminal.get("request_digest") == request_digest
                and record.revision == expected_revision + 1
            ):
                return record
            raise QuestConflict(
                f"Quest already contains a different {target_state.value} decision"
            )
        allowed_values = [state.value for state in allowed_from]
        if previous_state not in allowed_values:
            raise QuestStateError(
                f"Quest {quest_id} cannot transition from {previous_state} "
                f"to {target_state.value}"
            )
        if record.revision != expected_revision:
            raise QuestConflict(
                f"Expected Quest revision {expected_revision}, found {record.revision}"
            )

        quest = dict(record.payload)
        approval = quest.get("approval_request")
        if isinstance(approval, Mapping) and approval.get("status") == "PENDING":
            approval = dict(approval)
            approval["status"] = (
                "REJECTED"
                if target_state == QuestLifecycleState.REJECTED
                else "CANCELLED"
            )
            quest["approval_request"] = approval
        quest["lifecycle_state"] = target_state.value
        quest["terminal_decision"] = {
            "decision": target_state.value,
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": normalized_reason,
            "decided_at": _iso(_now()),
            "previous_state": previous_state,
            "request_digest": request_digest,
            "external_action_performed": False,
        }
        quest["external_action_performed"] = False
        self._validate(quest)

        return self.quest_repository.transition(
            quest_id,
            quest,
            expected_revision=expected_revision,
            allowed_from=allowed_values,
            target_state=target_state.value,
            event_type=f"quest.{target_state.value.lower()}",
            idempotency_key=(
                f"terminal:{quest_id}:{target_state.value}:{expected_revision}"
            ),
            request_digest=request_digest,
            exact_revision=self.exact_revision,
            audit_payload={
                "operator_role": "ACCOUNTABLE_OPERATOR",
                "reason": normalized_reason,
                "work_accepted": (
                    previous_state == QuestLifecycleState.WORK_ACCEPTED.value
                ),
            },
        )

    def get(self, quest_id: str) -> StoredRecord:
        record = self.quest_repository.get(quest_id)
        if record is None:
            raise QuestNotFound(quest_id)
        return record

    def list_quests(
        self,
        *,
        state: QuestLifecycleState | None = None,
    ) -> Sequence[StoredRecord]:
        records = self.quest_repository.list()
        if state is None:
            return records
        return tuple(
            record
            for record in records
            if record.payload.get("lifecycle_state") == state.value
        )

    def _authorization_revision(self) -> tuple[str, str]:
        normalized = str(self.exact_revision).lower()
        if _HEX40.fullmatch(normalized):
            return normalized, "exact_source_revision"
        derived = sha1(
            f"AIGC-LOCAL-SIMULATION:{self.exact_revision}".encode("utf-8")
        ).hexdigest()
        return derived, "derived_local_simulation"

    @staticmethod
    def _require_operator(operator_role: str, action: str) -> None:
        if operator_role != "ACCOUNTABLE_OPERATOR":
            raise WorkSourcePolicyError(
                f"Only ACCOUNTABLE_OPERATOR may {action}"
            )

    def _validate(self, quest: Mapping[str, Any]) -> None:
        errors = sorted(
            self.validator.iter_errors(dict(quest)),
            key=lambda error: list(error.absolute_path),
        )
        if not errors:
            return
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise ValueError(f"Quest contract validation failed: {detail}")
