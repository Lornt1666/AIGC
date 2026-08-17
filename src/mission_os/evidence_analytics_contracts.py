"""Fail-closed contracts for Ω Mission OS Increment 12 Slice A.

This module validates only schemas, metric definitions, deterministic JSON, fixtures,
and non-authorizing evidence semantics. It does not read canonical databases, build an
analytics store, call providers, mutate state, or authorize actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_FILES = {
    "run_envelope": "analytics_run_envelope.schema.json",
    "lineage_reference": "analytics_lineage_reference.schema.json",
    "entity_transition": "analytics_entity_transition.schema.json",
    "metric_definition": "analytics_metric_definition.schema.json",
    "metric_observation": "analytics_metric_observation.schema.json",
    "data_quality_finding": "analytics_data_quality_finding.schema.json",
}

FORBIDDEN_NORMALIZED_KEYS = {
    "apikey", "apitoken", "accesstoken", "refreshtoken", "oauthtoken", "token", "password",
    "passwd", "secret", "privatekey", "authorization", "cookie",
    "rawproviderpayload", "providerpayload", "proposalbody", "employermessage",
    "personalemail", "emailaddress", "phonenumber", "homeaddress", "fullname",
    "socialinsurancenumber", "sin", "ssn",
}
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PRIVATE_KEY_MARKER = "-----BEGIN PRIVATE KEY-----"
ACTIVE_AUTHORIZATION_STATES = {"ACTIVE", "PENDING", "ACTIVE_PENDING", "AUTHORIZED"}


class AnalyticsContractError(ValueError):
    """A deterministic, code-bearing validation failure."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AnalyticsContractError("DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except AnalyticsContractError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalyticsContractError("JSON_LOAD_FAILED", f"{path}: {exc}") from exc


def canonical_bytes(value: Any) -> bytes:
    """Canonical JSON subset: UTF-8, sorted keys, no insignificant whitespace or NaN."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AnalyticsContractError("CANONICALIZATION_FAILED", str(exc)) from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.casefold())


def enforce_data_minimization(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = _normalize_key(str(key))
            if normalized in FORBIDDEN_NORMALIZED_KEYS:
                raise AnalyticsContractError("PRIVACY_FORBIDDEN_KEY", f"{path}.{key}")
            enforce_data_minimization(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            enforce_data_minimization(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if PRIVATE_KEY_MARKER in value:
            raise AnalyticsContractError("PRIVACY_PRIVATE_KEY_MATERIAL", path)
        if EMAIL_RE.search(value):
            raise AnalyticsContractError("PRIVACY_EMAIL_VALUE", path)


def _parse_time(raw: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnalyticsContractError("TIMESTAMP_INVALID", field) from exc
    if parsed.tzinfo is None:
        raise AnalyticsContractError("TIMESTAMP_MISSING_TIMEZONE", field)
    return parsed.astimezone(timezone.utc)


def _schema(repo_root: Path, kind: str) -> dict[str, Any]:
    try:
        filename = SCHEMA_FILES[kind]
    except KeyError as exc:
        raise AnalyticsContractError("UNKNOWN_CONTRACT_KIND", kind) from exc
    return load_json(repo_root / "schemas" / filename)


def _schema_validate(repo_root: Path, kind: str, document: Any) -> None:
    validator = Draft202012Validator(_schema(repo_root, kind), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    if errors:
        first = errors[0]
        location = "$" + "".join(f"[{part!r}]" for part in first.absolute_path)
        raise AnalyticsContractError("SCHEMA_VALIDATION_FAILED", f"{kind} {location}: {first.message}")


def validate_document(
    repo_root: Path,
    kind: str,
    document: Any,
    *,
    now: datetime | None = None,
) -> None:
    enforce_data_minimization(document)
    _schema_validate(repo_root, kind, document)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    if kind == "run_envelope":
        started = _parse_time(document["started_at"], "started_at")
        finished = _parse_time(document["finished_at"], "finished_at")
        if finished < started:
            raise AnalyticsContractError("TIME_ORDER_INVALID", "finished_at precedes started_at")
        if started > now + timedelta(minutes=5) or finished > now + timedelta(minutes=5):
            raise AnalyticsContractError("TIMESTAMP_IMPLAUSIBLY_FUTURE", "run timestamp exceeds five-minute tolerance")
        counts = document["record_counts"]
        if counts["accepted"] + counts["rejected"] != counts["read"]:
            raise AnalyticsContractError("RECORD_COUNTS_INCONSISTENT", "accepted + rejected must equal read")
        for source in document["source_inventory"]:
            if source["records_accepted"] + source["records_rejected"] != source["records_read"]:
                raise AnalyticsContractError("SOURCE_RECORD_COUNTS_INCONSISTENT", source["source_identifier"])
            if source["source_status"] == "UNAVAILABLE" and (
                source["freshness_state"] == "FRESH" or document["overall_evidence_state"] == "PASS"
            ):
                raise AnalyticsContractError(
                    "UNAVAILABLE_SOURCE_REPORTED_HEALTHY", source["source_identifier"]
                )
            if source["freshness_state"] == "STALE" and document["overall_evidence_state"] == "PASS":
                raise AnalyticsContractError("STALE_SOURCE_REPORTED_PASS", source["source_identifier"])

    elif kind == "lineage_reference":
        observed = _parse_time(document["observed_at"], "observed_at")
        if observed > now + timedelta(minutes=5):
            raise AnalyticsContractError("TIMESTAMP_IMPLAUSIBLY_FUTURE", "observed_at")
        age_seconds = max(Decimal("0"), Decimal(str((now - observed).total_seconds())))
        expectation = Decimal(document["freshness_expectation_seconds"])
        if (
            document["source_status"] == "UNAVAILABLE"
            and document["freshness_state"] != "UNAVAILABLE"
        ):
            raise AnalyticsContractError("UNAVAILABLE_SOURCE_REPORTED_HEALTHY", document["lineage_id"])
        if age_seconds > expectation and document["freshness_state"] == "FRESH":
            raise AnalyticsContractError("STALE_SOURCE_REPORTED_FRESH", document["lineage_id"])

    elif kind == "entity_transition":
        _parse_time(document["transition_timestamp"], "transition_timestamp")
        if document["contradictory"] and document["validity_state"] != "CONTRADICTORY":
            raise AnalyticsContractError("CONTRADICTION_STATE_MISMATCH", document["transition_id"])
        if not document["contradictory"] and document["validity_state"] == "CONTRADICTORY":
            raise AnalyticsContractError("CONTRADICTION_STATE_MISMATCH", document["transition_id"])
        if document["entity_type"] == "AUTHORIZATION" and document["expiry_state"] == "EXPIRED":
            if document["new_state"].upper() in ACTIVE_AUTHORIZATION_STATES:
                raise AnalyticsContractError("EXPIRED_AUTHORIZATION_ACTIVE", document["transition_id"])
        if document["validity_state"] != "VALID" and document["evidence_state"] == "PASS":
            raise AnalyticsContractError("INVALID_TRANSITION_REPORTED_PASS", document["transition_id"])

    elif kind == "metric_definition":
        if not document["denominator"]["expression"].strip():
            raise AnalyticsContractError("DENOMINATOR_UNDEFINED", document["metric_id"])
        if document["metric_id"] == "AIGC-METRIC-DQC":
            if document["activation_state"] != "INACTIVE_SAMPLE_INSUFFICIENT":
                raise AnalyticsContractError("DQC_ACTIVATED_WITHOUT_EVIDENCE", document["metric_id"])
            if document["minimum_sample_size"] <= 0:
                raise AnalyticsContractError("DQC_SAMPLE_POLICY_MISSING", document["metric_id"])
        if document["autonomous_behavior_change_allowed"] is not False:
            raise AnalyticsContractError("AUTONOMOUS_CHANGE_AUTHORITY_PRESENT", document["metric_id"])

    elif kind == "metric_observation":
        start = _parse_time(document["reporting_window"]["start"], "reporting_window.start")
        end = _parse_time(document["reporting_window"]["end"], "reporting_window.end")
        if end <= start:
            raise AnalyticsContractError("TIME_ORDER_INVALID", "reporting window")
        try:
            denominator = Decimal(document["denominator"])
            Decimal(document["numerator"])
            Decimal(document["computed_value"])
        except InvalidOperation as exc:
            raise AnalyticsContractError("DECIMAL_INVALID", document["observation_id"]) from exc
        if denominator == 0 and document["evidence_state"] not in {"INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE"}:
            raise AnalyticsContractError("ZERO_DENOMINATOR_REPORTED_VALUE", document["observation_id"])
        lineage_digests = {item["source_sha256"] for item in document["source_lineage"]}
        if lineage_digests != set(document["source_digests"]):
            raise AnalyticsContractError("SOURCE_DIGEST_SET_MISMATCH", document["observation_id"])
        if document["freshness_state"] in {"STALE", "UNAVAILABLE"} and document["evidence_state"] == "PASS":
            raise AnalyticsContractError("NONFRESH_OBSERVATION_REPORTED_PASS", document["observation_id"])
        if document["evidence_basis"] == "STRUCTURAL_ONLY" and document["claim_classification"] in {
            "OUTCOME", "PRODUCTION_PROOF"
        }:
            raise AnalyticsContractError("STRUCTURAL_EVIDENCE_OVERCLAIM", document["observation_id"])

    elif kind == "data_quality_finding":
        try:
            confidence = Decimal(document["confidence"])
        except InvalidOperation as exc:
            raise AnalyticsContractError("CONFIDENCE_INVALID", document["finding_id"]) from exc
        if confidence < 0 or confidence > 1:
            raise AnalyticsContractError("CONFIDENCE_OUT_OF_RANGE", document["finding_id"])
        if document["severity"] == "BLOCKER" and not document["blocking"]:
            raise AnalyticsContractError("BLOCKER_NOT_MARKED_BLOCKING", document["finding_id"])
        if document["blocking"] and document["status"] in {"OPEN", "REMEDIATED"} and document["evidence_state"] == "PASS":
            raise AnalyticsContractError("BLOCKING_FINDING_REPORTED_PASS", document["finding_id"])


def validate_catalog(repo_root: Path, catalog: dict[str, Any]) -> None:
    enforce_data_minimization(catalog)
    required = {
        "schema_version", "catalog_id", "catalog_version", "catalog_status",
        "generated_at", "production_activation_authorized",
        "external_provider_action_authorized", "autonomous_behavior_change_allowed",
        "metrics", "catalog_content_sha256",
    }
    if set(catalog) != required:
        raise AnalyticsContractError("CATALOG_FIELDS_INVALID", repr(sorted(set(catalog) ^ required)))
    if catalog["production_activation_authorized"] is not False:
        raise AnalyticsContractError("PRODUCTION_AUTHORITY_PRESENT", catalog["catalog_id"])
    if catalog["external_provider_action_authorized"] is not False:
        raise AnalyticsContractError("PROVIDER_AUTHORITY_PRESENT", catalog["catalog_id"])
    if catalog["autonomous_behavior_change_allowed"] is not False:
        raise AnalyticsContractError("AUTONOMOUS_CHANGE_AUTHORITY_PRESENT", catalog["catalog_id"])
    digest_input = dict(catalog)
    expected_digest = digest_input.pop("catalog_content_sha256")
    if canonical_sha256(digest_input) != expected_digest:
        raise AnalyticsContractError("CATALOG_DIGEST_MISMATCH", catalog["catalog_id"])
    seen: set[tuple[str, str]] = set()
    for item in catalog["metrics"]:
        validate_document(repo_root, "metric_definition", item)
        identity = (item["metric_id"], item["version"])
        if identity in seen:
            raise AnalyticsContractError("DUPLICATE_METRIC_ID_VERSION", repr(identity))
        seen.add(identity)
    required_ids = {"AIGC-METRIC-GPR", "AIGC-METRIC-ECF", "AIGC-METRIC-DQC"}
    if {item["metric_id"] for item in catalog["metrics"]} != required_ids:
        raise AnalyticsContractError("CATALOG_REQUIRED_METRICS_MISMATCH", catalog["catalog_id"])


def _observation_grain(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item["metric_id"], item["metric_version"],
        item["reporting_window"]["start"], item["reporting_window"]["end"],
        canonical_sha256(item["dimensions"]),
    )


def validate_observation_set(repo_root: Path, observations: Iterable[dict[str, Any]], *, now: datetime) -> None:
    seen: set[tuple[Any, ...]] = set()
    for item in observations:
        validate_document(repo_root, "metric_observation", item, now=now)
        grain = _observation_grain(item)
        if grain in seen:
            raise AnalyticsContractError("DUPLICATE_DECLARED_GRAIN", repr(grain))
        seen.add(grain)


def derive_aggregate_state(findings: Iterable[dict[str, Any]]) -> str:
    findings = list(findings)
    for item in findings:
        if item["blocking"] and item["status"] != "VERIFIED":
            return "FAIL"
    if any(item["evidence_state"] == "UNAVAILABLE" for item in findings):
        return "INSUFFICIENT_EVIDENCE"
    if any(item["evidence_state"] == "STALE" for item in findings):
        return "STALE"
    if any(item["evidence_state"] == "FAIL" for item in findings):
        return "FAIL"
    return "PASS"


def validate_aggregate_projection(repo_root: Path, projection: dict[str, Any], *, now: datetime) -> None:
    enforce_data_minimization(projection)
    for finding in projection["findings"]:
        validate_document(repo_root, "data_quality_finding", finding, now=now)
    derived = derive_aggregate_state(projection["findings"])
    if projection["claimed_aggregate_state"] != derived:
        if derived == "FAIL" and any(item["blocking"] for item in projection["findings"]):
            raise AnalyticsContractError("BLOCKING_FINDING_HIDDEN", f"claimed={projection['claimed_aggregate_state']}")
        raise AnalyticsContractError("AGGREGATE_STATE_MISMATCH", f"claimed={projection['claimed_aggregate_state']} derived={derived}")


def validate_fixture_manifest(repo_root: Path) -> dict[str, Any]:
    fixture_root = repo_root / "tests" / "fixtures" / "analytics"
    manifest = load_json(fixture_root / "manifest.json")
    now = _parse_time(manifest["fixed_validation_now"], "fixed_validation_now")
    validated = 0
    expected_failures = 0
    for entry in manifest["valid"]:
        validate_document(repo_root, entry["kind"], load_json(fixture_root / entry["path"]), now=now)
        validated += 1
    for entry in manifest["negative"]:
        payload = load_json(fixture_root / entry["path"])
        try:
            if entry["kind"] == "observation_set":
                validate_observation_set(repo_root, payload["observations"], now=now)
            elif entry["kind"] == "aggregate_projection":
                validate_aggregate_projection(repo_root, payload, now=now)
            else:
                validate_document(repo_root, entry["kind"], payload, now=now)
        except AnalyticsContractError as exc:
            if exc.code != entry["expected_error_code"]:
                raise AnalyticsContractError(
                    "NEGATIVE_FIXTURE_WRONG_ERROR",
                    f"{entry['path']}: expected {entry['expected_error_code']} got {exc.code}",
                ) from exc
            expected_failures += 1
        else:
            raise AnalyticsContractError("NEGATIVE_FIXTURE_ACCEPTED", entry["path"])
    return {
        "valid_fixtures": validated,
        "negative_fixtures": expected_failures,
        "external_action_performed": False,
        "canonical_state_mutated": False,
        "production_activation_authorized": False,
    }


def validate_repository(repo_root: Path) -> dict[str, Any]:
    for kind in SCHEMA_FILES:
        Draft202012Validator.check_schema(_schema(repo_root, kind))
    catalog = load_json(repo_root / "config" / "analytics_metric_catalog.json")
    validate_catalog(repo_root, catalog)
    receipt = validate_fixture_manifest(repo_root)
    receipt.update(
        {
            "schema_count": len(SCHEMA_FILES),
            "metric_count": len(catalog["metrics"]),
            "catalog_version": catalog["catalog_version"],
            "catalog_content_sha256": catalog["catalog_content_sha256"],
        }
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        receipt = validate_repository(args.repo_root.resolve())
    except AnalyticsContractError as exc:
        print(json.dumps({"status": "FAIL", "error_code": exc.code, "detail": exc.detail}, sort_keys=True))
        return 1
    print(json.dumps({"status": "PASS", **receipt}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
