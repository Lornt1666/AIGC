from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from src.domain.quests import (
    QuestCandidateConflict,
    QuestCandidateNotFound,
    QuestCandidateRepository,
    QuestCandidateStateError,
    QuestCandidateStatus,
    WorkSourcePolicyError,
)
from src.domain.repositories import StoredRecord


_CANDIDATE_ID = re.compile(r"^cand_[A-Za-z0-9_-]{6,80}$")
_EXISTING_READ_ONLY_ADAPTERS = frozenset(
    {"remoteok", "remotive", "weworkremotely", "github_issues"}
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


class WorkSourceCatalog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        documents = [json.loads(self.path.read_text(encoding="utf-8"))]
        addendum_path = self.path.with_name(
            "aigc_work_source_gate_catalog_addendum.json"
        )
        if addendum_path.exists():
            documents.append(
                json.loads(addendum_path.read_text(encoding="utf-8"))
            )

        latest = documents[-1]
        self.catalog_version = str(
            latest.get("catalog_version")
            or documents[0].get("catalog_version")
            or "1.0.0"
        )
        self.authority_boundary = dict(
            latest.get("authority_boundary")
            or {
                "catalog_inclusion_grants_access": False,
                "catalog_inclusion_grants_external_action": False,
                "default_external_action_performed": False,
            }
        )
        self._sources: dict[str, dict[str, Any]] = {}
        for document in documents:
            for raw_source in document.get("sources", []):
                source = dict(raw_source)
                source_id = str(source["id"])
                source.setdefault("platform_role", "opportunity_source")
                source.setdefault(
                    "terms_review_target",
                    "official terms, platform rules, and interface policy review required",
                )
                source.setdefault(
                    "api_or_feed",
                    "official interface only if separately documented and approved",
                )
                source.setdefault(
                    "access_mode",
                    "manual_entry_or_approved_connector_only",
                )
                source.setdefault("connector_status", "review_required")
                source.setdefault(
                    "discovery_mode",
                    "existing_read_only_adapter_or_manual_entry"
                    if source_id in _EXISTING_READ_ONLY_ADAPTERS
                    else "manual_only",
                )
                source.setdefault(
                    "external_action_mode",
                    "separate policy evaluation and accountable-operator authorization required",
                )
                self._sources[source_id] = source
        if not self._sources:
            raise RuntimeError("Work-source catalog must contain at least one source")

    def require(self, source_id: str) -> dict[str, Any]:
        source = self._sources.get(source_id)
        if source is None:
            raise WorkSourcePolicyError(f"Unknown work source: {source_id}")
        return dict(source)

    def list(self, *, category: str | None = None) -> list[dict[str, Any]]:
        sources = list(self._sources.values())
        if category is not None:
            sources = [
                source
                for source in sources
                if source["category"] == category
            ]
        return sorted(
            (dict(source) for source in sources),
            key=lambda source: (source["category"], source["name"]),
        )

    def assert_ingestion_channel(
        self,
        source: Mapping[str, Any],
        channel: str,
    ) -> None:
        source_id = str(source["id"])
        connector_status = str(source["connector_status"])
        if channel == "manual":
            return
        if channel == "existing_read_only_adapter":
            if source_id not in _EXISTING_READ_ONLY_ADAPTERS:
                raise WorkSourcePolicyError(
                    f"{source_id} is not an existing AIGC read-only adapter"
                )
            return
        if channel == "approved_read_only_adapter":
            if connector_status != "read_only_enabled":
                raise WorkSourcePolicyError(
                    f"{source_id} has not been promoted to read_only_enabled"
                )
            return
        raise WorkSourcePolicyError(
            f"Unsupported ingestion channel: {channel}"
        )


class QuestCandidateApplicationService:
    def __init__(
        self,
        repository: QuestCandidateRepository,
        *,
        catalog_path: str | Path,
        schema_path: str | Path,
        exact_revision: str = "LOCAL_UNVERIFIED",
    ) -> None:
        self.repository = repository
        self.catalog = WorkSourceCatalog(catalog_path)
        self.exact_revision = exact_revision
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )

    def list_sources(
        self,
        *,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.catalog.list(category=category)

    def ingest(self, request: Mapping[str, Any]) -> StoredRecord:
        raw = dict(request)
        source_id = str(raw["source_id"]).strip()
        source = self.catalog.require(source_id)
        ingestion_channel = str(raw.get("ingestion_channel") or "manual")
        self.catalog.assert_ingestion_channel(source, ingestion_channel)

        title = str(raw["title"]).strip()
        description = str(raw["description"]).strip()
        source_url = str(raw["source_url"]).strip()
        if not title or not description:
            raise ValueError("title and description are required")

        candidate_id = str(raw.get("candidate_id") or "").strip()
        if not candidate_id:
            material = f"{source_id}|{source_url}|{title}"
            candidate_id = (
                f"cand_{sha256(material.encode('utf-8')).hexdigest()[:16]}"
            )
        if not _CANDIDATE_ID.fullmatch(candidate_id):
            raise ValueError(
                "candidate_id does not match the canonical cand_ format"
            )

        skills: list[str] = []
        seen: set[str] = set()
        for skill in raw.get("required_skills") or []:
            normalized = str(skill).strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                skills.append(normalized)

        budget_range = raw.get("budget_range")
        if budget_range is not None:
            budget_range = dict(budget_range)
            minimum = budget_range.get("min")
            maximum = budget_range.get("max")
            if (
                minimum is not None
                and maximum is not None
                and minimum > maximum
            ):
                raise ValueError(
                    "budget_range.min must be less than or equal to budget_range.max"
                )

        now = _utc_now()
        input_digest = _digest(raw)
        candidate: dict[str, Any] = {
            "candidate_id": candidate_id,
            "source_id": source_id,
            "source_url": source_url,
            "source_name": source["name"],
            "source_category": source["category"],
            "platform_role": source["platform_role"],
            "title": title,
            "description": description,
            "proposed_quest_title": str(
                raw.get("proposed_quest_title") or title
            ).strip(),
            "domain": str(raw["domain"]).strip().lower(),
            "required_skills": skills,
            "budget_range": budget_range,
            "compensation_text": raw.get("compensation_text"),
            "deadline_days": raw.get("deadline_days"),
            "deadline_at": raw.get("deadline_at"),
            "location": raw.get("location"),
            "remote_status": raw.get("remote_status") or "unspecified",
            "issuer": raw.get("issuer"),
            "risk_class": raw.get("risk_class") or "unassessed",
            "rights_status": raw.get("rights_status") or "public_posting",
            "ingestion_channel": ingestion_channel,
            "source_access_mode": source["access_mode"],
            "source_connector_status": source["connector_status"],
            "source_policy_snapshot": {
                "terms_review_target": source["terms_review_target"],
                "api_or_feed": source["api_or_feed"],
                "discovery_mode": source["discovery_mode"],
                "external_action_mode": source["external_action_mode"],
            },
            "provenance": {
                "normalized_by": "QuestCandidateApplicationService",
                "catalog_version": self.catalog.catalog_version,
                "input_digest": input_digest,
                "observed_at": str(raw.get("observed_at") or now),
            },
            "ingested_at": now,
            "status": QuestCandidateStatus.DISCOVERED.value,
            "qualification": None,
            "external_action_performed": False,
        }
        self._validate(candidate)
        return self.repository.ingest(
            candidate,
            idempotency_key=(
                f"quest-candidate-ingest:{candidate_id}:{input_digest}"
            ),
            exact_revision=self.exact_revision,
        )

    def list_candidates(
        self,
        *,
        status: QuestCandidateStatus | None = None,
    ) -> Sequence[StoredRecord]:
        records = self.repository.list()
        if status is None:
            return records
        return tuple(
            record
            for record in records
            if record.payload.get("status") == status.value
        )

    def qualify(
        self,
        candidate_id: str,
        *,
        expected_revision: int,
        operator_role: str,
        decision: str,
        reason: str | None,
    ) -> StoredRecord:
        if operator_role != "ACCOUNTABLE_OPERATOR":
            raise WorkSourcePolicyError(
                "Only ACCOUNTABLE_OPERATOR may qualify a candidate"
            )
        if decision != "QUALIFY":
            raise WorkSourcePolicyError(
                "Qualification decision must be QUALIFY"
            )

        existing = self.repository.get(candidate_id)
        if existing is None:
            raise QuestCandidateNotFound(candidate_id)
        current_status = str(existing.payload.get("status"))
        if current_status == QuestCandidateStatus.QUALIFIED.value:
            if expected_revision not in {
                existing.revision,
                existing.revision - 1,
            }:
                raise QuestCandidateConflict(
                    f"Expected revision {expected_revision}, "
                    f"found {existing.revision}"
                )
            return existing
        if current_status != QuestCandidateStatus.DISCOVERED.value:
            raise QuestCandidateStateError(
                f"Candidate {candidate_id} cannot qualify from {current_status}"
            )
        if existing.revision != expected_revision:
            raise QuestCandidateConflict(
                f"Expected revision {expected_revision}, "
                f"found {existing.revision}"
            )

        now = _utc_now()
        candidate = dict(existing.payload)
        candidate["status"] = QuestCandidateStatus.QUALIFIED.value
        candidate["qualification"] = {
            "decision": "QUALIFY",
            "operator_role": "ACCOUNTABLE_OPERATOR",
            "reason": reason,
            "qualified_at": now,
            "quest_creation_authorized": True,
            "quest_created": False,
            "quest_id": None,
            "quest_created_at": None,
            "quest_request_digest": None,
            "next_step": "CREATE_QUEST_UNDER_CANONICAL_LIFECYCLE",
        }
        candidate["external_action_performed"] = False
        self._validate(candidate)
        return self.repository.qualify(
            candidate_id,
            candidate,
            expected_revision=expected_revision,
            exact_revision=self.exact_revision,
        )

    def _validate(self, candidate: Mapping[str, Any]) -> None:
        errors = sorted(
            self.validator.iter_errors(dict(candidate)),
            key=lambda error: list(error.absolute_path),
        )
        if not errors:
            return
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise ValueError(
            f"Quest candidate contract validation failed: {detail}"
        )
