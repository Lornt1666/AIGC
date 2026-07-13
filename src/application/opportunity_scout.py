from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from uuid import uuid4
import xml.etree.ElementTree as ET

from src.domain.repositories import AuditEventRepository, StoredRecord
from src.phase2_radar import (
    CONNECTORS,
    BaseConnector,
    FetchResult,
    OpportunityRecord,
    RadarDecision,
)

from .opportunity_assessors import OpportunityAssessmentPipeline
from .quest_candidates import QuestCandidateApplicationService


_DEFAULT_SOURCE_IDS = ("weworkremotely", "remotive")
_CANDIDATE_SOURCE_IDS = {
    "weworkremotely": "weworkremotely",
    "remotive": "remotive",
    "remoteok": "remoteok",
    "github": "github_issues",
}
_ALLOWED_CONNECTORS = frozenset(
    {"wwr_rss", "remotive", "remoteok", "github_search"}
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _record_response(record: StoredRecord) -> dict[str, Any]:
    return {
        **dict(record.payload),
        "revision": record.revision,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


class OpportunityScoutError(RuntimeError):
    pass


class OpportunityScoutPolicyError(OpportunityScoutError):
    pass


class OpportunityScoutUnavailable(OpportunityScoutError):
    def __init__(self, report: Mapping[str, Any]) -> None:
        super().__init__("All requested Opportunity Scout sources failed")
        self.report = dict(report)


class OpportunityScoutApplicationService:
    """Run fixed readers, assess results, and persist governed candidates."""

    def __init__(
        self,
        candidate_service: QuestCandidateApplicationService,
        audit_repository: AuditEventRepository,
        *,
        source_config_path: str | Path,
        exact_revision: str = "LOCAL_UNVERIFIED",
        connector_registry: Mapping[str, type[BaseConnector]] | None = None,
        assessment_pipeline: OpportunityAssessmentPipeline | None = None,
    ) -> None:
        self.candidate_service = candidate_service
        self.audit_repository = audit_repository
        self.source_config_path = Path(source_config_path)
        self.exact_revision = exact_revision
        self.connector_registry: dict[str, type[BaseConnector]] = dict(
            connector_registry or CONNECTORS
        )
        self.assessment_pipeline = (
            assessment_pipeline or OpportunityAssessmentPipeline()
        )
        document = json.loads(
            self.source_config_path.read_text(encoding="utf-8")
        )
        if document.get("external_actions_allowed") is not False:
            raise OpportunityScoutPolicyError(
                "Opportunity Scout configuration must prohibit external actions"
            )
        self.run_config = dict(document.get("run") or {})
        self.sources = {
            str(source.get("slug")): dict(source)
            for source in document.get("sources", [])
            if source.get("slug")
        }

    def discover(
        self,
        *,
        limit: int = 5,
        source_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 25:
            raise ValueError("limit must be between 1 and 25")

        requested_sources = self._normalize_source_ids(source_ids)
        validated_sources = self._validate_sources_before_read(
            requested_sources
        )
        run_id = f"scout_{uuid4().hex}"
        started_at = _now()
        request_digest = sha256(
            _canonical(
                {
                    "limit": limit,
                    "source_ids": requested_sources,
                    "assessment_version": (
                        self.assessment_pipeline.ASSESSMENT_VERSION
                    ),
                    "external_actions_allowed": False,
                }
            ).encode("utf-8")
        ).hexdigest()

        source_results: list[dict[str, Any]] = []
        assessed_records: list[
            tuple[str, OpportunityRecord, dict[str, Any]]
        ] = []
        successful_sources = 0

        for source_id, source, connector_type in validated_sources:
            connector = connector_type(
                source,
                {**self.run_config, "max_per_source": limit},
            )
            try:
                result: FetchResult = connector.fetch()
            except (
                HTTPError,
                URLError,
                TimeoutError,
                ET.ParseError,
                json.JSONDecodeError,
                ValueError,
            ) as exc:
                source_results.append(
                    self._source_error(source_id, source, exc)
                )
                continue
            except Exception as exc:
                source_results.append(
                    self._source_error(source_id, source, exc)
                )
                continue

            successful_sources += 1
            eligible = 0
            rejected = 0
            assessment_errors = 0
            for record in result.normalized_records:
                try:
                    assessed, assessment = self.assessment_pipeline.assess(
                        record
                    )
                except Exception:
                    assessment_errors += 1
                    continue

                risk = assessment["risk"]
                if (
                    risk["radar_decision"] == RadarDecision.REJECT.value
                    or risk["forbidden_flags"]
                ):
                    rejected += 1
                    continue
                eligible += 1
                assessed_records.append(
                    (source_id, assessed, assessment)
                )

            source_results.append(
                {
                    "source_id": source_id,
                    "source_name": result.source_name,
                    "status": "success",
                    "records_fetched": len(result.normalized_records),
                    "records_eligible": eligible,
                    "records_rejected": rejected,
                    "assessment_errors": assessment_errors,
                }
            )

        deduped_records, duplicates_removed = self._dedupe(
            assessed_records
        )
        deduped_records.sort(
            key=lambda item: (
                int(item[2]["risk"]["radar_score"]),
                item[1].updated_at or item[1].posted_at,
                item[1].title,
            ),
            reverse=True,
        )
        selected = deduped_records[:limit]

        candidates: list[dict[str, Any]] = []
        new_candidates = 0
        existing_candidates = 0
        ingestion_errors: list[dict[str, Any]] = []

        for source_id, record, assessment in selected:
            candidate_id = f"cand_{record.opportunity_id}"
            try:
                payload = self._candidate_payload(
                    source_id,
                    record,
                    assessment,
                )
                candidate_id = str(payload["candidate_id"])
                existed = (
                    self.candidate_service.get_candidate(candidate_id)
                    is not None
                )
                stored = self.candidate_service.ingest(payload)
            except Exception as exc:
                ingestion_errors.append(
                    {
                        "candidate_id": candidate_id,
                        "source_id": source_id,
                        "error_type": type(exc).__name__,
                        "message": str(exc)[:1000],
                    }
                )
                continue

            if existed:
                existing_candidates += 1
            else:
                new_candidates += 1
            candidates.append(
                {
                    **_record_response(stored),
                    "radar_score": assessment["risk"]["radar_score"],
                    "radar_decision": assessment["risk"][
                        "radar_decision"
                    ],
                    "radar_risk_flags": list(
                        assessment["risk"]["risk_flags"]
                    ),
                    "qualification_recommended": assessment["risk"][
                        "qualification_recommended"
                    ],
                }
            )

        completed_at = _now()
        if successful_sources == 0:
            status = "failed"
        elif (
            any(item["status"] == "error" for item in source_results)
            or ingestion_errors
            or any(
                int(item.get("assessment_errors", 0)) > 0
                for item in source_results
            )
        ):
            status = "partial"
        elif not candidates:
            status = "no_eligible_candidates"
        else:
            status = "success"

        report: dict[str, Any] = {
            "status": status,
            "run_id": run_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "assessment_version": (
                self.assessment_pipeline.ASSESSMENT_VERSION
            ),
            "requested_sources": list(requested_sources),
            "scanned_sources": successful_sources,
            "source_results": source_results,
            "records_assessed": sum(
                int(item.get("records_fetched", 0))
                for item in source_results
            ),
            "assessment_errors": sum(
                int(item.get("assessment_errors", 0))
                for item in source_results
            ),
            "eligible_records": len(assessed_records),
            "duplicates_removed": duplicates_removed,
            "selected_records": len(selected),
            "new_candidates": new_candidates,
            "existing_candidates": existing_candidates,
            "ingestion_errors": ingestion_errors,
            "candidates": candidates,
            "external_reads_performed": successful_sources > 0,
            "external_action_performed": False,
        }
        self._record_run(report, request_digest=request_digest)

        if successful_sources == 0:
            raise OpportunityScoutUnavailable(report)
        return report

    def _normalize_source_ids(
        self,
        source_ids: Sequence[str] | None,
    ) -> tuple[str, ...]:
        values = source_ids or _DEFAULT_SOURCE_IDS
        normalized: list[str] = []
        for value in values:
            source_id = str(value).strip().lower()
            if source_id and source_id not in normalized:
                normalized.append(source_id)
        if not normalized:
            raise OpportunityScoutPolicyError(
                "At least one source must be selected"
            )
        return tuple(normalized)

    def _validate_sources_before_read(
        self,
        source_ids: Sequence[str],
    ) -> tuple[tuple[str, dict[str, Any], type[BaseConnector]], ...]:
        validated: list[
            tuple[str, dict[str, Any], type[BaseConnector]]
        ] = []
        for source_id in source_ids:
            source = self._require_source(source_id)
            connector_key = str(source["connector"])
            connector_type = self.connector_registry.get(connector_key)
            if connector_type is None:
                raise OpportunityScoutPolicyError(
                    "No reviewed connector implementation is registered for "
                    f"{source_id}"
                )
            validated.append((source_id, source, connector_type))
        return tuple(validated)

    def _require_source(self, source_id: str) -> dict[str, Any]:
        source = self.sources.get(source_id)
        if source is None:
            raise OpportunityScoutPolicyError(
                "Unknown or unconfigured Opportunity Scout source: "
                f"{source_id}"
            )
        if source_id not in _CANDIDATE_SOURCE_IDS:
            raise OpportunityScoutPolicyError(
                f"Source {source_id} has no reviewed Quest Candidate mapping"
            )
        if source.get("enabled") is not True:
            raise OpportunityScoutPolicyError(
                f"Source {source_id} is not enabled for read-only discovery"
            )
        if source.get("status") not in {"green", "yellow"}:
            raise OpportunityScoutPolicyError(
                f"Source {source_id} is not green/yellow for read-only discovery"
            )
        connector_key = str(source.get("connector") or "")
        if connector_key not in _ALLOWED_CONNECTORS:
            raise OpportunityScoutPolicyError(
                f"Connector {connector_key or '<missing>'} is not allowlisted"
            )
        if (
            source.get("requires_api_key")
            or source.get("requires_app_registration")
        ):
            raise OpportunityScoutPolicyError(
                f"Source {source_id} requires credentials or registration"
            )
        if not set(source.get("forbidden_actions") or []):
            raise OpportunityScoutPolicyError(
                f"Source {source_id} lacks an explicit forbidden-action policy"
            )
        return dict(source)

    @staticmethod
    def _source_error(
        source_id: str,
        source: Mapping[str, Any],
        error: Exception,
    ) -> dict[str, Any]:
        return {
            "source_id": source_id,
            "source_name": source.get("name", source_id),
            "status": "error",
            "error_type": type(error).__name__,
            "message": str(error)[:1000],
            "records_fetched": 0,
            "assessment_errors": 0,
        }

    @staticmethod
    def _dedupe(
        records: Sequence[
            tuple[str, OpportunityRecord, dict[str, Any]]
        ],
    ) -> tuple[
        list[tuple[str, OpportunityRecord, dict[str, Any]]],
        int,
    ]:
        selected: dict[
            str,
            tuple[str, OpportunityRecord, dict[str, Any]],
        ] = {}
        for source_id, record, assessment in records:
            key = (
                record.source_url.strip().lower()
                or f"{source_id}:{record.opportunity_id}"
            )
            current = selected.get(key)
            if (
                current is None
                or assessment["risk"]["radar_score"]
                > current[2]["risk"]["radar_score"]
            ):
                selected[key] = (source_id, record, assessment)
        return list(selected.values()), len(records) - len(selected)

    def _candidate_payload(
        self,
        scout_source_id: str,
        record: OpportunityRecord,
        assessment: Mapping[str, Any],
    ) -> dict[str, Any]:
        source_id = _CANDIDATE_SOURCE_IDS[scout_source_id]
        title = record.title.strip()
        source_url = record.source_url.strip()
        description = record.description_plain.strip() or title
        if not title or not source_url.startswith(("http://", "https://")):
            raise ValueError(
                "Opportunity record lacks a valid title or source URL"
            )

        ology = dict(assessment["ology"])
        risk = dict(assessment["risk"])

        budget_range: dict[str, Any] | None = None
        compensation_text: str | None = None
        if record.pay_min is not None or record.pay_max is not None:
            budget_range = {
                "min": record.pay_min,
                "max": record.pay_max,
                "currency": record.pay_currency or None,
            }
            compensation_text = " ".join(
                part
                for part in [
                    str(record.pay_currency or "").strip(),
                    (
                        f"{record.pay_min or '?'}-{record.pay_max or '?'}"
                        if record.pay_min != record.pay_max
                        else str(
                            record.pay_min
                            or record.pay_max
                            or ""
                        )
                    ),
                    (
                        f"per {record.pay_interval}"
                        if record.pay_interval
                        and record.pay_interval != "unknown"
                        else ""
                    ),
                ]
                if part
            ) or None

        return {
            "candidate_id": f"cand_{record.opportunity_id}",
            "source_id": source_id,
            "source_url": source_url,
            "title": title[:500],
            "description": description[:50000],
            "proposed_quest_title": title[:500],
            "domain": ology["primary_domain"],
            "required_skills": list(ology["required_skills"]),
            "budget_range": budget_range,
            "compensation_text": compensation_text,
            "deadline_days": None,
            "deadline_at": None,
            "location": record.location[:500] or None,
            "remote_status": (
                record.remote_status
                if record.remote_status in {"remote", "hybrid", "onsite"}
                else "unspecified"
            ),
            "issuer": (record.employer or record.client)[:500] or None,
            "risk_class": risk["risk_class"],
            "rights_status": (
                "official_api_record"
                if record.source_type == "api"
                else "public_posting"
            ),
            "ingestion_channel": "existing_read_only_adapter",
            "assessment": dict(assessment),
        }

    def _record_run(
        self,
        report: Mapping[str, Any],
        *,
        request_digest: str,
    ) -> None:
        summary = {
            "run_id": report["run_id"],
            "status": report["status"],
            "assessment_version": report["assessment_version"],
            "requested_sources": report["requested_sources"],
            "scanned_sources": report["scanned_sources"],
            "records_assessed": report["records_assessed"],
            "assessment_errors": report["assessment_errors"],
            "eligible_records": report["eligible_records"],
            "duplicates_removed": report["duplicates_removed"],
            "new_candidates": report["new_candidates"],
            "existing_candidates": report["existing_candidates"],
            "source_errors": [
                {
                    "source_id": item["source_id"],
                    "error_type": item.get("error_type"),
                }
                for item in report["source_results"]
                if item["status"] == "error"
            ],
            "ingestion_error_count": len(report["ingestion_errors"]),
            "external_reads_performed": report[
                "external_reads_performed"
            ],
            "external_action_performed": False,
        }
        self.audit_repository.append(
            f"opportunity-scout:{report['run_id']}",
            "opportunity_scout.completed",
            summary,
            exact_revision=self.exact_revision,
            request_digest=request_digest,
            idempotency_key=str(report["run_id"]),
        )
