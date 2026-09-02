from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Any, Mapping
from uuid import uuid4

from src.infrastructure.persistence.sqlite.connection import (
    SQLiteConnectionFactory,
)
from src.infrastructure.persistence.sqlite.migrations import SQLiteMigrator


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_ROOT = PACKAGE_ROOT / "database" / "migrations"


class GrantApplicationStorageError(ValueError):
    """Raised when local ACGS persistence cannot preserve its invariants."""


class GrantApplicationNotFound(GrantApplicationStorageError):
    """Raised when a requested local ACGS application does not exist."""


class GrantApplicationConflict(GrantApplicationStorageError):
    """Raised when an application revision no longer matches."""


class GrantApplicationStateError(GrantApplicationStorageError):
    """Raised when a local review transition is not allowed."""


class LocalGrantApplicationStore:
    """SQLite-backed draft and review records with append-only audit evidence."""

    def __init__(
        self,
        database_path: str | Path,
        migration_root: str | Path = MIGRATION_ROOT,
    ) -> None:
        self.factory = SQLiteConnectionFactory(database_path)
        self.migrator = SQLiteMigrator(self.factory, migration_root)
        self._migration_lock = Lock()
        self._migrated = False

    def create_application(self, package: Mapping[str, Any]) -> dict[str, Any]:
        self._ensure_migrated()
        application_id = str(package.get("application_id", "")).strip()
        if not application_id:
            raise GrantApplicationStorageError(
                "Persisted application requires an application ID."
            )
        payload = dict(package)
        payload_json = _canonical(payload)
        created_at = _utc_now()
        state = "AUDITED_REVIEW_REQUIRED"
        with self.factory.transaction() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO grant_applications(
                        application_id,
                        created_at,
                        lifecycle_state,
                        payload_json,
                        external_submission_performed,
                        revision,
                        updated_at
                    ) VALUES (?, ?, ?, ?, 0, 1, ?)
                    """,
                    (
                        application_id,
                        created_at,
                        state,
                        payload_json,
                        created_at,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise GrantApplicationConflict(
                    f"Application already exists: {application_id}"
                ) from exc
            self._append_audit_event(
                connection,
                application_id=application_id,
                event_type="grant_application.draft_generated",
                metadata=_audit_metadata(payload, state),
            )
        return self.get_application(application_id)

    def get_application(self, application_id: str) -> dict[str, Any]:
        self._ensure_migrated()
        with self.factory.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM grant_applications
                WHERE application_id = ?
                """,
                (application_id,),
            ).fetchone()
            if row is None:
                raise GrantApplicationNotFound(application_id)
            review_rows = connection.execute(
                """
                SELECT review_json
                FROM grant_operator_reviews
                WHERE application_id = ?
                ORDER BY application_revision ASC
                """,
                (application_id,),
            ).fetchall()
            audit_rows = connection.execute(
                """
                SELECT
                    event_id,
                    created_at,
                    event_type,
                    payload_digest,
                    metadata_json,
                    previous_event_hash,
                    event_hash
                FROM grant_audit_events
                WHERE application_id = ?
                ORDER BY rowid ASC
                """,
                (application_id,),
            ).fetchall()
        package = _json_object(row["payload_json"], "application payload")
        return {
            "application_id": row["application_id"],
            "lifecycle_state": row["lifecycle_state"],
            "revision": int(row["revision"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "external_submission_performed": bool(
                row["external_submission_performed"]
            ),
            "package": package,
            "operator_reviews": [
                _json_object(item["review_json"], "operator review")
                for item in review_rows
            ],
            "audit_events": [
                {
                    "event_id": item["event_id"],
                    "created_at": item["created_at"],
                    "event_type": item["event_type"],
                    "payload_digest": item["payload_digest"],
                    "metadata": _json_object(
                        item["metadata_json"],
                        "audit metadata",
                    ),
                    "previous_event_hash": item["previous_event_hash"],
                    "event_hash": item["event_hash"],
                }
                for item in audit_rows
            ],
        }

    def record_operator_review(
        self,
        application_id: str,
        *,
        expected_revision: int,
        review: Mapping[str, Any],
        reviewed_financial_findings: list[dict[str, str]],
    ) -> dict[str, Any]:
        self._ensure_migrated()
        review_value = dict(review)
        decision = str(review_value["decision"])
        state = {
            "approve_local_export": "LOCAL_EXPORT_APPROVED",
            "return_for_revision": "REVISION_REQUIRED",
        }.get(decision)
        if state is None:
            raise GrantApplicationStateError("Unsupported operator review decision.")

        with self.factory.transaction() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM grant_applications
                WHERE application_id = ?
                """,
                (application_id,),
            ).fetchone()
            if row is None:
                raise GrantApplicationNotFound(application_id)
            if int(row["revision"]) != expected_revision:
                raise GrantApplicationConflict(
                    f"Expected revision {expected_revision}, found {row['revision']}."
                )
            if row["lifecycle_state"] != "AUDITED_REVIEW_REQUIRED":
                raise GrantApplicationStateError(
                    "Operator review is allowed only for an audited draft."
                )
            if bool(row["external_submission_performed"]):
                raise GrantApplicationStateError(
                    "A local application cannot record an external submission."
                )

            created_at = _utc_now()
            next_revision = expected_revision + 1
            review_id = f"acgs_review_{uuid4().hex}"
            review_receipt = {
                **review_value,
                "review_id": review_id,
                "reviewed_at": created_at,
                "review_state": state,
                "source_verification_status": "operator_attested_reviewed",
                "reviewed_financial_findings": reviewed_financial_findings,
                "local_export_approved": state == "LOCAL_EXPORT_APPROVED",
                "phase5_submission_approved": False,
                "external_submission_performed": False,
                "review_disclaimer": (
                    "This operator review approves only a local review artifact. "
                    "It does not establish program eligibility or authorize "
                    "external submission."
                ),
            }
            package = _json_object(row["payload_json"], "application payload")
            source = dict(package.get("source_attribution", {}))
            source["operator_reviewed_source"] = {
                "program_name": review_value["program_name"],
                "source_guideline_url": review_value["source_guideline_url"],
                "source_version": review_value["source_version"],
                "source_reviewed_at": review_value["source_reviewed_at"],
                "source_verification_status": "operator_attested_reviewed",
                "current_program_confirmation_required": True,
            }
            package["source_attribution"] = source
            package["operator_review"] = review_receipt
            package["status"] = state
            lifecycle = list(package.get("lifecycle", []))
            lifecycle.append(state)
            package["lifecycle"] = lifecycle
            package_json = _canonical(package)
            review_json = _canonical(review_receipt)
            review_digest = _sha256(review_json)

            cursor = connection.execute(
                """
                UPDATE grant_applications
                SET
                    lifecycle_state = ?,
                    payload_json = ?,
                    revision = ?,
                    updated_at = ?
                WHERE application_id = ? AND revision = ?
                """,
                (
                    state,
                    package_json,
                    next_revision,
                    created_at,
                    application_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise GrantApplicationConflict(
                    "Application revision changed during operator review."
                )
            connection.execute(
                """
                INSERT INTO grant_operator_reviews(
                    review_id,
                    application_id,
                    application_revision,
                    created_at,
                    decision,
                    review_digest,
                    review_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    application_id,
                    next_revision,
                    created_at,
                    decision.upper(),
                    review_digest,
                    review_json,
                ),
            )
            self._append_audit_event(
                connection,
                application_id=application_id,
                event_type="grant_application.operator_review_recorded",
                metadata={
                    **_audit_metadata(package, state),
                    "review_id": review_id,
                    "review_decision": decision,
                },
            )
        return self.get_application(application_id)

    def local_export(self, application_id: str) -> dict[str, Any]:
        record = self.get_application(application_id)
        if record["lifecycle_state"] != "LOCAL_EXPORT_APPROVED":
            raise GrantApplicationStateError(
                "Local export requires an approved local operator review."
            )
        package = record["package"]
        review = package.get("operator_review")
        if not isinstance(review, dict) or not review.get("local_export_approved"):
            raise GrantApplicationStateError(
                "Local export requires a complete approval receipt."
            )
        return {
            "export_type": "ACGS_LOCAL_REVIEW_ARTIFACT",
            "application_id": record["application_id"],
            "revision": record["revision"],
            "created_at": record["created_at"],
            "exported_from_state": record["lifecycle_state"],
            "source_attribution": package.get("source_attribution", {}),
            "operator_review": review,
            "draft": package.get("draft", {}),
            "financial_review": package.get("financial_review", {}),
            "red_team_audit": package.get("red_team_audit", {}),
            "submission": package.get("submission", {}),
            "manual_handoff_notice": (
                "This is a local review artifact. It does not authorize or "
                "perform an external portal submission."
            ),
            "external_submission_performed": False,
            "credential_use_performed": False,
            "external_action_performed": False,
        }

    def _ensure_migrated(self) -> None:
        if self._migrated:
            return
        with self._migration_lock:
            if not self._migrated:
                self.migrator.apply_all()
                self._migrated = True

    def _append_audit_event(
        self,
        connection: Any,
        *,
        application_id: str,
        event_type: str,
        metadata: Mapping[str, Any],
    ) -> None:
        event_id = f"acgs_event_{uuid4().hex}"
        created_at = _utc_now()
        metadata_json = _canonical(dict(metadata))
        payload_digest = _sha256(metadata_json)
        previous = connection.execute(
            """
            SELECT event_hash
            FROM grant_audit_events
            WHERE event_hash IS NOT NULL
            ORDER BY rowid DESC
            LIMIT 1
            """
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else None
        event_hash = _sha256(
            "|".join(
                [
                    event_id,
                    application_id,
                    event_type,
                    payload_digest,
                    previous_hash or "",
                    created_at,
                ]
            )
        )
        connection.execute(
            """
            INSERT INTO grant_audit_events(
                event_id,
                application_id,
                created_at,
                event_type,
                payload_digest,
                metadata_json,
                previous_event_hash,
                event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                application_id,
                created_at,
                event_type,
                payload_digest,
                metadata_json,
                previous_hash,
                event_hash,
            ),
        )


def _audit_metadata(
    package: Mapping[str, Any],
    lifecycle_state: str,
) -> dict[str, Any]:
    source = package.get("source_attribution")
    source_value = dict(source) if isinstance(source, Mapping) else {}
    draft = package.get("draft")
    draft_value = dict(draft) if isinstance(draft, Mapping) else {}
    return {
        "application_id": package.get("application_id"),
        "lifecycle_state": lifecycle_state,
        "source_attribution": {
            "portal_id": source_value.get("portal_id"),
            "official_portal_url": source_value.get("official_portal_url"),
            "provided_guideline_url": source_value.get(
                "provided_guideline_url"
            ),
            "source_verification_status": source_value.get(
                "source_verification_status"
            ),
            "operator_reviewed_source": source_value.get(
                "operator_reviewed_source"
            ),
        },
        "ai_use_disclosure_present": bool(
            str(draft_value.get("ai_use_disclosure", "")).strip()
        ),
        "external_action_performed": False,
    }


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _json_object(value: str, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise GrantApplicationStorageError(
            f"Persisted {label} is invalid JSON."
        ) from exc
    if not isinstance(parsed, dict):
        raise GrantApplicationStorageError(
            f"Persisted {label} must be a JSON object."
        )
    return parsed


def _sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
