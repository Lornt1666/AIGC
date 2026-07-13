from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

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
    )


class QuestApplicationService:
    """Creates and reads canonical Quest aggregates without accepting the work commitment."""

    def __init__(
        self,
        candidate_repository: RecordRepository,
        quest_repository: QuestRepository,
        *,
        schema_path: str | Path,
        exact_revision: str = "LOCAL_UNVERIFIED",
    ) -> None:
        self.candidate_repository = candidate_repository
        self.quest_repository = quest_repository
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
        if operator_role != "ACCOUNTABLE_OPERATOR":
            raise WorkSourcePolicyError(
                "Only ACCOUNTABLE_OPERATOR may create a Quest from a qualified candidate"
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
        request_digest = sha256(
            _canonical(logical_request).encode("utf-8")
        ).hexdigest()

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
