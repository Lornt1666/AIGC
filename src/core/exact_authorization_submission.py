from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKET_PATH = ROOT / "config" / "exact_identifier_submission_packet.json"
DEFAULT_PACKET_SCHEMA = ROOT / "schemas" / "exact_identifier_submission_packet.schema.json"
DEFAULT_STAGING_SCHEMA = ROOT / "schemas" / "staging_identity_authorization_receipt.schema.json"
DEFAULT_PRODUCTION_SCHEMA = ROOT / "schemas" / "production_deployment_authorization_receipt.schema.json"
DEFAULT_EVALUATION_SCHEMA = ROOT / "schemas" / "exact_authorization_submission_evaluation.schema.json"
_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_MAX_PACKET_LIFETIME_HOURS = 168


class ExactAuthorizationSubmissionError(ValueError):
    """Raised when an identifier or authorization packet violates its contract."""


@dataclass(frozen=True)
class ExactAuthorizationSubmissionEvaluation:
    receipt: dict[str, Any]
    identifier_packet: dict[str, Any]

    @property
    def staging_identity_effective(self) -> bool:
        return bool(self.receipt["staging_identity_authorization_effective"])

    @property
    def production_deployment_effective(self) -> bool:
        return bool(self.receipt["production_deployment_authorization_effective"])


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def canonical_digest(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_time(value: object) -> datetime:
    try:
        return _utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError as exc:
        raise ExactAuthorizationSubmissionError(
            "Authorization or packet time is invalid"
        ) from exc


def _strict_validate(schema_path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExactAuthorizationSubmissionError(
            f"Unable to load authorization schema: {schema_path.name}"
        ) from exc
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(dict(value)),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        messages: list[str] = []
        for error in errors[:10]:
            location = "$"
            if error.absolute_path:
                location += "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error.absolute_path
                )
            messages.append(f"{location}: {error.message}")
        raise ExactAuthorizationSubmissionError(
            f"{schema_path.name} validation failed: {'; '.join(messages)}"
        )
    return dict(value)


def load_identifier_packet(
    path: str | Path = DEFAULT_PACKET_PATH,
) -> dict[str, Any]:
    """Load the committed packet template or a separately supplied submission."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExactAuthorizationSubmissionError(
            "Unable to load exact identifier submission packet"
        ) from exc
    if not isinstance(value, dict):
        raise ExactAuthorizationSubmissionError(
            "Exact identifier submission packet must be an object"
        )
    return _strict_validate(DEFAULT_PACKET_SCHEMA, value)


def _time_reasons(
    receipt: Mapping[str, Any],
    *,
    now: datetime,
    maximum_hours: int,
    prefix: str,
) -> list[str]:
    reasons: list[str] = []
    issued_at = _parse_time(receipt["issued_at"])
    expires_at = _parse_time(receipt["expires_at"])
    if expires_at <= issued_at:
        reasons.append(f"{prefix}_LIFETIME_INVALID")
    if issued_at > now:
        reasons.append(f"{prefix}_FUTURE_DATED")
    if now >= expires_at:
        reasons.append(f"{prefix}_EXPIRED")
    lifetime_hours = (expires_at - issued_at).total_seconds() / 3600
    if lifetime_hours > maximum_hours:
        reasons.append(f"{prefix}_TTL_EXCEEDED")
    return reasons


def _packet_lifecycle_reasons(
    packet: Mapping[str, Any],
    *,
    now: datetime,
) -> list[str]:
    if packet["artifact_kind"] == "TEMPLATE":
        return ["IDENTIFIER_PACKET_TEMPLATE_ONLY"]

    lifecycle = dict(packet["lifecycle"])
    created_at = _parse_time(lifecycle["created_at"])
    expires_at = _parse_time(lifecycle["expires_at"])
    reasons: list[str] = []

    if expires_at <= created_at:
        reasons.append("IDENTIFIER_PACKET_LIFETIME_INVALID")
    if created_at > now:
        reasons.append("IDENTIFIER_PACKET_FUTURE_DATED")
    if now >= expires_at:
        reasons.append("IDENTIFIER_PACKET_EXPIRED")
    lifetime_hours = (expires_at - created_at).total_seconds() / 3600
    if lifetime_hours > _MAX_PACKET_LIFETIME_HOURS:
        reasons.append("IDENTIFIER_PACKET_TTL_EXCEEDED")
    if lifecycle["revoked"] is True:
        reasons.append("IDENTIFIER_PACKET_REVOKED")
    return list(dict.fromkeys(reasons))


def _staging_target_projection(packet: Mapping[str, Any]) -> dict[str, Any]:
    return dict(packet["staging_identity"])


def _production_target_projection(packet: Mapping[str, Any]) -> dict[str, Any]:
    production = dict(packet["production_deployment"])
    return {
        "release_id": production["release_id"],
        "release_candidate_digest": production["release_candidate_digest"],
        "readiness_truth_digest": production["readiness_truth_digest"],
        "release_artifact_digest": production["release_artifact_digest"],
        "production_project_reference": production["project_reference"],
        "deployment_workload_identity_reference": production[
            "deployment_workload_identity_reference"
        ],
        "domain_reference": production["domain_reference"],
        "database_reference": production["database_reference"],
        "remote_state_reference": production["remote_state_reference"],
        "production_release_gate_receipt_id": production[
            "production_release_gate_receipt_id"
        ],
    }


def evaluate_exact_authorization_submission(
    *,
    identifier_packet: Mapping[str, Any],
    exact_revision: str | None,
    staging_identity_receipt: Mapping[str, Any] | None = None,
    production_deployment_receipt: Mapping[str, Any] | None = None,
    readiness_report: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> ExactAuthorizationSubmissionEvaluation:
    packet = _strict_validate(DEFAULT_PACKET_SCHEMA, identifier_packet)
    current = _utc(now or datetime.now(timezone.utc))
    revision = (
        str(exact_revision)
        if exact_revision and _HEX40.fullmatch(str(exact_revision))
        else "unbound"
    )
    packet_hash = canonical_digest(packet)
    lifecycle_reasons = _packet_lifecycle_reasons(packet, now=current)
    lifecycle_active = (
        packet["artifact_kind"] == "SUBMISSION" and not lifecycle_reasons
    )
    revision_bound = revision != "unbound"

    lifecycle = dict(packet["lifecycle"])
    staging_consumed = (
        lifecycle["staging_consumption"]["status"] == "CONSUMED"
    )
    production_consumed = (
        lifecycle["production_consumption"]["status"] == "CONSUMED"
    )
    staging_packet_ready = (
        lifecycle_active
        and revision_bound
        and not staging_consumed
        and packet["staging_status"] == "READY_FOR_OPERATOR_REVIEW"
        and packet["unresolved_staging_identifiers"] == []
    )
    production_packet_ready = (
        lifecycle_active
        and revision_bound
        and not production_consumed
        and packet["production_status"] == "READY_FOR_OPERATOR_REVIEW"
        and packet["unresolved_production_identifiers"] == []
    )

    staging_reasons: list[str] = []
    staging_valid = False
    staging_value: dict[str, Any] | None = None
    if not staging_packet_ready:
        staging_reasons.append("STAGING_PACKET_NOT_READY")
    if staging_consumed:
        staging_reasons.append("STAGING_PACKET_ALREADY_CONSUMED")
    if not revision_bound:
        staging_reasons.append("EVALUATED_REVISION_UNBOUND")
    if staging_identity_receipt is None:
        staging_reasons.append("STAGING_IDENTITY_RECEIPT_MISSING")
    else:
        try:
            staging_value = _strict_validate(
                DEFAULT_STAGING_SCHEMA,
                staging_identity_receipt,
            )
        except ExactAuthorizationSubmissionError:
            staging_reasons.append("STAGING_IDENTITY_RECEIPT_INVALID")
        else:
            staging_valid = True
            if staging_value["exact_revision"] != revision:
                staging_reasons.append("STAGING_IDENTITY_REVISION_MISMATCH")
            if staging_value["identifier_packet_digest"] != packet_hash:
                staging_reasons.append("STAGING_IDENTITY_PACKET_DIGEST_MISMATCH")
            if staging_value["targets"] != _staging_target_projection(packet):
                staging_reasons.append("STAGING_IDENTITY_TARGET_MISMATCH")
            if staging_value["decision"] != "APPROVED":
                staging_reasons.append("STAGING_IDENTITY_OPERATOR_DENIED")
            staging_reasons.extend(
                _time_reasons(
                    staging_value,
                    now=current,
                    maximum_hours=4,
                    prefix="STAGING_IDENTITY_RECEIPT",
                )
            )
    staging_reasons = list(dict.fromkeys(staging_reasons))
    staging_effective = staging_valid and not staging_reasons

    report = dict(readiness_report or {})
    score = float(report.get("overall_score") or 0)
    blocking_gaps = sorted(str(item) for item in report.get("blocking_gaps") or [])
    production_ready_truth = bool(report.get("production_ready"))

    production_reasons: list[str] = []
    production_valid = False
    production_value: dict[str, Any] | None = None
    if not production_packet_ready:
        production_reasons.append("PRODUCTION_PACKET_NOT_READY")
    if production_consumed:
        production_reasons.append("PRODUCTION_PACKET_ALREADY_CONSUMED")
    if not revision_bound:
        production_reasons.append("EVALUATED_REVISION_UNBOUND")
    if production_deployment_receipt is None:
        production_reasons.append("PRODUCTION_DEPLOYMENT_RECEIPT_MISSING")
    else:
        try:
            production_value = _strict_validate(
                DEFAULT_PRODUCTION_SCHEMA,
                production_deployment_receipt,
            )
        except ExactAuthorizationSubmissionError:
            production_reasons.append("PRODUCTION_DEPLOYMENT_RECEIPT_INVALID")
        else:
            production_valid = True
            if production_value["exact_revision"] != revision:
                production_reasons.append("PRODUCTION_DEPLOYMENT_REVISION_MISMATCH")
            if production_value["identifier_packet_digest"] != packet_hash:
                production_reasons.append(
                    "PRODUCTION_DEPLOYMENT_PACKET_DIGEST_MISMATCH"
                )
            expected = _production_target_projection(packet)
            for key, value in expected.items():
                if production_value.get(key) != value:
                    production_reasons.append(
                        "PRODUCTION_DEPLOYMENT_TARGET_MISMATCH"
                    )
                    break
            if production_value["decision"] != "APPROVED":
                production_reasons.append("PRODUCTION_DEPLOYMENT_OPERATOR_DENIED")
            if production_value["production_release_gate_result"] != "PERMIT":
                production_reasons.append("PRODUCTION_RELEASE_GATE_NOT_PERMITTED")
            production_reasons.extend(
                _time_reasons(
                    production_value,
                    now=current,
                    maximum_hours=1,
                    prefix="PRODUCTION_DEPLOYMENT_RECEIPT",
                )
            )

            if not report:
                production_reasons.append("READINESS_REPORT_MISSING")
            else:
                if report.get("source_revision") != revision:
                    production_reasons.append("READINESS_REVISION_MISMATCH")
                threshold = max(
                    90.0,
                    float(report.get("production_readiness_threshold") or 0),
                )
                if score < threshold:
                    production_reasons.append("READINESS_SCORE_BELOW_THRESHOLD")
                if blocking_gaps:
                    production_reasons.append("BLOCKING_GAPS_PRESENT")
                if not production_ready_truth:
                    production_reasons.append("READINESS_NOT_PRODUCTION_READY")

    production_reasons = list(dict.fromkeys(production_reasons))
    production_effective = production_valid and not production_reasons

    evaluation_material = "|".join(
        (
            revision,
            packet_hash,
            ",".join(lifecycle_reasons),
            packet["staging_status"],
            str(staging_value.get("receipt_id") if staging_value else ""),
            ",".join(staging_reasons),
            packet["production_status"],
            str(production_value.get("receipt_id") if production_value else ""),
            ",".join(production_reasons),
            f"{score:.4f}",
            ",".join(blocking_gaps),
        )
    )
    receipt = {
        "contract_id": "AIGC-EXACT-AUTHORIZATION-SUBMISSION-EVALUATION-001",
        "contract_version": "1.1.0",
        "evaluation_id": "EAS-"
        + sha256(evaluation_material.encode("utf-8")).hexdigest()[:24].upper(),
        "evaluated_revision": revision,
        "identifier_packet_digest": packet_hash,
        "artifact_kind": packet["artifact_kind"],
        "packet_id": packet["packet_id"],
        "lifecycle_active": lifecycle_active,
        "lifecycle_reason_codes": lifecycle_reasons,
        "staging_packet_status": packet["staging_status"],
        "staging_packet_ready_for_review": staging_packet_ready,
        "staging_identity_receipt_present": staging_identity_receipt is not None,
        "staging_identity_authorization_effective": staging_effective,
        "staging_identity_reason_codes": staging_reasons,
        "production_packet_status": packet["production_status"],
        "production_packet_ready_for_review": production_packet_ready,
        "production_deployment_receipt_present": (
            production_deployment_receipt is not None
        ),
        "production_deployment_authorization_effective": production_effective,
        "production_deployment_reason_codes": production_reasons,
        "readiness_score": score,
        "production_ready": production_ready_truth,
        "blocking_gaps": blocking_gaps,
        "evaluated_at": current.isoformat(),
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "external_action_performed": False,
    }
    receipt = _strict_validate(DEFAULT_EVALUATION_SCHEMA, receipt)
    return ExactAuthorizationSubmissionEvaluation(
        receipt=receipt,
        identifier_packet=packet,
    )
