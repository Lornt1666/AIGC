from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sqlite3
import stat
import time
import uuid
from contextlib import closing
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from jsonschema.exceptions import SchemaError

from .cloud_advancement_loop import (
    CloudAdvancementError,
    DEFAULT_EXECUTION_RECEIPT_SCHEMA_PATH,
    _assert_safe_evidence,
    _safe_input_path,
    _safe_runtime_path,
    _strict_validate,
    canonical_digest,
    canonical_json,
    isoformat,
    load_program,
    parse_datetime,
    repository_revision_state,
    utc_now,
)


DEFAULT_ASSURANCE_CONFIG_PATH = Path(
    "config/cloud_advancement_assurance.json"
)
DEFAULT_ASSURANCE_SCHEMA_PATH = Path(
    "schemas/cloud_advancement_assurance.schema.json"
)
DEFAULT_VERIFICATION_RECEIPT_SCHEMA_PATH = Path(
    "schemas/cloud_advancement_verification_receipt.schema.json"
)
ASSURANCE_EVENT_TYPES = {
    "memory_recorded",
    "metric_evaluated",
}
DECIMAL_PATTERN = re.compile(
    r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$"
)
MEMORY_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._/-]{2,127}$")
METRIC_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._/-]{2,127}$")
RUN_ID_PATTERN = re.compile(r"^CLOUD-RUN-CLD-[0-9]{3}-[A-F0-9]{12}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$"
)
STABLE_TOKEN_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._:/_-]{0,127}$"
)
ACTOR_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:/-]{2,127}$")
DIGEST_PATTERN = re.compile(r"^[a-f0-9]{64}$")
PERSON_NAME_TOKEN_PATTERN = re.compile(r"^[a-z]{2,32}\.[a-z]{2,32}$")
MAX_ASSURANCE_JSON_BYTES = 3 * 1024 * 1024
ALLOWED_MEMORY_SUBJECT_NAMESPACES = {
    "action",
    "aigc",
    "ci",
    "cloud",
    "connector",
    "database",
    "deployment",
    "github",
    "governance",
    "identity",
    "infrastructure",
    "metric",
    "program",
    "release",
    "repository",
    "run",
    "runtime",
    "security",
    "terraform",
    "workflow",
}
SENSITIVE_OPERATIONAL_TOKEN_COMPONENTS = {
    "account",
    "authorization",
    "card",
    "contact",
    "cookie",
    "credential",
    "credentials",
    "email",
    "iban",
    "name",
    "otp",
    "passwd",
    "password",
    "payment",
    "person",
    "phone",
    "pin",
    "secret",
    "secrets",
    "sin",
    "ssn",
    "token",
    "tokens",
}
ASSURANCE_SENSITIVE_PATTERNS = [
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    re.compile(r"\b\d{3}[- ]?\d{3}[- ]?\d{3}\b"),
    re.compile(r"\b\d{6,8}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    re.compile(r"\b[A-Z]\d[A-Z][ -]?\d[A-Z]\d\b", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b"),
    re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
]
NON_TEXT_ASSURANCE_FIELDS = {
    "absolute_error",
    "absolute_tolerance",
    "accuracy_score",
    "actual",
    "confidence",
    "created_at",
    "effective_tolerance",
    "event_id",
    "expected",
    "expires_at",
    "observed_at",
    "relative_error",
    "relative_tolerance",
    "salience",
    "sha256",
    "source_revision",
    "supersedes_event_id",
    "value_sha256",
}
Clock = Callable[[], int]


def _read_bounded_file(path: Path, max_bytes: int, label: str) -> bytes:
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise CloudAdvancementError(f"{label} must be a regular file.")
            if before.st_size < 1 or before.st_size > max_bytes:
                raise CloudAdvancementError(
                    f"{label} is empty or exceeds its byte limit."
                )
            data = stream.read(max_bytes + 1)
            after = os.fstat(stream.fileno())
    except CloudAdvancementError:
        raise
    except OSError as exc:
        raise CloudAdvancementError(f"{label} could not be read safely.") from exc
    if (
        len(data) != before.st_size
        or len(data) > max_bytes
        or after.st_size != before.st_size
    ):
        raise CloudAdvancementError(f"{label} changed while it was read.")
    return data


def _decode_json_object(data: bytes, path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CloudAdvancementError(f"Invalid UTF-8 JSON at {path}.") from exc
    if not isinstance(payload, dict):
        raise CloudAdvancementError(f"Expected a JSON object at {path}.")
    return payload


def _load_assurance_json_object(path: Path) -> dict[str, Any]:
    return _decode_json_object(
        _read_bounded_file(
            path,
            MAX_ASSURANCE_JSON_BYTES,
            f"Assurance JSON file {path}",
        ),
        path,
    )


def _strict_assurance_validate(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> None:
    try:
        _strict_validate(payload, schema)
    except SchemaError as exc:
        raise CloudAdvancementError(
            "Cloud assurance schema is invalid."
        ) from exc


def _validate_execution_receipt_bytes(
    project_root: Path,
    receipt_path: Path,
    data: bytes,
) -> dict[str, Any]:
    root = project_root.resolve()
    receipt = _decode_json_object(data, receipt_path)
    schema_path = _safe_input_path(
        root,
        DEFAULT_EXECUTION_RECEIPT_SCHEMA_PATH,
        "cloud advancement execution receipt schema",
    )
    schema = _load_assurance_json_object(schema_path)
    _strict_assurance_validate(receipt, schema)
    digest_basis = dict(receipt)
    recorded_digest = str(digest_basis.pop("receipt_digest", ""))
    if recorded_digest != canonical_digest(digest_basis):
        raise CloudAdvancementError(
            "Cloud advancement execution receipt digest is invalid."
        )
    return receipt


def _validate_operational_token(
    value: str,
    label: str,
    *,
    reject_name_shape: bool = False,
) -> None:
    components = {
        component
        for component in re.split(r"[._:/-]+", value.casefold())
        if component
    }
    if components & SENSITIVE_OPERATIONAL_TOKEN_COMPONENTS:
        raise CloudAdvancementError(
            f"{label} contains a prohibited sensitive semantic."
        )
    compact = value.casefold()
    mixed_compact = (
        len(compact) >= 16
        and compact.isalnum()
        and any(character.isalpha() for character in compact)
        and any(character.isdigit() for character in compact)
        and len(set(compact)) >= 8
    )
    opaque_compact = (
        len(compact) >= 24
        and compact.isalnum()
        and len(set(compact)) >= 12
    )
    if mixed_compact or opaque_compact:
        raise CloudAdvancementError(
            f"{label} resembles an opaque credential or identifier."
        )
    if reject_name_shape and PERSON_NAME_TOKEN_PATTERN.fullmatch(value):
        raise CloudAdvancementError(
            f"{label} resembles a personal name."
        )


def load_assurance_config(
    project_root: Path,
    config_path: Path | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    config_file = _safe_input_path(
        root,
        config_path or DEFAULT_ASSURANCE_CONFIG_PATH,
        "cloud advancement assurance config",
    )
    schema_file = _safe_input_path(
        root,
        schema_path or DEFAULT_ASSURANCE_SCHEMA_PATH,
        "cloud advancement assurance schema",
    )
    payload = _load_assurance_json_object(config_file)
    schema = _load_assurance_json_object(schema_file)
    _strict_assurance_validate(payload, schema)
    validate_assurance_config(payload)
    return payload


def validate_assurance_config(config: Mapping[str, Any]) -> None:
    quantitative = dict(config["quantitative_accuracy"])
    memory = dict(config["working_memory"])
    performance = dict(config["performance"])
    state = dict(config["state"])
    governance = dict(config["governance"])
    verification = dict(config["verification"])

    minimum_confidence = parse_decimal(
        quantitative["minimum_confidence"],
        "minimum quantitative confidence",
    )
    maximum_relative_tolerance = parse_decimal(
        quantitative["maximum_relative_tolerance"],
        "maximum relative tolerance",
    )
    minimum_recall_confidence = parse_decimal(
        memory["minimum_recall_confidence"],
        "minimum recall confidence",
    )
    for label, value in {
        "minimum quantitative confidence": minimum_confidence,
        "maximum relative tolerance": maximum_relative_tolerance,
        "minimum recall confidence": minimum_recall_confidence,
    }.items():
        if value < 0 or value > 1:
            raise CloudAdvancementError(f"{label} must be within 0..1.")

    if int(memory["minimum_active_entries"]) > int(
        memory["max_active_entries"]
    ):
        raise CloudAdvancementError(
            "Minimum working-memory entries exceed capacity."
        )
    if int(memory["default_ttl_hours"]) > int(memory["max_ttl_hours"]):
        raise CloudAdvancementError(
            "Default working-memory TTL exceeds the maximum TTL."
        )
    if int(memory["default_recall_limit"]) > int(
        memory["max_recall_limit"]
    ):
        raise CloudAdvancementError(
            "Default recall limit exceeds the maximum recall limit."
        )
    if int(state["max_total_events"]) < int(memory["max_active_entries"]):
        raise CloudAdvancementError(
            "Assurance event capacity is below working-memory capacity."
        )
    if int(memory["max_recall_bytes"]) > int(
        memory["max_active_bytes_per_scope"]
    ):
        raise CloudAdvancementError(
            "Working-memory recall bytes exceed the per-scope budget."
        )
    definitions = list(quantitative["metric_definitions"])
    metric_ids = [str(item["metric_id"]) for item in definitions]
    if len(metric_ids) != len(set(metric_ids)):
        raise CloudAdvancementError(
            "Quantitative metric definitions must have unique identifiers."
        )
    if int(quantitative["minimum_distinct_metrics"]) != len(definitions):
        raise CloudAdvancementError(
            "Every defined quantitative metric must be required."
        )
    for definition in definitions:
        if definition["unit"] not in quantitative["allowed_units"]:
            raise CloudAdvancementError(
                "A quantitative metric definition uses an unknown unit."
            )
        if definition["measurement_mode"] != "exact":
            raise CloudAdvancementError(
                "The v1 quantitative contract supports exact metrics only."
            )
        if (
            parse_decimal(
                definition["absolute_tolerance"],
                "defined absolute tolerance",
            )
            != 0
            or parse_decimal(
                definition["relative_tolerance"],
                "defined relative tolerance",
            )
            != 0
        ):
            raise CloudAdvancementError(
                "Required exact metrics must use zero tolerance."
            )
        for field in (
            "expected",
            "absolute_tolerance",
            "relative_tolerance",
            "confidence",
        ):
            validate_metric_decimal_shape(
                str(definition[field]),
                f"defined metric {definition['metric_id']} {field}",
                quantitative,
            )
        expected = parse_decimal(
            definition["expected"],
            "defined metric expected value",
        )
        definition_confidence = parse_decimal(
            definition["confidence"],
            "defined metric confidence",
        )
        if definition_confidence < minimum_confidence:
            raise CloudAdvancementError(
                "Defined metric confidence is below the policy minimum."
            )
        absolute_tolerance = parse_decimal(
            definition["absolute_tolerance"],
            "defined metric absolute tolerance",
        )
        _validate_unit_domain(
            str(definition["unit"]),
            expected,
            expected,
            absolute_tolerance,
        )
    if (
        int(quantitative["precision_digits"]) != 50
        or int(quantitative["minimum_sample_size"]) != 1
        or int(performance["warmup_iterations"]) != 10
        or int(performance["sample_count"]) != 100
    ):
        raise CloudAdvancementError(
            "The v1 assurance receipt requires precision 50, exact sample "
            "size 1, 10 warmups, and 100 measured samples."
        )
    for name, value in performance["budgets_ms"].items():
        if parse_decimal(value, f"performance budget {name}") <= 0:
            raise CloudAdvancementError(
                f"Performance budget {name} must be greater than zero."
            )
    if not DIGEST_PATTERN.fullmatch(
        str(verification["trusted_loop_receipt_sha256"])
    ):
        raise CloudAdvancementError(
            "Trusted loop receipt must have a pinned SHA-256 digest."
        )
    for key in {
        "automation_can_self_approve",
        "automation_can_expand_scope",
        "accepted_history_mutation_allowed",
        "credential_access_allowed",
        "provider_resource_mutation_allowed",
        "external_action_performed",
    }:
        if governance[key] is not False:
            raise CloudAdvancementError(
                f"Cloud assurance governance control {key} is weakened."
            )


def parse_decimal(value: Any, label: str) -> Decimal:
    if not isinstance(value, str) or not DECIMAL_PATTERN.fullmatch(value):
        raise CloudAdvancementError(
            f"{label} must be a finite plain decimal string."
        )
    if len(value) > 80:
        raise CloudAdvancementError(f"{label} is too large.")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise CloudAdvancementError(
            f"{label} must be a finite decimal."
        ) from exc
    if not parsed.is_finite():
        raise CloudAdvancementError(f"{label} must be finite.")
    return parsed


def decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise CloudAdvancementError("Cannot serialize a non-finite decimal.")
    normalized = format(value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    if normalized in {"", "-0"}:
        return "0"
    return normalized


def nearest_rank(values: Sequence[int], percentile: Decimal) -> int:
    if not values:
        raise CloudAdvancementError(
            "A percentile requires one or more observations."
        )
    if percentile <= 0 or percentile > 1:
        raise CloudAdvancementError("Percentile must be within (0, 1].")
    ordered = sorted(int(value) for value in values)
    if any(value <= 0 for value in ordered):
        raise CloudAdvancementError(
            "Performance observations must be positive nanoseconds."
        )
    rank = int(
        (percentile * Decimal(len(ordered))).to_integral_value(
            rounding="ROUND_CEILING"
        )
    )
    return ordered[rank - 1]


def evaluate_quantitative_metric(
    assurance: Mapping[str, Any],
    *,
    metric_id: str,
    actual: str,
    expected: str,
    unit: str,
    absolute_tolerance: str,
    relative_tolerance: str,
    sample_size: int,
    confidence: str,
    source_refs: Sequence[str],
    source_sha256: Sequence[str],
    measurement_mode: str,
    observed_at: datetime,
    supersedes_event_id: str = "",
) -> dict[str, Any]:
    if not METRIC_ID_PATTERN.fullmatch(metric_id):
        raise CloudAdvancementError(
            "Metric identifier must use stable lowercase path syntax."
        )
    policy = dict(assurance["quantitative_accuracy"])
    unit = unit.strip()
    if unit not in policy["allowed_units"]:
        raise CloudAdvancementError(
            "Metric unit is not in the quantitative allowlist."
        )
    if measurement_mode not in policy["allowed_measurement_modes"]:
        raise CloudAdvancementError(
            "Metric measurement mode is not supported."
        )
    sources = normalize_sources(source_refs, source_sha256)
    actual_value = parse_decimal(actual, "metric actual")
    expected_value = parse_decimal(expected, "metric expected")
    absolute_value = parse_decimal(
        absolute_tolerance,
        "metric absolute tolerance",
    )
    relative_value = parse_decimal(
        relative_tolerance,
        "metric relative tolerance",
    )
    confidence_value = parse_decimal(confidence, "metric confidence")
    for label, raw in {
        "metric actual": actual,
        "metric expected": expected,
        "metric absolute tolerance": absolute_tolerance,
        "metric relative tolerance": relative_tolerance,
        "metric confidence": confidence,
    }.items():
        validate_metric_decimal_shape(raw, label, policy)
    if absolute_value < 0:
        raise CloudAdvancementError(
            "Metric absolute tolerance cannot be negative."
        )
    if relative_value < 0:
        raise CloudAdvancementError(
            "Metric relative tolerance cannot be negative."
        )
    maximum_relative = parse_decimal(
        policy["maximum_relative_tolerance"],
        "maximum relative tolerance",
    )
    if relative_value > maximum_relative:
        raise CloudAdvancementError(
            "Metric relative tolerance exceeds the assurance policy."
        )
    minimum_confidence = parse_decimal(
        policy["minimum_confidence"],
        "minimum quantitative confidence",
    )
    if confidence_value < minimum_confidence or confidence_value > 1:
        raise CloudAdvancementError(
            "Metric confidence is outside the accepted range."
        )
    if sample_size < int(policy["minimum_sample_size"]):
        raise CloudAdvancementError(
            "Metric sample size is below the assurance minimum."
        )
    if sample_size > 1_000_000_000:
        raise CloudAdvancementError("Metric sample size is unreasonably large.")
    if measurement_mode == "exact" and sample_size != 1:
        raise CloudAdvancementError(
            "Exact metrics require a sample size of one."
        )
    _validate_unit_domain(
        unit,
        actual_value,
        expected_value,
        absolute_value,
    )

    precision = int(policy["precision_digits"])
    with localcontext() as context:
        context.prec = precision
        context.rounding = policy["rounding"]
        absolute_error = abs(actual_value - expected_value)
        if expected_value == 0:
            relative_error: Decimal | None = None
            effective_tolerance = absolute_value
        else:
            relative_error = absolute_error / abs(expected_value)
            effective_tolerance = max(
                absolute_value,
                abs(expected_value) * relative_value,
            )
        passed = absolute_error <= effective_tolerance
        if expected_value == 0:
            accuracy_score = Decimal(1) if absolute_error == 0 else Decimal(0)
        else:
            accuracy_score = max(
                Decimal(0),
                Decimal(1) - min(relative_error or Decimal(0), Decimal(1)),
            )

    payload = {
        "metric_id": metric_id,
        "actual": decimal_text(actual_value),
        "expected": decimal_text(expected_value),
        "unit": unit,
        "absolute_tolerance": decimal_text(absolute_value),
        "relative_tolerance": decimal_text(relative_value),
        "absolute_error": decimal_text(absolute_error),
        "relative_error": (
            decimal_text(relative_error) if relative_error is not None else ""
        ),
        "effective_tolerance": decimal_text(effective_tolerance),
        "accuracy_score": decimal_text(accuracy_score),
        "sample_size": int(sample_size),
        "confidence": decimal_text(confidence_value),
        "sources": sources,
        "measurement_mode": measurement_mode,
        "calculation_method": (
            "absolute_only_for_zero_expected"
            if expected_value == 0
            else "max_absolute_or_relative_tolerance"
        ),
        "passed": bool(passed),
        "observed_at": isoformat(observed_at),
        "supersedes_event_id": supersedes_event_id,
    }
    assert_non_sensitive_assurance_payload(payload)
    return payload


def validate_metric_decimal_shape(
    value: str,
    label: str,
    policy: Mapping[str, Any],
) -> None:
    unsigned = value.lstrip("-")
    integer, separator, fraction = unsigned.partition(".")
    significant = (integer.lstrip("0") + fraction).lstrip("0") or "0"
    scale = len(fraction) if separator else 0
    if len(significant) > int(policy["max_significant_digits"]):
        raise CloudAdvancementError(
            f"{label} exceeds the significant-digit contract."
        )
    if scale > int(policy["max_scale_digits"]):
        raise CloudAdvancementError(
            f"{label} exceeds the decimal-scale contract."
        )


def _validate_unit_domain(
    unit: str,
    actual: Decimal,
    expected: Decimal,
    absolute_tolerance: Decimal,
) -> None:
    values = (actual, expected)
    if unit in {"count", "action", "event", "byte"}:
        if any(value < 0 or value != value.to_integral_value() for value in values):
            raise CloudAdvancementError(
                f"Metric unit {unit} requires nonnegative integers."
            )
        if absolute_tolerance != absolute_tolerance.to_integral_value():
            raise CloudAdvancementError(
                f"Metric unit {unit} requires an integral tolerance."
            )
        return
    if unit == "ratio_0_1" and any(
        value < 0 or value > 1 for value in values
    ):
        raise CloudAdvancementError(
            "Ratio metrics must remain within 0..1."
        )
    elif unit == "percent_0_100" and any(
        value < 0 or value > 100 for value in values
    ):
        raise CloudAdvancementError(
            "Percent metrics must remain within 0..100."
        )
    elif unit in {
        "millisecond",
        "minute",
        "CAD_per_month",
        "nanosecond",
    } and any(value < 0 for value in values):
        raise CloudAdvancementError(
            f"Metric unit {unit} cannot be negative."
        )


def normalize_sources(
    source_refs: Sequence[str],
    source_sha256: Sequence[str],
) -> list[dict[str, str]]:
    refs = [str(source).strip() for source in source_refs]
    digests = [str(digest).strip() for digest in source_sha256]
    if not refs or len(refs) > 50 or len(refs) != len(digests):
        raise CloudAdvancementError(
            "Assurance evidence requires 1..50 paired source references "
            "and SHA-256 digests."
        )
    if any(not source or len(source) > 1000 for source in refs):
        raise CloudAdvancementError(
            "An assurance source reference is too long."
        )
    if any(not DIGEST_PATTERN.fullmatch(digest) for digest in digests):
        raise CloudAdvancementError(
            "Every assurance source requires a lowercase SHA-256 digest."
        )
    paired = sorted(
        {
            (source, digest)
            for source, digest in zip(refs, digests, strict=True)
        }
    )
    if len(paired) != len(refs):
        raise CloudAdvancementError(
            "Assurance source and digest pairs must be unique."
        )
    sources = [
        {"source_ref": source, "sha256": digest}
        for source, digest in paired
    ]
    assert_non_sensitive_assurance_payload({"sources": sources})
    return sources


def _resolve_json_pointer(document: Any, pointer: str) -> Any:
    current = document
    for raw_token in pointer.split("/")[1:]:
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                raise CloudAdvancementError(
                    "Quantitative JSON pointer does not exist."
                )
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit() or int(token) >= len(current):
                raise CloudAdvancementError(
                    "Quantitative JSON pointer array index is invalid."
                )
            current = current[int(token)]
        else:
            raise CloudAdvancementError(
                "Quantitative JSON pointer traverses a scalar."
            )
    return current


def assert_non_sensitive_assurance_payload(payload: Any) -> None:
    _assert_safe_evidence(payload)
    for text in _sensitive_text_values(payload):
        for pattern in ASSURANCE_SENSITIVE_PATTERNS:
            if pattern.search(text):
                raise CloudAdvancementError(
                    "Assurance payload contains prohibited personal or "
                    "credential-like data."
                )


def validate_actor(value: str) -> str:
    actor = str(value)
    if not ACTOR_PATTERN.fullmatch(actor):
        raise CloudAdvancementError(
            "Assurance actor must be a lowercase opaque identifier."
        )
    _validate_operational_token(actor, "Assurance actor")
    assert_non_sensitive_assurance_payload({"actor": actor})
    return actor


def _sensitive_text_values(
    value: Any,
    *,
    field: str = "",
) -> list[str]:
    if field in NON_TEXT_ASSURANCE_FIELDS:
        return []
    if isinstance(value, Mapping):
        texts: list[str] = []
        for key, item in value.items():
            texts.extend(
                _sensitive_text_values(item, field=str(key).casefold())
            )
        return texts
    if isinstance(value, (list, tuple)):
        texts = []
        for item in value:
            texts.extend(_sensitive_text_values(item, field=field))
        return texts
    return [value] if isinstance(value, str) else []


def validate_working_memory_fact(
    fact: Any,
    assurance: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(fact, dict):
        raise CloudAdvancementError(
            "Working memory accepts only a typed fact object."
        )
    required = {
        "fact_type",
        "subject_ref",
        "value",
        "reason_codes",
        "tags",
    }
    if set(fact) != required:
        raise CloudAdvancementError(
            "Working-memory fact fields do not match the closed contract."
        )
    fact_type = str(fact["fact_type"])
    if fact_type not in assurance["working_memory"]["allowed_fact_types"]:
        raise CloudAdvancementError(
            "Working-memory fact type is not allowlisted."
        )
    subject_ref = str(fact["subject_ref"])
    if not STABLE_TOKEN_PATTERN.fullmatch(subject_ref):
        raise CloudAdvancementError(
            "Working-memory subject reference must be an opaque token."
        )
    subject_namespace = re.split(r"[._:/-]", subject_ref, maxsplit=1)[0]
    if subject_namespace not in ALLOWED_MEMORY_SUBJECT_NAMESPACES:
        raise CloudAdvancementError(
            "Working-memory subject namespace is not allowlisted."
        )
    _validate_operational_token(
        subject_ref,
        "Working-memory subject reference",
    )
    value = fact["value"]
    values = value if isinstance(value, list) else [value]
    if not values or len(values) > 20:
        raise CloudAdvancementError(
            "Working-memory fact values must contain 1..20 scalars."
        )
    for item in values:
        if isinstance(item, bool):
            continue
        if isinstance(item, str) and STABLE_TOKEN_PATTERN.fullmatch(item):
            _validate_operational_token(
                item,
                "Working-memory value",
                reject_name_shape=True,
            )
            continue
        raise CloudAdvancementError(
            "Working-memory values must be booleans or stable tokens; "
            "numbers belong in the quantitative assurance plane."
        )
    normalized_lists: dict[str, list[str]] = {}
    for field in ("reason_codes", "tags"):
        raw = fact[field]
        if not isinstance(raw, list) or len(raw) > 20:
            raise CloudAdvancementError(
                f"Working-memory {field} must be a bounded token list."
            )
        normalized = sorted({str(item) for item in raw})
        if len(normalized) != len(raw) or any(
            not STABLE_TOKEN_PATTERN.fullmatch(item)
            for item in normalized
        ):
            raise CloudAdvancementError(
                f"Working-memory {field} contains invalid tokens."
            )
        for item in normalized:
            _validate_operational_token(
                item,
                f"Working-memory {field}",
                reject_name_shape=True,
            )
        normalized_lists[field] = normalized
    normalized_fact = {
        "fact_type": fact_type,
        "subject_ref": subject_ref,
        "value": value,
        "reason_codes": normalized_lists["reason_codes"],
        "tags": normalized_lists["tags"],
    }
    assert_non_sensitive_assurance_payload(normalized_fact)
    return normalized_fact


class CloudAdvancementAssuranceStore:
    def __init__(
        self,
        project_root: Path,
        program: Mapping[str, Any],
        assurance: Mapping[str, Any],
        *,
        state_path: Path | None = None,
        clock: Clock = time.perf_counter_ns,
        initialize: bool = True,
    ):
        self.root = project_root.resolve()
        self.program = dict(program)
        self.assurance = dict(assurance)
        self.action_ids = {
            str(action["action_id"]) for action in self.program["actions"]
        }
        self.metric_by_id = {
            str(definition["metric_id"]): dict(definition)
            for definition in self.assurance["quantitative_accuracy"][
                "metric_definitions"
            ]
        }
        configured = Path(str(self.assurance["state"]["sqlite_path"]))
        self.state_path = _safe_runtime_path(
            self.root,
            state_path or configured,
            "cloud advancement assurance database",
        )
        self.clock = clock
        self.read_only = not initialize
        if initialize:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize()
        elif not self.state_path.exists():
            raise CloudAdvancementError(
                "Cloud assurance state does not exist for read-only "
                "verification."
            )

    def remember(
        self,
        *,
        key: str,
        value: Any,
        scope: str,
        actor: str,
        source_refs: Sequence[str],
        source_sha256: Sequence[str],
        idempotency_key: str,
        derivation_type: str,
        confidence: str = "1",
        salience: str = "0.5",
        ttl_hours: int | None = None,
        action_id: str = "",
        run_id: str = "",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        observed_at = now or utc_now()
        normalized_actor = validate_actor(actor)
        identity = self._memory_identity(
            key=key,
            scope=scope,
            action_id=action_id,
            run_id=run_id,
        )
        memory_policy = dict(self.assurance["working_memory"])
        self._validate_idempotency_key(idempotency_key)
        if derivation_type not in memory_policy[
            "allowed_derivation_types"
        ]:
            raise CloudAdvancementError(
                "Working-memory derivation type is not allowlisted."
            )
        if ttl_hours is not None and type(ttl_hours) is not int:
            raise CloudAdvancementError(
                "Working-memory TTL must be an integer number of hours."
            )
        ttl = (
            ttl_hours
            if ttl_hours is not None
            else int(memory_policy["default_ttl_hours"])
        )
        if ttl < 1 or ttl > int(memory_policy["max_ttl_hours"]):
            raise CloudAdvancementError(
                "Working-memory TTL is outside the governed range."
            )
        confidence_value = parse_decimal(
            confidence,
            "working-memory confidence",
        )
        salience_value = parse_decimal(
            salience,
            "working-memory salience",
        )
        for label, number in {
            "working-memory confidence": confidence_value,
            "working-memory salience": salience_value,
        }.items():
            if number < 0 or number > 1:
                raise CloudAdvancementError(f"{label} must be within 0..1.")
        sources = normalize_sources(source_refs, source_sha256)
        normalized_fact = validate_working_memory_fact(
            value,
            self.assurance,
        )
        value_json = canonical_json(normalized_fact)
        value_bytes = len(value_json.encode("utf-8"))
        if value_bytes > int(memory_policy["max_value_bytes"]):
            raise CloudAdvancementError(
                "Working-memory value exceeds the configured byte limit."
            )
        request_hash = canonical_digest(
            {
                "operation": "remember",
                "identity": identity,
                "fact": normalized_fact,
                "scope": scope,
                "action_id": action_id,
                "run_id": run_id,
                "confidence": decimal_text(confidence_value),
                "salience": decimal_text(salience_value),
                "ttl_hours": ttl,
                "sources": sources,
                "derivation_type": derivation_type,
                "actor": normalized_actor,
            }
        )

        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            events = self._validate_history(connection)
            existing = self._idempotent_event(
                connection,
                operation_key=idempotency_key,
                request_hash=request_hash,
                event_type="memory_recorded",
            )
            if existing:
                connection.commit()
                return {
                    "status": "remembered",
                    "event_id": existing["event_id"],
                    "identity": existing["subject_id"],
                    "expires_at": existing["payload"]["expires_at"],
                    "supersedes_event_id": existing["payload"][
                        "supersedes_event_id"
                    ],
                    "idempotent_replay": True,
                    "external_action_performed": False,
                }
            if scope == "run" and not self._run_belongs_to_action(
                run_id,
                action_id,
                as_of=observed_at,
            ):
                raise CloudAdvancementError(
                    "Run-scoped memory is not bound to an existing action run."
                )
            self._validate_source_files(sources)
            revision, source_state = repository_revision_state(self.root)
            latest = self._latest_by_subject(events, "memory_recorded")
            previous = latest.get(identity)
            summary = self._memory_summary_from_events(
                events,
                observed_at,
            )
            previous_is_active = bool(
                previous
                and parse_datetime(
                    str(previous["payload"]["expires_at"])
                )
                > observed_at
            )
            if (
                not previous_is_active
                and int(summary["active_entry_count"])
                >= int(memory_policy["max_active_entries"])
            ):
                raise CloudAdvancementError(
                    "Working-memory active-entry capacity is exhausted."
                )
            active_scope_bytes = sum(
                int(event["payload"]["value_bytes"])
                for event in latest.values()
                if event["payload"]["scope"] == scope
                and event["payload"]["action_id"] == action_id
                and event["payload"]["run_id"] == run_id
                and parse_datetime(
                    str(event["payload"]["expires_at"])
                )
                > observed_at
                and event["subject_id"] != identity
            )
            if active_scope_bytes + value_bytes > int(
                memory_policy["max_active_bytes_per_scope"]
            ):
                raise CloudAdvancementError(
                    "Working-memory scope byte capacity is exhausted."
                )
            expires_at = observed_at + timedelta(hours=ttl)
            payload = {
                "identity": identity,
                "key": key,
                "value": normalized_fact,
                "value_sha256": hashlib.sha256(
                    value_json.encode("utf-8")
                ).hexdigest(),
                "value_bytes": value_bytes,
                "scope": scope,
                "action_id": action_id,
                "run_id": run_id,
                "confidence": decimal_text(confidence_value),
                "salience": decimal_text(salience_value),
                "sources": sources,
                "derivation_type": derivation_type,
                "source_revision": revision,
                "source_state": source_state,
                "data_classification": memory_policy[
                    "data_classification"
                ],
                "created_at": isoformat(observed_at),
                "expires_at": isoformat(expires_at),
                "supersedes_event_id": (
                    str(previous["event_id"]) if previous else ""
                ),
            }
            self._validate_source_files(sources)
            final_revision, final_source_state = repository_revision_state(
                self.root
            )
            if (final_revision, final_source_state) != (
                revision,
                source_state,
            ):
                raise CloudAdvancementError(
                    "Repository provenance changed during the memory write."
                )
            event = self._append_event(
                connection,
                event_type="memory_recorded",
                subject_id=identity,
                actor=normalized_actor,
                occurred_at=observed_at,
                payload=payload,
                operation_key=idempotency_key,
                request_hash=request_hash,
            )
            connection.commit()
        return {
            "status": "remembered",
            "event_id": event["event_id"],
            "identity": identity,
            "expires_at": payload["expires_at"],
            "supersedes_event_id": payload["supersedes_event_id"],
            "idempotent_replay": False,
            "external_action_performed": False,
        }

    def recall(
        self,
        *,
        scope: str,
        query: str = "",
        action_id: str = "",
        run_id: str = "",
        limit: int | None = None,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        observed_at = now or utc_now()
        memory_policy = dict(self.assurance["working_memory"])
        selected_limit = (
            int(limit)
            if limit is not None
            else int(memory_policy["default_recall_limit"])
        )
        if selected_limit < 1 or selected_limit > int(
            memory_policy["max_recall_limit"]
        ):
            raise CloudAdvancementError(
                "Working-memory recall limit is outside policy."
            )
        if len(query) > 200:
            raise CloudAdvancementError("Working-memory query is too long.")
        self._validate_memory_scope(
            scope=scope,
            action_id=action_id,
            run_id=run_id,
        )
        if scope == "run" and not self._run_belongs_to_action(
            run_id,
            action_id,
            as_of=observed_at,
        ):
            raise CloudAdvancementError(
                "Run-scoped recall is not bound to an existing action run."
            )
        with closing(self._connect()) as connection:
            events = self._validate_history(connection)
        latest = self._latest_memory_as_of(events, observed_at)
        for event in latest.values():
            payload = event["payload"]
            if not (
                payload["scope"] == scope
                and payload["action_id"] == action_id
                and payload["run_id"] == run_id
                and parse_datetime(str(payload["expires_at"])) > observed_at
            ):
                continue
            try:
                self._validate_source_files(list(payload["sources"]))
            except (CloudAdvancementError, OSError) as exc:
                raise CloudAdvancementError(
                    "Working-memory provenance has drifted from its recorded "
                    "digest."
                ) from exc
        return self._recall_from_events(
            events,
            query=query,
            scope=scope,
            action_id=action_id,
            run_id=run_id,
            limit=selected_limit,
            now=observed_at,
        )

    def record_metric(
        self,
        *,
        metric_id: str,
        idempotency_key: str,
        actor: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        observed_at = now or utc_now()
        normalized_actor = validate_actor(actor)
        self._validate_idempotency_key(idempotency_key)
        definition = self.metric_by_id.get(metric_id)
        if definition is None:
            raise CloudAdvancementError(
                "Metric identifier is not defined by assurance policy."
            )
        definition_digest = canonical_digest(definition)
        request_hash = canonical_digest(
            {
                "operation": "measure",
                "metric_id": metric_id,
                "definition_digest": definition_digest,
                "actor": normalized_actor,
            }
        )
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            events = self._validate_history(connection)
            existing = self._idempotent_event(
                connection,
                operation_key=idempotency_key,
                request_hash=request_hash,
                event_type="metric_evaluated",
            )
            if existing:
                connection.commit()
                return {
                    "status": "evaluated",
                    "event_id": existing["event_id"],
                    **existing["payload"],
                    "idempotent_replay": True,
                    "external_action_performed": False,
                }
            actual, sources = self._extract_defined_metric(definition)
            latest = self._latest_by_subject(events, "metric_evaluated")
            previous = latest.get(metric_id)
            payload = evaluate_quantitative_metric(
                self.assurance,
                metric_id=metric_id,
                actual=actual,
                expected=str(definition["expected"]),
                unit=str(definition["unit"]),
                absolute_tolerance=str(
                    definition["absolute_tolerance"]
                ),
                relative_tolerance=str(
                    definition["relative_tolerance"]
                ),
                sample_size=1,
                confidence=str(definition["confidence"]),
                source_refs=[
                    str(source["source_ref"]) for source in sources
                ],
                source_sha256=[
                    str(source["sha256"]) for source in sources
                ],
                measurement_mode=str(definition["measurement_mode"]),
                observed_at=observed_at,
                supersedes_event_id=(
                    str(previous["event_id"]) if previous else ""
                ),
            )
            payload["definition_digest"] = definition_digest
            self._validate_source_files(payload["sources"])
            final_actual, final_sources = self._extract_defined_metric(
                definition
            )
            if (final_actual, final_sources) != (actual, sources):
                raise CloudAdvancementError(
                    "Quantitative source changed during metric evaluation."
                )
            event = self._append_event(
                connection,
                event_type="metric_evaluated",
                subject_id=metric_id,
                actor=normalized_actor,
                occurred_at=observed_at,
                payload=payload,
                operation_key=idempotency_key,
                request_hash=request_hash,
            )
            connection.commit()
        return {
            "status": "evaluated",
            "event_id": event["event_id"],
            **payload,
            "idempotent_replay": False,
            "external_action_performed": False,
        }

    def memory_summary(
        self,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        observed_at = now or utc_now()
        with closing(self._connect()) as connection:
            events = self._validate_history(connection)
            database_bytes = self._database_bytes(connection)
        loop_rows = self._read_validated_loop_rows()
        return self._memory_summary_from_events(
            events,
            observed_at,
            database_bytes=database_bytes,
            loop_rows=loop_rows,
        )

    def metric_summary(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            events = self._validate_history(connection)
        return self._metric_summary_from_events(events)

    def verify(
        self,
        *,
        now: datetime | None = None,
        anchor_receipt: Path | None = None,
    ) -> dict[str, Any]:
        observed_at = now or utc_now()
        if self.clock is not time.perf_counter_ns:
            raise CloudAdvancementError(
                "Attestable verification requires time.perf_counter_ns."
            )
        on_disk_assurance = load_assurance_config(self.root)
        if canonical_digest(on_disk_assurance) != canonical_digest(
            self.assurance
        ):
            raise CloudAdvancementError(
                "Loaded assurance policy differs from the workspace policy."
            )
        on_disk_program = load_program(
            self.root,
            Path(str(on_disk_assurance["program_config"])),
        )
        if canonical_digest(on_disk_program) != canonical_digest(self.program):
            raise CloudAdvancementError(
                "Loaded cloud program differs from the workspace program."
            )
        snapshot = self._snapshot()
        try:
            database_bytes_at_snapshot = self._database_bytes(snapshot)
            integrity_rows = [
                str(row[0])
                for row in snapshot.execute(
                    "PRAGMA integrity_check"
                ).fetchall()
            ]
            sqlite_integrity = integrity_rows == ["ok"]
            foreign_keys_enabled = (
                int(snapshot.execute("PRAGMA foreign_keys").fetchone()[0])
                == 1
            )
            declared_foreign_keys = snapshot.execute(
                "PRAGMA foreign_key_list(cloud_assurance_events)"
            ).fetchall()
            foreign_key_violations = snapshot.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            foreign_keys_valid = (
                foreign_keys_enabled
                and self._foreign_key_topology_valid(
                    declared_foreign_keys
                )
                and not foreign_key_violations
            )
            append_only_controls = bool(
                self._append_only_controls_valid(snapshot)
                and self._functional_append_only_controls_valid(snapshot)
            )
            append_only_trigger_count = len(
                snapshot.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'trigger'
                      AND name LIKE 'assurance_%'
                    """
                ).fetchall()
            )
            events = self._validate_history(snapshot)
            if events and parse_datetime(str(events[-1]["occurred_at"])) > (
                observed_at
            ):
                raise CloudAdvancementError(
                    "Verification time precedes the assurance history head."
                )
            binding_valid = self._binding_valid(snapshot)
            loop_rows = self._read_validated_loop_rows()
            memory_summary = self._memory_summary_from_events(
                events,
                observed_at,
                database_bytes=database_bytes_at_snapshot,
                loop_rows=loop_rows,
            )
            metric_summary = self._metric_summary_from_events(events)
            loop_state = self._verify_loop_state(loop_rows)
            artifact_manifest = self._artifact_manifest()
            assurance_history = self._verify_anchor(
                events,
                anchor_receipt=anchor_receipt,
            )
            performance = self._measure_performance(
                snapshot,
                observed_at,
                database_bytes=database_bytes_at_snapshot,
            )
        finally:
            snapshot.close()

        checks = {
            "program_and_assurance_config_valid": True,
            "sqlite_integrity_valid": sqlite_integrity,
            "foreign_keys_valid": foreign_keys_valid,
            "append_only_controls_valid": append_only_controls,
            "event_chain_valid": True,
            "program_binding_valid": binding_valid,
            "assurance_binding_valid": binding_valid,
            "loop_history_valid": True,
            "working_memory_valid": bool(
                memory_summary["within_capacity"]
                and memory_summary["scope_bytes_within_capacity"]
                and memory_summary["database_bytes_within_capacity"]
                and memory_summary["run_bindings_valid"]
                and memory_summary["sources_current"]
                and memory_summary["minimum_satisfied"]
            ),
            "quantitative_accuracy_valid": bool(
                metric_summary["minimum_satisfied"]
                and metric_summary["all_current_metrics_passed"]
            ),
            "performance_budgets_valid": bool(
                performance["all_budgets_passed"]
            ),
            "required_artifacts_present": True,
            "secrets_absent": True,
        }
        assurance_passed = all(checks.values())
        revision, source_state = repository_revision_state(self.root)
        receipt: dict[str, Any] = {
            "receipt_id": (
                "AIGC-CLOUD-VERIFY-" + uuid.uuid4().hex[:16].upper()
            ),
            "schema_version": "1.0.0",
            "assurance_id": self.assurance["assurance_id"],
            "assurance_version": self.assurance["version"],
            "assurance_digest": canonical_digest(self.assurance),
            "program_id": self.program["program_id"],
            "program_version": self.program["version"],
            "program_digest": canonical_digest(self.program),
            "verified_at": isoformat(observed_at),
            "source_revision": revision,
            "source_state": source_state,
            "assurance_passed": assurance_passed,
            "execution_authorized": False,
            "checks": checks,
            "database_integrity": {
                "integrity_result": (
                    "ok" if sqlite_integrity else "failed"
                ),
                "foreign_keys_enabled": foreign_keys_enabled,
                "declared_foreign_key_count": len(
                    declared_foreign_keys
                ),
                "foreign_key_violation_count": len(
                    foreign_key_violations
                ),
                "append_only_trigger_count": (
                    append_only_trigger_count
                ),
            },
            "loop_state": loop_state,
            "assurance_history": assurance_history,
            "working_memory": memory_summary,
            "quantitative_accuracy": metric_summary,
            "performance": performance,
            "artifact_manifest": artifact_manifest,
            "governance": {
                "operator_review_required": True,
                "phase5_approval_present": False,
                "credential_access_performed": False,
                "provider_resource_mutation_performed": False,
                "external_action_performed": False,
            },
        }
        receipt["receipt_digest"] = canonical_digest(receipt)
        schema_path = Path(
            str(self.assurance["verification"]["receipt_schema"])
        )
        schema = _load_assurance_json_object(
            _safe_input_path(
                self.root,
                schema_path,
                "cloud assurance verification receipt schema",
            )
        )
        _strict_assurance_validate(receipt, schema)
        return receipt

    def write_verification_receipt(
        self,
        receipt: Mapping[str, Any],
        output_path: Path,
    ) -> tuple[Path, dict[str, Any]]:
        target = _safe_assurance_receipt_output_path(
            self.root,
            output_path,
            self.assurance,
        )
        if target.exists():
            raise CloudAdvancementError(
                "Verification receipts are immutable and cannot be overwritten."
            )
        preliminary = validate_verification_receipt_payload(
            receipt,
            self.root,
            Path(
                str(self.assurance["verification"]["receipt_schema"])
            ),
        )
        if not preliminary["assurance_passed"]:
            raise CloudAdvancementError(
                "A failed assurance receipt cannot become a trusted "
                "checkpoint."
            )
        with closing(self._connect()) as connection:
            events = self._validate_history(connection)
            expected_count = int(
                preliminary["assurance_history"]["event_count"]
            )
            expected_head = str(
                preliminary["assurance_history"]["history_head_sha256"]
            )
            observed_head = (
                str(events[-1]["event_hash"]) if events else "0" * 64
            )
            if len(events) != expected_count or observed_head != expected_head:
                raise CloudAdvancementError(
                    "Assurance history changed before checkpoint creation."
                )
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(
            f".{target.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(
                    json.dumps(preliminary, indent=2, ensure_ascii=False)
                    + "\n"
                )
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError as exc:
                raise CloudAdvancementError(
                    "Verification receipts are immutable and cannot be "
                    "overwritten."
                ) from exc
            except OSError as exc:
                raise CloudAdvancementError(
                    "Verification receipt could not be atomically published "
                    "without replacement."
                ) from exc
        finally:
            if temporary.exists():
                temporary.unlink()
        return target, preliminary

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cloud_assurance_bindings (
                    binding_id TEXT PRIMARY KEY,
                    program_digest TEXT NOT NULL,
                    assurance_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cloud_assurance_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL CHECK (
                        event_type IN (
                            'memory_recorded',
                            'metric_evaluated'
                        )
                    ),
                    subject_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    operation_key TEXT NOT NULL UNIQUE,
                    request_hash TEXT NOT NULL,
                    binding_id TEXT NOT NULL,
                    program_digest TEXT NOT NULL,
                    assurance_digest TEXT NOT NULL,
                    previous_event_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    external_action_performed INTEGER NOT NULL
                        CHECK (external_action_performed = 0),
                    FOREIGN KEY (binding_id)
                        REFERENCES cloud_assurance_bindings(binding_id)
                );

                CREATE INDEX IF NOT EXISTS cloud_assurance_type_subject
                    ON cloud_assurance_events(
                        event_type,
                        subject_id,
                        sequence
                    );

                CREATE INDEX IF NOT EXISTS cloud_assurance_request_hash
                    ON cloud_assurance_events(request_hash);

                CREATE TRIGGER IF NOT EXISTS assurance_bindings_no_update
                BEFORE UPDATE ON cloud_assurance_bindings
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'cloud assurance bindings are append-only'
                    );
                END;

                CREATE TRIGGER IF NOT EXISTS assurance_bindings_no_delete
                BEFORE DELETE ON cloud_assurance_bindings
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'cloud assurance bindings are append-only'
                    );
                END;

                CREATE TRIGGER IF NOT EXISTS assurance_events_no_update
                BEFORE UPDATE ON cloud_assurance_events
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'cloud assurance history is append-only'
                    );
                END;

                CREATE TRIGGER IF NOT EXISTS assurance_events_no_delete
                BEFORE DELETE ON cloud_assurance_events
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'cloud assurance history is append-only'
                    );
                END;
                """
            )
            binding = connection.execute(
                """
                SELECT *
                FROM cloud_assurance_bindings
                WHERE binding_id = 'current'
                """
            ).fetchone()
            expected_program = canonical_digest(self.program)
            expected_assurance = canonical_digest(self.assurance)
            if binding is None:
                connection.execute(
                    """
                    INSERT INTO cloud_assurance_bindings (
                        binding_id,
                        program_digest,
                        assurance_digest,
                        created_at
                    )
                    VALUES ('current', ?, ?, ?)
                    """,
                    (
                        expected_program,
                        expected_assurance,
                        isoformat(utc_now()),
                    ),
                )
            elif (
                str(binding["program_digest"]) != expected_program
                or str(binding["assurance_digest"]) != expected_assurance
            ):
                raise CloudAdvancementError(
                    "Cloud assurance state is bound to different contracts."
                )
            if (
                not self._append_only_controls_valid(connection)
                or not self._functional_append_only_controls_valid(connection)
            ):
                raise CloudAdvancementError(
                    "Cloud assurance append-only controls are incomplete."
                )
            columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(cloud_assurance_events)"
                ).fetchall()
            }
            if not {"operation_key", "request_hash"} <= columns:
                raise CloudAdvancementError(
                    "Cloud assurance state predates the idempotency contract; "
                    "preserve it and use an approved migration or new path."
                )

    def _connect(self) -> sqlite3.Connection:
        timeout = int(self.assurance["state"]["busy_timeout_ms"]) / 1000
        if self.read_only:
            connection = sqlite3.connect(
                self.state_path.resolve().as_uri() + "?mode=ro",
                uri=True,
                timeout=timeout,
                isolation_level=None,
            )
        else:
            connection = sqlite3.connect(
                self.state_path,
                timeout=timeout,
                isolation_level=None,
            )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        busy_timeout_ms = int(self.assurance["state"]["busy_timeout_ms"])
        connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
        return connection

    def _snapshot(self) -> sqlite3.Connection:
        snapshot = sqlite3.connect(":memory:", isolation_level=None)
        snapshot.row_factory = sqlite3.Row
        snapshot.execute("PRAGMA foreign_keys = ON")
        with closing(self._connect()) as source:
            source.backup(snapshot)
        return snapshot

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        subject_id: str,
        actor: str,
        occurred_at: datetime,
        payload: Mapping[str, Any],
        operation_key: str,
        request_hash: str,
    ) -> dict[str, Any]:
        if event_type not in ASSURANCE_EVENT_TYPES:
            raise CloudAdvancementError(
                f"Unsupported assurance event type: {event_type}."
            )
        normalized_actor = validate_actor(actor)
        self._validate_idempotency_key(operation_key)
        if not DIGEST_PATTERN.fullmatch(request_hash):
            raise CloudAdvancementError(
                "Assurance request hash must be a SHA-256 digest."
            )
        if (
            not self._append_only_controls_valid(connection)
            or not self._functional_append_only_controls_valid(connection)
        ):
            raise CloudAdvancementError(
                "Cloud assurance append-only controls are not functional."
            )
        assert_non_sensitive_assurance_payload(payload)
        count = int(
            connection.execute(
                "SELECT COUNT(*) FROM cloud_assurance_events"
            ).fetchone()[0]
        )
        if count >= int(self.assurance["state"]["max_total_events"]):
            raise CloudAdvancementError(
                "Cloud assurance event capacity is exhausted."
            )
        maximum_database_bytes = int(
            self.assurance["state"]["max_database_bytes"]
        )
        database_bytes_before = self._database_bytes(connection)
        if database_bytes_before >= maximum_database_bytes:
            raise CloudAdvancementError(
                "Cloud assurance database byte capacity is exhausted."
            )
        previous = connection.execute(
            """
            SELECT event_hash, occurred_at
            FROM cloud_assurance_events
            ORDER BY sequence DESC
            LIMIT 1
            """
        ).fetchone()
        previous_hash = (
            str(previous["event_hash"]) if previous else "0" * 64
        )
        if previous and occurred_at < parse_datetime(
            str(previous["occurred_at"])
        ):
            raise CloudAdvancementError(
                "Assurance writes cannot precede the history head time."
            )
        event_id = f"ASSURANCE-EVENT-{uuid.uuid4().hex.upper()}"
        occurred_at_text = isoformat(occurred_at)
        payload_json = canonical_json(dict(payload))
        program_digest = canonical_digest(self.program)
        assurance_digest = canonical_digest(self.assurance)
        basis = {
            "event_id": event_id,
            "event_type": event_type,
            "subject_id": subject_id,
            "occurred_at": occurred_at_text,
            "actor": normalized_actor,
            "payload_json": payload_json,
            "operation_key": operation_key,
            "request_hash": request_hash,
            "binding_id": "current",
            "program_digest": program_digest,
            "assurance_digest": assurance_digest,
            "previous_event_hash": previous_hash,
            "external_action_performed": 0,
        }
        event_hash = canonical_digest(basis)
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        projected_growth = len(
            canonical_json({**basis, "event_hash": event_hash}).encode("utf-8")
        ) + (page_size * 8)
        if database_bytes_before + projected_growth > maximum_database_bytes:
            raise CloudAdvancementError(
                "Cloud assurance database byte capacity would be exceeded."
            )
        connection.execute(
            """
            INSERT INTO cloud_assurance_events (
                event_id,
                event_type,
                subject_id,
                occurred_at,
                actor,
                payload_json,
                operation_key,
                request_hash,
                binding_id,
                program_digest,
                assurance_digest,
                previous_event_hash,
                event_hash,
                external_action_performed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'current', ?, ?, ?, ?, 0)
            """,
            (
                event_id,
                event_type,
                subject_id,
                occurred_at_text,
                normalized_actor,
                payload_json,
                operation_key,
                request_hash,
                program_digest,
                assurance_digest,
                previous_hash,
                event_hash,
            ),
        )
        if self._database_bytes(connection) > maximum_database_bytes:
            raise CloudAdvancementError(
                "Cloud assurance database byte capacity was exceeded."
            )
        return {
            **basis,
            "event_hash": event_hash,
        }

    def _idempotent_event(
        self,
        connection: sqlite3.Connection,
        *,
        operation_key: str,
        request_hash: str,
        event_type: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT *
            FROM cloud_assurance_events
            WHERE operation_key = ?
            """,
            (operation_key,),
        ).fetchone()
        if row is None:
            return None
        event = {
            "sequence": int(row["sequence"]),
            "event_id": str(row["event_id"]),
            "event_type": str(row["event_type"]),
            "subject_id": str(row["subject_id"]),
            "payload": json.loads(str(row["payload_json"])),
        }
        if (
            str(row["request_hash"]) != request_hash
            or event["event_type"] != event_type
        ):
            raise CloudAdvancementError(
                "Idempotency key was reused with a different request."
            )
        return event

    @staticmethod
    def _validate_idempotency_key(value: str) -> None:
        if not IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
            raise CloudAdvancementError(
                "Idempotency key must be 8..128 stable characters."
            )
        _validate_operational_token(value, "Idempotency key")
        assert_non_sensitive_assurance_payload(
            {"idempotency_key": value}
        )

    def _database_bytes(
        self,
        connection: sqlite3.Connection | None = None,
    ) -> int:
        if connection is None:
            with closing(self._connect()) as opened:
                return self._database_bytes(opened)
        page_count = int(
            connection.execute("PRAGMA page_count").fetchone()[0]
        )
        page_size = int(
            connection.execute("PRAGMA page_size").fetchone()[0]
        )
        return page_count * page_size

    def _read_events(
        self,
        connection: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM cloud_assurance_events ORDER BY sequence"
        ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(str(row["payload_json"]))
            except json.JSONDecodeError as exc:
                raise CloudAdvancementError(
                    "Cloud assurance event payload is not valid JSON."
                ) from exc
            if not isinstance(payload, dict):
                raise CloudAdvancementError(
                    "Cloud assurance event payload must be a JSON object."
                )
            events.append(
                {
                "sequence": int(row["sequence"]),
                "event_id": str(row["event_id"]),
                "event_type": str(row["event_type"]),
                "subject_id": str(row["subject_id"]),
                "occurred_at": str(row["occurred_at"]),
                "actor": str(row["actor"]),
                "payload": payload,
                "payload_json": str(row["payload_json"]),
                "operation_key": str(row["operation_key"]),
                "request_hash": str(row["request_hash"]),
                "binding_id": str(row["binding_id"]),
                "program_digest": str(row["program_digest"]),
                "assurance_digest": str(row["assurance_digest"]),
                "previous_event_hash": str(row["previous_event_hash"]),
                "event_hash": str(row["event_hash"]),
                "external_action_performed": bool(
                    row["external_action_performed"]
                ),
                }
            )
        return events

    def _validate_history(
        self,
        connection: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        if not self._binding_valid(connection):
            raise CloudAdvancementError(
                "Cloud assurance contract binding is invalid."
            )
        events = self._read_events(connection)
        expected_program = canonical_digest(self.program)
        expected_assurance = canonical_digest(self.assurance)
        previous_hash = "0" * 64
        latest_subject: dict[tuple[str, str], str] = {}
        previous_timestamp: datetime | None = None
        for expected_sequence, event in enumerate(events, start=1):
            if int(event["sequence"]) != expected_sequence:
                raise CloudAdvancementError(
                    "Cloud assurance history sequence is discontinuous."
                )
            if event["event_type"] not in ASSURANCE_EVENT_TYPES:
                raise CloudAdvancementError(
                    "Cloud assurance history has an unsupported event."
                )
            if event["binding_id"] != "current":
                raise CloudAdvancementError(
                    "Cloud assurance event has an invalid binding."
                )
            if event["program_digest"] != expected_program:
                raise CloudAdvancementError(
                    "Cloud assurance history has a program mismatch."
                )
            if event["assurance_digest"] != expected_assurance:
                raise CloudAdvancementError(
                    "Cloud assurance history has a policy mismatch."
                )
            if event["previous_event_hash"] != previous_hash:
                raise CloudAdvancementError(
                    "Cloud assurance history chain is discontinuous."
                )
            timestamp = parse_datetime(str(event["occurred_at"]))
            if previous_timestamp and timestamp < previous_timestamp:
                raise CloudAdvancementError(
                    "Cloud assurance timestamps are not nondecreasing."
                )
            previous_timestamp = timestamp
            validate_actor(str(event["actor"]))
            self._validate_idempotency_key(str(event["operation_key"]))
            if not DIGEST_PATTERN.fullmatch(str(event["request_hash"])):
                raise CloudAdvancementError(
                    "Cloud assurance request hash is invalid."
                )
            if event["external_action_performed"] is not False:
                raise CloudAdvancementError(
                    "Cloud assurance history claims an external action."
                )
            assert_non_sensitive_assurance_payload(event["payload"])
            basis = {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "subject_id": event["subject_id"],
                "occurred_at": event["occurred_at"],
                "actor": event["actor"],
                "payload_json": event["payload_json"],
                "operation_key": event["operation_key"],
                "request_hash": event["request_hash"],
                "binding_id": event["binding_id"],
                "program_digest": event["program_digest"],
                "assurance_digest": event["assurance_digest"],
                "previous_event_hash": event["previous_event_hash"],
                "external_action_performed": 0,
            }
            expected_hash = canonical_digest(basis)
            if event["event_hash"] != expected_hash:
                raise CloudAdvancementError(
                    "Cloud assurance event hash is invalid."
                )
            subject_key = (
                str(event["event_type"]),
                str(event["subject_id"]),
            )
            expected_supersedes = latest_subject.get(subject_key, "")
            if event["payload"].get("supersedes_event_id", "") != (
                expected_supersedes
            ):
                raise CloudAdvancementError(
                    "Cloud assurance supersession chain is invalid."
                )
            if event["event_type"] == "memory_recorded":
                self._validate_memory_event(event)
            else:
                self._validate_metric_event(event)
            latest_subject[subject_key] = str(event["event_id"])
            previous_hash = expected_hash
        return events

    def _validate_memory_event(self, event: Mapping[str, Any]) -> None:
        payload = dict(event["payload"])
        required = {
            "identity",
            "key",
            "value",
            "value_sha256",
            "value_bytes",
            "scope",
            "action_id",
            "run_id",
            "confidence",
            "salience",
            "sources",
            "derivation_type",
            "source_revision",
            "source_state",
            "data_classification",
            "created_at",
            "expires_at",
            "supersedes_event_id",
        }
        if set(payload) != required:
            raise CloudAdvancementError(
                "Working-memory event fields do not match the contract."
            )
        identity = self._memory_identity(
            key=str(payload["key"]),
            scope=str(payload["scope"]),
            action_id=str(payload["action_id"]),
            run_id=str(payload["run_id"]),
        )
        if identity != event["subject_id"] or payload["identity"] != identity:
            raise CloudAdvancementError(
                "Working-memory identity binding is invalid."
            )
        created_at = parse_datetime(str(payload["created_at"]))
        expires_at = parse_datetime(str(payload["expires_at"]))
        if str(payload["created_at"]) != event["occurred_at"]:
            raise CloudAdvancementError(
                "Working-memory creation time is not event-bound."
            )
        max_ttl = timedelta(
            hours=int(self.assurance["working_memory"]["max_ttl_hours"])
        )
        if expires_at <= created_at or expires_at > created_at + max_ttl:
            raise CloudAdvancementError(
                "Working-memory expiry violates the TTL policy."
            )
        confidence = parse_decimal(
            payload["confidence"],
            "working-memory confidence",
        )
        salience = parse_decimal(
            payload["salience"],
            "working-memory salience",
        )
        if not (0 <= confidence <= 1 and 0 <= salience <= 1):
            raise CloudAdvancementError(
                "Working-memory weights must be within 0..1."
            )
        sources = list(payload["sources"])
        normalized_sources = normalize_sources(
            [
                str(source.get("source_ref", ""))
                for source in sources
                if isinstance(source, dict)
            ],
            [
                str(source.get("sha256", ""))
                for source in sources
                if isinstance(source, dict)
            ],
        )
        if normalized_sources != sources:
            raise CloudAdvancementError(
                "Working-memory provenance is not canonical."
            )
        self._validate_source_references(normalized_sources)
        if payload["derivation_type"] not in (
            self.assurance["working_memory"]["allowed_derivation_types"]
        ):
            raise CloudAdvancementError(
                "Working-memory derivation type is invalid."
            )
        if payload["source_state"] not in {"clean", "dirty", "unbound"}:
            raise CloudAdvancementError(
                "Working-memory source state is invalid."
            )
        if not re.fullmatch(
            r"(?:[a-f0-9]{40}|unbound)",
            str(payload["source_revision"]),
        ):
            raise CloudAdvancementError(
                "Working-memory source revision is invalid."
            )
        if payload["data_classification"] != (
            self.assurance["working_memory"]["data_classification"]
        ):
            raise CloudAdvancementError(
                "Working-memory data classification is invalid."
            )
        normalized_fact = validate_working_memory_fact(
            payload["value"],
            self.assurance,
        )
        if normalized_fact != payload["value"]:
            raise CloudAdvancementError(
                "Working-memory fact is not canonical."
            )
        value_json = canonical_json(normalized_fact)
        if int(payload["value_bytes"]) != len(
            value_json.encode("utf-8")
        ):
            raise CloudAdvancementError(
                "Working-memory byte count is invalid."
            )
        if int(payload["value_bytes"]) > int(
            self.assurance["working_memory"]["max_value_bytes"]
        ):
            raise CloudAdvancementError(
                "Working-memory payload exceeds its byte limit."
            )
        expected_value_hash = hashlib.sha256(
            value_json.encode("utf-8")
        ).hexdigest()
        if payload["value_sha256"] != expected_value_hash:
            raise CloudAdvancementError(
                "Working-memory value digest is invalid."
            )

    def _validate_metric_event(self, event: Mapping[str, Any]) -> None:
        payload = dict(event["payload"])
        metric_id = str(payload.get("metric_id", ""))
        definition = self.metric_by_id.get(metric_id)
        if definition is None:
            raise CloudAdvancementError(
                "Quantitative history references an undefined metric."
            )
        actual, sources = self._extract_defined_metric(definition)
        expected = evaluate_quantitative_metric(
            self.assurance,
            metric_id=metric_id,
            actual=actual,
            expected=str(definition["expected"]),
            unit=str(definition["unit"]),
            absolute_tolerance=str(definition["absolute_tolerance"]),
            relative_tolerance=str(definition["relative_tolerance"]),
            sample_size=1,
            confidence=str(definition["confidence"]),
            source_refs=[
                str(source.get("source_ref", ""))
                for source in sources
                if isinstance(source, dict)
            ],
            source_sha256=[
                str(source.get("sha256", ""))
                for source in sources
                if isinstance(source, dict)
            ],
            measurement_mode=str(definition["measurement_mode"]),
            observed_at=parse_datetime(str(payload.get("observed_at", ""))),
            supersedes_event_id=str(
                payload.get("supersedes_event_id", "")
            ),
        )
        expected["definition_digest"] = canonical_digest(definition)
        if payload != expected or event["subject_id"] != payload["metric_id"]:
            raise CloudAdvancementError(
                "Quantitative metric cannot be recomputed exactly."
            )
        self._validate_source_files(expected["sources"])
        if payload["observed_at"] != event["occurred_at"]:
            raise CloudAdvancementError(
                "Quantitative metric time is not event-bound."
            )

    def _memory_identity(
        self,
        *,
        key: str,
        scope: str,
        action_id: str,
        run_id: str,
    ) -> str:
        if not MEMORY_KEY_PATTERN.fullmatch(key):
            raise CloudAdvancementError(
                "Memory key must use stable lowercase path syntax."
            )
        _validate_operational_token(key, "Memory key")
        assert_non_sensitive_assurance_payload({"memory_key": key})
        self._validate_memory_scope(
            scope=scope,
            action_id=action_id,
            run_id=run_id,
        )
        return "|".join((scope, action_id, run_id, key))

    def _validate_memory_scope(
        self,
        *,
        scope: str,
        action_id: str,
        run_id: str,
    ) -> None:
        allowed = self.assurance["working_memory"]["allowed_scopes"]
        if scope not in allowed:
            raise CloudAdvancementError(
                "Working-memory operations require an explicit valid scope."
            )
        if scope == "program":
            if action_id or run_id:
                raise CloudAdvancementError(
                    "Program memory cannot bind an action or run."
                )
        elif scope == "action":
            if action_id not in self.action_ids or run_id:
                raise CloudAdvancementError(
                    "Action memory requires one known action and no run."
                )
        else:
            if action_id not in self.action_ids:
                raise CloudAdvancementError(
                    "Run memory requires one known action."
                )
            if not RUN_ID_PATTERN.fullmatch(run_id):
                raise CloudAdvancementError(
                    "Run memory requires a valid run identifier."
                )

    @staticmethod
    def _latest_memory_as_of(
        events: Sequence[Mapping[str, Any]],
        now: datetime,
    ) -> dict[str, Mapping[str, Any]]:
        latest: dict[str, Mapping[str, Any]] = {}
        for event in events:
            if event["event_type"] != "memory_recorded":
                continue
            created_at = parse_datetime(
                str(event["payload"]["created_at"])
            )
            if created_at <= now:
                latest[str(event["subject_id"])] = event
        return latest

    @staticmethod
    def _latest_by_subject(
        events: Sequence[Mapping[str, Any]],
        event_type: str,
    ) -> dict[str, Mapping[str, Any]]:
        latest: dict[str, Mapping[str, Any]] = {}
        for event in events:
            if event["event_type"] == event_type:
                latest[str(event["subject_id"])] = event
        return latest

    def _memory_summary_from_events(
        self,
        events: Sequence[Mapping[str, Any]],
        now: datetime,
        *,
        database_bytes: int | None = None,
        loop_rows: Sequence[sqlite3.Row] | None = None,
    ) -> dict[str, Any]:
        memory_events = [
            event
            for event in events
            if event["event_type"] == "memory_recorded"
            and parse_datetime(str(event["payload"]["created_at"])) <= now
        ]
        latest = self._latest_memory_as_of(events, now)
        active = 0
        expired = 0
        active_value_bytes = 0
        active_events: list[Mapping[str, Any]] = []
        scope_bytes: dict[tuple[str, str, str], int] = {}
        for event in latest.values():
            if parse_datetime(str(event["payload"]["expires_at"])) > now:
                active += 1
                active_events.append(event)
                value_bytes = int(event["payload"]["value_bytes"])
                active_value_bytes += value_bytes
                scope_key = (
                    str(event["payload"]["scope"]),
                    str(event["payload"]["action_id"]),
                    str(event["payload"]["run_id"]),
                )
                scope_bytes[scope_key] = (
                    scope_bytes.get(scope_key, 0) + value_bytes
                )
            else:
                expired += 1
        policy = dict(self.assurance["working_memory"])
        capacity = int(policy["max_active_entries"])
        minimum = int(policy["minimum_active_entries"])
        max_scope_bytes = int(policy["max_active_bytes_per_scope"])
        observed_max_scope_bytes = max(scope_bytes.values(), default=0)
        observed_database_bytes = (
            self._database_bytes()
            if database_bytes is None
            else int(database_bytes)
        )
        max_database_bytes = int(
            self.assurance["state"]["max_database_bytes"]
        )
        run_bindings_valid = all(
            event["payload"]["scope"] != "run"
            or self._run_belongs_to_action_rows(
                loop_rows,
                str(event["payload"]["run_id"]),
                str(event["payload"]["action_id"]),
                as_of=parse_datetime(
                    str(event["payload"]["created_at"])
                ),
            )
            for event in active_events
        )
        source_drift_count = 0
        for event in active_events:
            try:
                self._validate_source_files(
                    list(event["payload"]["sources"])
                )
            except (CloudAdvancementError, OSError):
                source_drift_count += 1
        return {
            "memory_event_count": len(memory_events),
            "distinct_identity_count": len(latest),
            "active_entry_count": active,
            "expired_entry_count": expired,
            "active_value_bytes": active_value_bytes,
            "minimum_active_entries": minimum,
            "capacity": capacity,
            "max_active_bytes_per_scope": max_scope_bytes,
            "max_active_scope_bytes_observed": observed_max_scope_bytes,
            "database_bytes": observed_database_bytes,
            "max_database_bytes": max_database_bytes,
            "within_capacity": active <= capacity,
            "scope_bytes_within_capacity": all(
                value <= max_scope_bytes for value in scope_bytes.values()
            ),
            "database_bytes_within_capacity": (
                observed_database_bytes <= max_database_bytes
            ),
            "run_bindings_valid": run_bindings_valid,
            "source_drift_count": source_drift_count,
            "sources_current": source_drift_count == 0,
            "minimum_satisfied": active >= minimum,
        }

    def _metric_summary_from_events(
        self,
        events: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        metric_events = [
            event
            for event in events
            if event["event_type"] == "metric_evaluated"
        ]
        latest = self._latest_by_subject(events, "metric_evaluated")
        required_metric_ids = set(self.metric_by_id)
        missing_required = sorted(required_metric_ids - set(latest))
        current_passed = sum(
            1 for event in latest.values() if event["payload"]["passed"]
        )
        current_failed = len(latest) - current_passed
        historical_failed = sum(
            1 for event in metric_events if not event["payload"]["passed"]
        )
        with localcontext() as context:
            context.prec = int(
                self.assurance["quantitative_accuracy"]["precision_digits"]
            )
            pass_rate = (
                Decimal(current_passed) / Decimal(len(latest))
                if latest
                else Decimal(0)
            )
        minimum = len(required_metric_ids)
        return {
            "metric_event_count": len(metric_events),
            "distinct_metric_count": len(latest),
            "current_passed_count": current_passed,
            "current_failed_count": current_failed,
            "historical_failed_count": historical_failed,
            "required_metric_count": minimum,
            "missing_required_metric_ids": missing_required,
            "minimum_distinct_metrics": minimum,
            "pass_rate": decimal_text(pass_rate),
            "minimum_satisfied": not missing_required,
            "all_current_metrics_passed": (
                not missing_required and current_failed == 0
            ),
        }

    def _recall_from_events(
        self,
        events: Sequence[Mapping[str, Any]],
        *,
        query: str,
        scope: str,
        action_id: str,
        run_id: str,
        limit: int,
        now: datetime,
    ) -> list[dict[str, Any]]:
        latest = self._latest_memory_as_of(events, now)
        minimum_confidence = parse_decimal(
            self.assurance["working_memory"][
                "minimum_recall_confidence"
            ],
            "minimum recall confidence",
        )
        needle = query.casefold().strip()
        selected: list[dict[str, Any]] = []
        for event in latest.values():
            payload = dict(event["payload"])
            if not (
                parse_datetime(str(payload["created_at"]))
                <= now
                < parse_datetime(str(payload["expires_at"]))
            ):
                continue
            if parse_decimal(
                payload["confidence"],
                "working-memory confidence",
            ) < minimum_confidence:
                continue
            if payload["scope"] != scope:
                continue
            if action_id and payload["action_id"] != action_id:
                continue
            if run_id and payload["run_id"] != run_id:
                continue
            searchable = (
                str(payload["key"]) + " " + canonical_json(payload["value"])
            ).casefold()
            if needle and needle not in searchable:
                continue
            selected.append(
                {
                    "event_id": event["event_id"],
                    "sequence": event["sequence"],
                    **payload,
                }
            )
        selected.sort(
            key=lambda item: (
                -parse_decimal(item["salience"], "memory salience"),
                -parse_decimal(item["confidence"], "memory confidence"),
                -int(item["sequence"]),
                str(item["identity"]),
            )
        )
        bounded: list[dict[str, Any]] = []
        used_bytes = 0
        max_bytes = int(
            self.assurance["working_memory"]["max_recall_bytes"]
        )
        for item in selected[:limit]:
            item_bytes = len(canonical_json(item).encode("utf-8"))
            if used_bytes + item_bytes > max_bytes:
                break
            bounded.append(item)
            used_bytes += item_bytes
        return bounded

    def _binding_valid(self, connection: sqlite3.Connection) -> bool:
        rows = connection.execute(
            "SELECT * FROM cloud_assurance_bindings"
        ).fetchall()
        return bool(
            len(rows) == 1
            and str(rows[0]["binding_id"]) == "current"
            and str(rows[0]["program_digest"])
            == canonical_digest(self.program)
            and str(rows[0]["assurance_digest"])
            == canonical_digest(self.assurance)
        )

    def _validate_source_files(
        self,
        sources: Sequence[Mapping[str, str]],
    ) -> None:
        self._validate_source_references(sources)
        max_bytes = int(self.assurance["provenance"]["max_source_bytes"])
        for source in sources:
            relative = Path(str(source["source_ref"]))
            path = _safe_input_path(
                self.root,
                relative,
                "assurance provenance source",
            )
            data = _read_bounded_file(
                path,
                max_bytes,
                "Assurance provenance source",
            )
            observed_digest = hashlib.sha256(data).hexdigest()
            if observed_digest != source["sha256"]:
                raise CloudAdvancementError(
                    "Assurance provenance source digest does not match."
                )

    @staticmethod
    def _validate_source_references(
        sources: Sequence[Mapping[str, str]],
    ) -> None:
        for source in sources:
            relative = Path(str(source["source_ref"]))
            lowered_parts = {part.casefold() for part in relative.parts}
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or ".env" in lowered_parts
                or "credentials" in lowered_parts
                or relative.suffix.casefold() in {".key", ".pem", ".p12"}
            ):
                raise CloudAdvancementError(
                    "Assurance provenance must reference a non-secret "
                    "workspace file."
                )

    def _extract_defined_metric(
        self,
        definition: Mapping[str, Any],
    ) -> tuple[str, list[dict[str, str]]]:
        relative = Path(str(definition["source_ref"]))
        path = _safe_input_path(
            self.root,
            relative,
            "defined quantitative source",
        )
        data = _read_bounded_file(
            path,
            int(self.assurance["provenance"]["max_source_bytes"]),
            "Defined quantitative source",
        )
        sources = [
            {
                "source_ref": str(relative).replace("\\", "/"),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        ]
        self._validate_source_files(sources)
        try:
            document = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CloudAdvancementError(
                "Defined quantitative source must be UTF-8 JSON."
            ) from exc

        normalized_source = str(relative).replace("\\", "/")
        if normalized_source == str(self.assurance["program_config"]):
            if canonical_digest(document) != canonical_digest(self.program):
                raise CloudAdvancementError(
                    "Defined program metric source does not match the "
                    "bound program."
                )
        initial_receipt_path = (
            "reports/artifacts/cloud_advancement/"
            "initial_execution_receipt.json"
        )
        if normalized_source == initial_receipt_path:
            pinned_digest = str(
                self.assurance["verification"][
                    "trusted_loop_receipt_sha256"
                ]
            )
            if hashlib.sha256(data).hexdigest() != pinned_digest:
                raise CloudAdvancementError(
                    "Defined execution receipt does not match its pinned "
                    "SHA-256 digest."
                )
            initial_receipt = _validate_execution_receipt_bytes(
                self.root,
                path,
                data,
            )
            if initial_receipt["program_digest"] != canonical_digest(
                self.program
            ):
                raise CloudAdvancementError(
                    "Defined execution receipt does not match the bound "
                    "program."
                )

        extracted = _resolve_json_pointer(
            document,
            str(definition["extractor"]["pointer"]),
        )
        extractor_type = str(definition["extractor"]["type"])
        if extractor_type == "json_pointer_length":
            if not isinstance(extracted, list):
                raise CloudAdvancementError(
                    "Defined length extractor did not resolve to an array."
                )
            value: Any = len(extracted)
        elif extractor_type == "json_pointer_value":
            value = extracted
        elif extractor_type == "execution_receipt_completed_unique_count":
            if not isinstance(extracted, list):
                raise CloudAdvancementError(
                    "Execution-receipt completion extractor did not resolve "
                    "to an array."
                )
            execution_pairs: list[tuple[str, str]] = []
            for item in extracted:
                if not isinstance(item, Mapping):
                    raise CloudAdvancementError(
                        "Execution receipt contains an invalid action record."
                    )
                action_id = str(item.get("action_id", ""))
                run_id = str(item.get("run_id", ""))
                if action_id not in self.action_ids:
                    raise CloudAdvancementError(
                        "Execution receipt contains an action outside the "
                        "bound program."
                    )
                execution_pairs.append((run_id, action_id))
            if len(execution_pairs) != len(set(execution_pairs)):
                raise CloudAdvancementError(
                    "Execution receipt contains a duplicate action run."
                )
            completed_ids = {
                str(item.get("action_id", ""))
                for item in extracted
                if isinstance(item, Mapping)
                and item.get("state") == "completed"
            }
            if "" in completed_ids:
                raise CloudAdvancementError(
                    "Execution receipt has an invalid completed action."
                )
            loop_rows = self._read_validated_loop_rows()
            if loop_rows is not None:
                completed_pairs = {
                    (str(row["run_id"]), str(row["action_id"]))
                    for row in loop_rows
                    if str(row["event_type"]) == "completed"
                }
                required_completed_pairs = {
                    (
                        str(item.get("run_id", "")),
                        str(item.get("action_id", "")),
                    )
                    for item in extracted
                    if isinstance(item, Mapping)
                    and item.get("state") == "completed"
                }
                if not required_completed_pairs <= completed_pairs:
                    raise CloudAdvancementError(
                        "Execution receipt completion is not backed by the "
                        "validated action ledger."
                    )
            value = len(completed_ids)
        else:
            raise CloudAdvancementError(
                "Defined quantitative extractor is unsupported."
            )
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise CloudAdvancementError(
                "Defined quantitative extractor must yield an integer or "
                "plain decimal string."
            )
        actual = str(value)
        parse_decimal(actual, "defined quantitative actual")
        return actual, sources

    @staticmethod
    def _append_only_controls_valid(
        connection: sqlite3.Connection,
    ) -> bool:
        names = {
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                """
            ).fetchall()
        }
        return {
            "assurance_bindings_no_update",
            "assurance_bindings_no_delete",
            "assurance_events_no_update",
            "assurance_events_no_delete",
        } <= names

    @staticmethod
    def _foreign_key_topology_valid(
        rows: Sequence[sqlite3.Row],
    ) -> bool:
        if len(rows) != 1:
            return False
        row = rows[0]
        return bool(
            str(row["table"]) == "cloud_assurance_bindings"
            and str(row["from"]) == "binding_id"
            and str(row["to"]) == "binding_id"
            and str(row["on_update"]).upper() == "NO ACTION"
            and str(row["on_delete"]).upper() == "NO ACTION"
        )

    @staticmethod
    def _functional_append_only_controls_valid(
        connection: sqlite3.Connection,
    ) -> bool:
        operations = [
            (
                "UPDATE cloud_assurance_bindings "
                "SET created_at = created_at || 'Z' "
                "WHERE binding_id = 'current'"
            ),
            (
                "DELETE FROM cloud_assurance_bindings "
                "WHERE binding_id = 'current'"
            ),
            (
                "UPDATE cloud_assurance_events "
                "SET actor = actor || '-tamper' "
                "WHERE sequence = ("
                "SELECT MIN(sequence) FROM cloud_assurance_events"
                ")"
            ),
            (
                "DELETE FROM cloud_assurance_events "
                "WHERE sequence = ("
                "SELECT MIN(sequence) FROM cloud_assurance_events"
                ")"
            ),
        ]
        outer_savepoint = "append_only_functional_probe"
        connection.execute(f"SAVEPOINT {outer_savepoint}")
        try:
            event_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM cloud_assurance_events"
                ).fetchone()[0]
            )
            if event_count == 0:
                connection.execute(
                    """
                    INSERT INTO cloud_assurance_events (
                        event_id,
                        event_type,
                        subject_id,
                        occurred_at,
                        actor,
                        payload_json,
                        operation_key,
                        request_hash,
                        binding_id,
                        program_digest,
                        assurance_digest,
                        previous_event_hash,
                        event_hash,
                        external_action_performed
                    )
                    VALUES (
                        'ASSURANCE-APPEND-ONLY-PROBE',
                        'memory_recorded',
                        'probe',
                        '1970-01-01T00:00:00Z',
                        'probe',
                        '{}',
                        'assurance-append-only-probe',
                        ?,
                        'current',
                        ?,
                        ?,
                        ?,
                        ?,
                        0
                    )
                    """,
                    ("0" * 64,) * 5,
                )
            for index, statement in enumerate(operations):
                savepoint = f"append_only_probe_{index}"
                connection.execute(f"SAVEPOINT {savepoint}")
                protected = False
                try:
                    connection.execute(statement)
                except sqlite3.DatabaseError as exc:
                    protected = "append-only" in str(exc)
                finally:
                    connection.execute(f"ROLLBACK TO {savepoint}")
                    connection.execute(f"RELEASE {savepoint}")
                if not protected:
                    return False
            return True
        except sqlite3.DatabaseError:
            return False
        finally:
            connection.execute(f"ROLLBACK TO {outer_savepoint}")
            connection.execute(f"RELEASE {outer_savepoint}")

    def _read_validated_loop_rows(
        self,
    ) -> list[sqlite3.Row] | None:
        state_path = _safe_runtime_path(
            self.root,
            Path(str(self.program["state"]["sqlite_path"])),
            "cloud advancement state database",
        )
        if not state_path.exists():
            return None
        uri = state_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                "SELECT * FROM cloud_action_events ORDER BY sequence"
            ).fetchall()
            self._validate_loop_rows(rows)
            self._validate_loop_trusted_prefix(rows)
            return rows
        finally:
            connection.close()

    def _verify_loop_state(
        self,
        rows: Sequence[sqlite3.Row] | None = None,
    ) -> dict[str, Any]:
        selected_rows = (
            self._read_validated_loop_rows() if rows is None else rows
        )
        if selected_rows is None:
            return {
                "policy": "verify_if_present",
                "observation": "not_present",
                "event_count": 0,
                "history_head_sha256": "0" * 64,
            }
        return {
            "policy": "verify_if_present",
            "observation": "verified",
            "event_count": len(selected_rows),
            "history_head_sha256": (
                str(selected_rows[-1]["event_hash"])
                if selected_rows
                else "0" * 64
            ),
        }

    def _run_belongs_to_action(
        self,
        run_id: str,
        action_id: str,
        *,
        as_of: datetime | None = None,
    ) -> bool:
        rows = self._read_validated_loop_rows()
        return self._run_belongs_to_action_rows(
            rows,
            run_id,
            action_id,
            as_of=as_of,
        )

    def _run_belongs_to_action_rows(
        self,
        rows: Sequence[sqlite3.Row] | None,
        run_id: str,
        action_id: str,
        *,
        as_of: datetime | None = None,
    ) -> bool:
        if rows is None:
            return False
        trusted_receipt = self._trusted_loop_receipt()
        trusted_runs = {
            (str(item["run_id"]), str(item["action_id"]))
            for item in trusted_receipt["executed_actions"]
        }
        if (run_id, action_id) not in trusted_runs:
            return False
        return any(
            str(row["run_id"]) == run_id
            and str(row["action_id"]) == action_id
            and str(row["event_type"]) == "claimed"
            and (
                as_of is None
                or parse_datetime(str(row["occurred_at"])) <= as_of
            )
            for row in rows
        )

    def _trusted_loop_receipt(self) -> dict[str, Any]:
        configured_path = Path(
            str(
                self.assurance["verification"]["trusted_loop_receipt"]
            )
        )
        receipt_path = _safe_input_path(
            self.root,
            configured_path,
            "trusted cloud advancement execution receipt",
        )
        data = _read_bounded_file(
            receipt_path,
            int(self.assurance["provenance"]["max_source_bytes"]),
            "Trusted cloud advancement execution receipt",
        )
        if hashlib.sha256(data).hexdigest() != str(
            self.assurance["verification"][
                "trusted_loop_receipt_sha256"
            ]
        ):
            raise CloudAdvancementError(
                "Trusted loop receipt does not match its pinned SHA-256 "
                "digest."
            )
        receipt = _validate_execution_receipt_bytes(
            self.root,
            receipt_path,
            data,
        )
        if (
            receipt["program_digest"] != canonical_digest(self.program)
            or receipt["program_id"] != self.program["program_id"]
            or receipt["program_version"] != self.program["version"]
        ):
            raise CloudAdvancementError(
                "Trusted loop receipt is not bound to the active program."
            )
        return receipt

    def _validate_loop_trusted_prefix(
        self,
        rows: Sequence[sqlite3.Row],
    ) -> None:
        trusted_head = str(
            self._trusted_loop_receipt()["history_head_sha256"]
        )
        if not any(
            str(row["event_hash"]) == trusted_head for row in rows
        ):
            raise CloudAdvancementError(
                "Cloud action history does not contain its trusted "
                "execution-receipt anchor."
            )

    def _verify_loop_receipt_prefix(
        self,
        receipt_state: Mapping[str, Any],
    ) -> None:
        if receipt_state["observation"] == "not_present":
            return
        rows = self._read_validated_loop_rows()
        if rows is None:
            raise CloudAdvancementError(
                "Verification receipt action history is missing."
            )
        receipt_count = int(receipt_state["event_count"])
        if len(rows) < receipt_count:
            raise CloudAdvancementError(
                "Action history is shorter than the verification receipt."
            )
        prefix_head = (
            str(rows[receipt_count - 1]["event_hash"])
            if receipt_count
            else "0" * 64
        )
        if prefix_head != receipt_state["history_head_sha256"]:
            raise CloudAdvancementError(
                "Verification receipt action-history prefix is invalid."
            )

    def _validate_loop_rows(self, rows: Sequence[sqlite3.Row]) -> None:
        expected_program = canonical_digest(self.program)
        previous_hash = "0" * 64
        runs: dict[str, list[str]] = {}
        previous_timestamp: datetime | None = None
        action_by_id = {
            str(action["action_id"]): dict(action)
            for action in self.program["actions"]
        }
        for expected_sequence, row in enumerate(rows, start=1):
            if int(row["sequence"]) != expected_sequence:
                raise CloudAdvancementError(
                    "Cloud action history sequence is discontinuous."
                )
            action_id = str(row["action_id"])
            if action_id not in action_by_id:
                raise CloudAdvancementError(
                    "Cloud action history references an unknown action."
                )
            if str(row["program_digest"]) != expected_program:
                raise CloudAdvancementError(
                    "Cloud action history has a program mismatch."
                )
            if str(row["previous_event_hash"]) != previous_hash:
                raise CloudAdvancementError(
                    "Cloud action history chain is discontinuous."
                )
            timestamp = parse_datetime(str(row["occurred_at"]))
            if previous_timestamp and timestamp < previous_timestamp:
                raise CloudAdvancementError(
                    "Cloud action event timestamps are not nondecreasing."
                )
            previous_timestamp = timestamp
            payload = json.loads(str(row["evidence_json"]))
            _assert_safe_evidence(payload)
            if int(row["external_action_performed"]) != 0:
                raise CloudAdvancementError(
                    "Cloud action history claims an external action."
                )
            basis = {
                "event_id": str(row["event_id"]),
                "run_id": str(row["run_id"]),
                "action_id": action_id,
                "event_type": str(row["event_type"]),
                "occurred_at": str(row["occurred_at"]),
                "attempt": int(row["attempt"]),
                "actor": str(row["actor"]),
                "source_revision": str(row["source_revision"]),
                "source_state": str(row["source_state"]),
                "necessity_reason": str(row["necessity_reason"]),
                "blocker_key": str(row["blocker_key"]),
                "blocker_fingerprint": str(row["blocker_fingerprint"]),
                "retry_not_before": str(row["retry_not_before"]),
                "evidence_json": str(row["evidence_json"]),
                "program_digest": str(row["program_digest"]),
                "previous_event_hash": str(row["previous_event_hash"]),
                "external_action_performed": 0,
            }
            expected_hash = canonical_digest(basis)
            if str(row["event_hash"]) != expected_hash:
                raise CloudAdvancementError(
                    "Cloud action history event hash is invalid."
                )
            if int(row["attempt"]) > int(
                action_by_id[action_id]["max_attempts"]
            ):
                raise CloudAdvancementError(
                    "Cloud action history exceeds an attempt limit."
                )
            run_events = runs.setdefault(str(row["run_id"]), [])
            run_events.append(str(row["event_type"]))
            if run_events[0] != "claimed":
                raise CloudAdvancementError(
                    "Cloud action run does not begin with a claim."
                )
            if run_events.count("claimed") != 1:
                raise CloudAdvancementError(
                    "Cloud action run contains multiple claims."
                )
            if len(
                [
                    item
                    for item in run_events
                    if item in {"completed", "blocked", "failed", "expired"}
                ]
            ) > 1:
                raise CloudAdvancementError(
                    "Cloud action run contains multiple terminal events."
                )
            if row["event_type"] == "claimed":
                expected_fingerprint = canonical_digest(
                    {
                        "category": " ".join(
                            str(
                                action_by_id[action_id]["category"]
                            ).split()
                        ).casefold(),
                        "objective": " ".join(
                            str(
                                action_by_id[action_id]["objective"]
                            ).split()
                        ).casefold(),
                        "required_outputs": sorted(
                            " ".join(str(item).split()).casefold()
                            for item in action_by_id[action_id][
                                "required_outputs"
                            ]
                        ),
                        "acceptance_checks": sorted(
                            " ".join(str(item).split()).casefold()
                            for item in action_by_id[action_id][
                                "acceptance_checks"
                            ]
                        ),
                    }
                )
                if payload.get("action_fingerprint") != (
                    expected_fingerprint
                ):
                    raise CloudAdvancementError(
                        "Cloud claim fingerprint is invalid."
                    )
            previous_hash = expected_hash

    def _verify_anchor(
        self,
        events: Sequence[Mapping[str, Any]],
        *,
        anchor_receipt: Path | None,
    ) -> dict[str, Any]:
        paths: list[Path] = []
        configured = Path(
            str(self.assurance["verification"]["anchor_receipt"])
        )
        if (
            configured.is_absolute()
            and configured.exists()
            or (self.root / configured).exists()
        ):
            paths.append(configured)
        checkpoint_directory = _safe_runtime_path(
            self.root,
            Path(
                str(
                    self.assurance["verification"][
                        "checkpoint_directory"
                    ]
                )
            ),
            "cloud assurance checkpoint directory",
        )
        if checkpoint_directory.exists():
            paths.extend(
                path.relative_to(self.root)
                for path in sorted(checkpoint_directory.glob("*.json"))
                if path.is_file()
            )
        if anchor_receipt and anchor_receipt not in paths:
            paths.append(anchor_receipt)

        anchors: list[dict[str, Any]] = []
        seen_paths: set[Path] = set()
        for path in paths:
            candidate = (
                path if path.is_absolute() else self.root / path
            ).resolve()
            if candidate in seen_paths:
                continue
            seen_paths.add(candidate)
            if not candidate.exists():
                raise CloudAdvancementError(
                    "A requested assurance checkpoint receipt is missing."
                )
            anchor = validate_verification_receipt(
                self.root,
                path,
                assurance=self.assurance,
                program=self.program,
                state_path=self.state_path,
                historical=True,
            )
            anchor_count = int(
                anchor["assurance_history"]["event_count"]
            )
            anchor_head = str(
                anchor["assurance_history"]["history_head_sha256"]
            )
            if len(events) < anchor_count:
                raise CloudAdvancementError(
                    "Assurance history is shorter than its trusted anchor."
                )
            observed_head = (
                str(events[anchor_count - 1]["event_hash"])
                if anchor_count
                else "0" * 64
            )
            if observed_head != anchor_head:
                raise CloudAdvancementError(
                    "Assurance history is not an append-only anchor "
                    "extension."
                )
            anchors.append(anchor)

        strongest = max(
            anchors,
            key=lambda item: int(
                item["assurance_history"]["event_count"]
            ),
            default=None,
        )
        anchor_count = (
            int(strongest["assurance_history"]["event_count"])
            if strongest
            else 0
        )
        anchor_head = (
            str(strongest["assurance_history"]["history_head_sha256"])
            if strongest
            else "0" * 64
        )
        return {
            "event_count": len(events),
            "history_head_sha256": (
                str(events[-1]["event_hash"]) if events else "0" * 64
            ),
            "trusted_checkpoint_count": len(anchors),
            "anchor_policy": "required_if_present",
            "anchor_observation": (
                "verified" if strongest else "not_present"
            ),
            "anchor_receipt_digest": (
                str(strongest["receipt_digest"]) if strongest else ""
            ),
            "anchor_event_count": anchor_count,
            "anchor_history_head_sha256": anchor_head,
        }

    def _artifact_manifest(self) -> list[dict[str, Any]]:
        manifest: list[dict[str, Any]] = []
        for relative in self.assurance["verification"][
            "required_artifacts"
        ]:
            path = _safe_input_path(
                self.root,
                Path(str(relative)),
                "required cloud assurance artifact",
            )
            data = path.read_bytes()
            if not data:
                raise CloudAdvancementError(
                    f"Required assurance artifact is empty: {relative}."
                )
            manifest.append(
                {
                    "path": str(relative).replace("\\", "/"),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size_bytes": len(data),
                }
            )
        return manifest

    def _measure_performance(
        self,
        snapshot: sqlite3.Connection,
        now: datetime,
        *,
        database_bytes: int,
    ) -> dict[str, Any]:
        policy = dict(self.assurance["performance"])
        clock_info = time.get_clock_info("perf_counter")
        if not clock_info.monotonic:
            raise CloudAdvancementError(
                "The configured performance clock is not monotonic."
            )
        warmups = int(policy["warmup_iterations"])
        sample_count = int(policy["sample_count"])

        def integrity_probe() -> None:
            if snapshot.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise CloudAdvancementError(
                    "SQLite quick-check failed during benchmark."
                )
            self._validate_history(snapshot)

        def memory_probe() -> None:
            events = self._read_events(snapshot)
            self._recall_from_events(
                events,
                query="",
                scope="program",
                action_id="",
                run_id="",
                limit=int(
                    self.assurance["working_memory"][
                        "default_recall_limit"
                    ]
                ),
                now=now,
            )

        def metric_probe() -> None:
            self._metric_summary_from_events(
                self._read_events(snapshot)
            )

        operations = {
            "integrity_check": self._measure_operation(
                integrity_probe,
                warmups,
                sample_count,
                policy["budgets_ms"]["integrity_check_p95"],
            ),
            "memory_recall": self._measure_operation(
                memory_probe,
                warmups,
                sample_count,
                policy["budgets_ms"]["memory_recall_p95"],
            ),
            "metric_summary": self._measure_operation(
                metric_probe,
                warmups,
                sample_count,
                policy["budgets_ms"]["metric_summary_p95"],
            ),
        }
        workload_events = self._read_events(snapshot)
        metric_source_paths = {
            _safe_input_path(
                self.root,
                Path(str(definition["source_ref"])),
                "quantitative performance source",
            )
            for definition in self.metric_by_id.values()
        }
        metric_source_bytes = sum(
            len(
                _read_bounded_file(
                    path,
                    int(self.assurance["provenance"]["max_source_bytes"]),
                    "Quantitative performance source",
                )
            )
            for path in metric_source_paths
        )
        return {
            "clock": "perf_counter_ns",
            "percentile_method": "nearest_rank",
            "measurement_scope": (
                "hot_cache_sqlite_and_workspace_probes_not_end_to_end"
            ),
            "sample_count": sample_count,
            "warmup_iterations": warmups,
            "environment_bound_observation": True,
            "cross_host_claim": False,
            "environment": {
                "python_implementation": platform.python_implementation(),
                "python_version": platform.python_version(),
                "platform_system": platform.system() or "unknown",
                "platform_release": platform.release() or "unknown",
                "clock_resolution_seconds": decimal_text(
                    Decimal(str(clock_info.resolution))
                ),
                "clock_monotonic": True,
            },
            "workload": {
                "event_count": len(workload_events),
                "memory_event_count": sum(
                    1
                    for event in workload_events
                    if event["event_type"] == "memory_recorded"
                ),
                "metric_event_count": sum(
                    1
                    for event in workload_events
                    if event["event_type"] == "metric_evaluated"
                ),
                "metric_source_count": len(metric_source_paths),
                "metric_source_bytes": metric_source_bytes,
                "database_bytes": int(database_bytes),
            },
            "operations": operations,
            "all_budgets_passed": all(
                operation["passed"] for operation in operations.values()
            ),
        }

    def _measure_operation(
        self,
        operation: Callable[[], None],
        warmup_count: int,
        sample_count: int,
        budget_ms: str,
    ) -> dict[str, Any]:
        warmups = [
            self._timed_call(operation) for _ in range(warmup_count)
        ]
        samples = [
            self._timed_call(operation) for _ in range(sample_count)
        ]
        budget_decimal = parse_decimal(
            budget_ms,
            "performance p95 budget",
        )
        budget_ns_decimal = budget_decimal * Decimal(1_000_000)
        if budget_ns_decimal != budget_ns_decimal.to_integral_value():
            raise CloudAdvancementError(
                "Performance budget must resolve to whole nanoseconds."
            )
        budget_ns = int(budget_ns_decimal)
        p50 = nearest_rank(samples, Decimal("0.50"))
        p95 = nearest_rank(samples, Decimal("0.95"))
        p99 = nearest_rank(samples, Decimal("0.99"))
        minimum = min(samples)
        maximum = max(samples)
        mean = sum(samples) // len(samples)
        if not minimum <= p50 <= p95 <= p99 <= maximum:
            raise CloudAdvancementError(
                "Performance statistics are internally inconsistent."
            )
        return {
            "warmup_ns": warmups,
            "samples_ns": samples,
            "minimum_ns": minimum,
            "mean_ns": mean,
            "p50_ns": p50,
            "p95_ns": p95,
            "p99_ns": p99,
            "maximum_ns": maximum,
            "budget_p95_ns": budget_ns,
            "passed": p95 <= budget_ns,
        }

    def _timed_call(self, operation: Callable[[], None]) -> int:
        started = int(self.clock())
        operation()
        finished = int(self.clock())
        elapsed = finished - started
        if elapsed <= 0:
            raise CloudAdvancementError(
                "Performance clock did not advance monotonically."
            )
        return elapsed


def validate_verification_receipt_payload(
    receipt: Mapping[str, Any],
    project_root: Path,
    schema_path: Path = DEFAULT_VERIFICATION_RECEIPT_SCHEMA_PATH,
) -> dict[str, Any]:
    payload = dict(receipt)
    schema = _load_assurance_json_object(
        _safe_input_path(
            project_root.resolve(),
            schema_path,
            "cloud assurance verification receipt schema",
        )
    )
    _strict_assurance_validate(payload, schema)
    _validate_verification_receipt_semantics(payload)
    digest_basis = dict(payload)
    recorded_digest = str(digest_basis.pop("receipt_digest", ""))
    if recorded_digest != canonical_digest(digest_basis):
        raise CloudAdvancementError(
            "Cloud assurance verification receipt digest is invalid."
        )
    return payload


def _validate_verification_receipt_semantics(
    receipt: Mapping[str, Any],
) -> None:
    performance = dict(receipt["performance"])
    sample_count = int(performance["sample_count"])
    warmup_count = int(performance["warmup_iterations"])
    operation_passes: list[bool] = []
    for name, raw_stats in performance["operations"].items():
        stats = dict(raw_stats)
        warmups = [int(value) for value in stats["warmup_ns"]]
        samples = [int(value) for value in stats["samples_ns"]]
        if len(warmups) != warmup_count or len(samples) != sample_count:
            raise CloudAdvancementError(
                f"Performance sample count is invalid for {name}."
            )
        expected = {
            "minimum_ns": min(samples),
            "mean_ns": sum(samples) // len(samples),
            "p50_ns": nearest_rank(samples, Decimal("0.50")),
            "p95_ns": nearest_rank(samples, Decimal("0.95")),
            "p99_ns": nearest_rank(samples, Decimal("0.99")),
            "maximum_ns": max(samples),
        }
        for field, value in expected.items():
            if int(stats[field]) != value:
                raise CloudAdvancementError(
                    f"Performance statistic {name}.{field} is invalid."
                )
        operation_passed = int(stats["p95_ns"]) <= int(
            stats["budget_p95_ns"]
        )
        if bool(stats["passed"]) != operation_passed:
            raise CloudAdvancementError(
                f"Performance verdict for {name} is invalid."
            )
        operation_passes.append(operation_passed)
    if bool(performance["all_budgets_passed"]) != all(operation_passes):
        raise CloudAdvancementError(
            "Overall performance budget verdict is invalid."
        )

    memory = dict(receipt["working_memory"])
    if bool(memory["within_capacity"]) != (
        int(memory["active_entry_count"]) <= int(memory["capacity"])
    ):
        raise CloudAdvancementError(
            "Working-memory entry-capacity verdict is invalid."
        )
    if bool(memory["scope_bytes_within_capacity"]) != (
        int(memory["max_active_scope_bytes_observed"])
        <= int(memory["max_active_bytes_per_scope"])
    ):
        raise CloudAdvancementError(
            "Working-memory scope-byte verdict is invalid."
        )
    if bool(memory["database_bytes_within_capacity"]) != (
        int(memory["database_bytes"]) <= int(memory["max_database_bytes"])
    ):
        raise CloudAdvancementError(
            "Working-memory database-byte verdict is invalid."
        )
    memory_valid = bool(
        int(memory["active_entry_count"]) <= int(memory["capacity"])
        and memory["within_capacity"]
        and memory["scope_bytes_within_capacity"]
        and memory["database_bytes_within_capacity"]
        and memory["run_bindings_valid"]
        and memory["sources_current"]
        and int(memory["active_entry_count"])
        >= int(memory["minimum_active_entries"])
    )
    if bool(memory["sources_current"]) != (
        int(memory["source_drift_count"]) == 0
    ):
        raise CloudAdvancementError(
            "Working-memory provenance-drift verdict is invalid."
        )
    if bool(memory["minimum_satisfied"]) != (
        int(memory["active_entry_count"])
        >= int(memory["minimum_active_entries"])
    ):
        raise CloudAdvancementError(
            "Working-memory minimum verdict is invalid."
        )

    quantitative = dict(receipt["quantitative_accuracy"])
    distinct = int(quantitative["distinct_metric_count"])
    passed_count = int(quantitative["current_passed_count"])
    failed_count = int(quantitative["current_failed_count"])
    if passed_count + failed_count != distinct:
        raise CloudAdvancementError(
            "Quantitative metric summary counts do not reconcile."
        )
    with localcontext() as context:
        context.prec = 50
        expected_rate = (
            Decimal(passed_count) / Decimal(distinct)
            if distinct
            else Decimal(0)
        )
    if parse_decimal(
        quantitative["pass_rate"],
        "quantitative pass rate",
    ) != expected_rate:
        raise CloudAdvancementError(
            "Quantitative metric pass rate is invalid."
        )
    quantitative_valid = bool(
        distinct >= int(quantitative["minimum_distinct_metrics"])
        and not quantitative["missing_required_metric_ids"]
        and failed_count == 0
        and quantitative["minimum_satisfied"]
        and quantitative["all_current_metrics_passed"]
    )
    if int(quantitative["required_metric_count"]) != int(
        quantitative["minimum_distinct_metrics"]
    ):
        raise CloudAdvancementError(
            "Quantitative required-metric count is inconsistent."
        )
    if bool(quantitative["minimum_satisfied"]) != (
        not quantitative["missing_required_metric_ids"]
    ):
        raise CloudAdvancementError(
            "Quantitative required-metric verdict is inconsistent."
        )

    checks = dict(receipt["checks"])
    workload = dict(performance["workload"])
    history = dict(receipt["assurance_history"])
    if int(workload["event_count"]) != int(history["event_count"]):
        raise CloudAdvancementError(
            "Performance workload and assurance history do not reconcile."
        )
    if int(workload["memory_event_count"]) != int(
        memory["memory_event_count"]
    ):
        raise CloudAdvancementError(
            "Performance workload and memory event counts do not reconcile."
        )
    if int(workload["metric_event_count"]) != int(
        quantitative["metric_event_count"]
    ):
        raise CloudAdvancementError(
            "Performance workload and metric event counts do not reconcile."
        )
    if int(workload["database_bytes"]) != int(memory["database_bytes"]):
        raise CloudAdvancementError(
            "Performance and memory database bytes do not reconcile."
        )
    anchor_verified = history["anchor_observation"] == "verified"
    if anchor_verified:
        if (
            int(history["trusted_checkpoint_count"]) < 1
            or not history["anchor_receipt_digest"]
            or int(history["anchor_event_count"])
            > int(history["event_count"])
        ):
            raise CloudAdvancementError(
                "Verified assurance anchor metadata is inconsistent."
            )
    elif (
        int(history["trusted_checkpoint_count"]) != 0
        or history["anchor_receipt_digest"]
        or int(history["anchor_event_count"]) != 0
        or history["anchor_history_head_sha256"] != "0" * 64
    ):
        raise CloudAdvancementError(
            "Absent assurance anchor metadata is inconsistent."
        )
    if checks["working_memory_valid"] != memory_valid:
        raise CloudAdvancementError(
            "Working-memory verification check is inconsistent."
        )
    if checks["quantitative_accuracy_valid"] != quantitative_valid:
        raise CloudAdvancementError(
            "Quantitative verification check is inconsistent."
        )
    if checks["performance_budgets_valid"] != all(operation_passes):
        raise CloudAdvancementError(
            "Performance verification check is inconsistent."
        )
    if bool(receipt["assurance_passed"]) != all(
        bool(value) for value in checks.values()
    ):
        raise CloudAdvancementError(
            "Overall verification receipt verdict is inconsistent."
        )
    if receipt["execution_authorized"] is not False:
        raise CloudAdvancementError(
            "Assurance verification cannot grant execution authority."
        )


def _safe_assurance_receipt_output_path(
    project_root: Path,
    value: Path,
    assurance: Mapping[str, Any],
) -> Path:
    root = project_root.resolve()
    path = (value if value.is_absolute() else root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise CloudAdvancementError(
            "Cloud assurance receipt must remain inside the workspace."
        ) from exc
    configured_anchor = (
        root / Path(str(assurance["verification"]["anchor_receipt"]))
    ).resolve()
    checkpoint_directory = _safe_runtime_path(
        root,
        Path(str(assurance["verification"]["checkpoint_directory"])),
        "cloud assurance checkpoint directory",
    )
    discoverable = (
        path == configured_anchor
        or path.parent == checkpoint_directory
    )
    if (
        not discoverable
        or path.suffix != ".json"
        or path.name.startswith(".")
    ):
        raise CloudAdvancementError(
            "Cloud assurance receipt must be the configured baseline or a "
            "direct JSON child of the governed checkpoint directory."
        )
    return path


def validate_verification_receipt(
    project_root: Path,
    receipt_path: Path,
    schema_path: Path | None = None,
    *,
    assurance: Mapping[str, Any] | None = None,
    program: Mapping[str, Any] | None = None,
    state_path: Path | None = None,
    historical: bool = False,
) -> dict[str, Any]:
    root = project_root.resolve()
    receipt = _load_assurance_json_object(
        _safe_input_path(
            root,
            receipt_path,
            "cloud assurance verification receipt",
        )
    )
    payload = validate_verification_receipt_payload(
        receipt,
        root,
        schema_path or DEFAULT_VERIFICATION_RECEIPT_SCHEMA_PATH,
    )
    selected_assurance = (
        dict(assurance) if assurance is not None else load_assurance_config(root)
    )
    selected_program = (
        dict(program)
        if program is not None
        else load_program(
            root,
            Path(str(selected_assurance["program_config"])),
        )
    )
    if payload["assurance_digest"] != canonical_digest(selected_assurance):
        raise CloudAdvancementError(
            "Verification receipt is not bound to the local assurance policy."
        )
    if payload["program_digest"] != canonical_digest(selected_program):
        raise CloudAdvancementError(
            "Verification receipt is not bound to the local cloud program."
        )
    if payload["assurance_version"] != selected_assurance["version"]:
        raise CloudAdvancementError(
            "Verification receipt assurance version is not current."
        )
    if payload["program_version"] != selected_program["version"]:
        raise CloudAdvancementError(
            "Verification receipt program version is not current."
        )

    performance_policy = selected_assurance["performance"]
    if int(payload["performance"]["sample_count"]) != int(
        performance_policy["sample_count"]
    ) or int(payload["performance"]["warmup_iterations"]) != int(
        performance_policy["warmup_iterations"]
    ):
        raise CloudAdvancementError(
            "Verification receipt sampling policy is not current."
        )
    budget_names = {
        "integrity_check": "integrity_check_p95",
        "memory_recall": "memory_recall_p95",
        "metric_summary": "metric_summary_p95",
    }
    for operation, budget_name in budget_names.items():
        expected_budget = int(
            parse_decimal(
                performance_policy["budgets_ms"][budget_name],
                f"performance budget {budget_name}",
            )
            * Decimal(1_000_000)
        )
        if int(
            payload["performance"]["operations"][operation][
                "budget_p95_ns"
            ]
        ) != expected_budget:
            raise CloudAdvancementError(
                "Verification receipt performance budget is not current."
            )

    expected_manifest: list[dict[str, Any]] = []
    for relative in selected_assurance["verification"]["required_artifacts"]:
        path = _safe_input_path(
            root,
            Path(str(relative)),
            "required cloud assurance artifact",
        )
        data = path.read_bytes()
        expected_manifest.append(
            {
                "path": str(relative).replace("\\", "/"),
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
        )
    if payload["artifact_manifest"] != expected_manifest:
        raise CloudAdvancementError(
            "Verification receipt artifact manifest is not current."
        )

    store = CloudAdvancementAssuranceStore(
        root,
        selected_program,
        selected_assurance,
        state_path=state_path,
        initialize=False,
    )
    snapshot = store._snapshot()
    try:
        integrity_rows = [
            str(row[0])
            for row in snapshot.execute("PRAGMA integrity_check").fetchall()
        ]
        foreign_keys_enabled = (
            int(snapshot.execute("PRAGMA foreign_keys").fetchone()[0]) == 1
        )
        declared_foreign_keys = snapshot.execute(
            "PRAGMA foreign_key_list(cloud_assurance_events)"
        ).fetchall()
        foreign_key_violations = snapshot.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        append_only_valid = bool(
            store._append_only_controls_valid(snapshot)
            and store._functional_append_only_controls_valid(snapshot)
        )
        append_only_trigger_count = len(
            snapshot.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                  AND name LIKE 'assurance_%'
                """
            ).fetchall()
        )
        binding_valid = store._binding_valid(snapshot)
        events = store._validate_history(snapshot)
        current_database_bytes = store._database_bytes(snapshot)
    finally:
        snapshot.close()
    sqlite_integrity = integrity_rows == ["ok"]
    foreign_keys_valid = bool(
        foreign_keys_enabled
        and store._foreign_key_topology_valid(declared_foreign_keys)
        and not foreign_key_violations
    )
    expected_database_integrity = {
        "integrity_result": "ok" if sqlite_integrity else "failed",
        "foreign_keys_enabled": foreign_keys_enabled,
        "declared_foreign_key_count": len(declared_foreign_keys),
        "foreign_key_violation_count": len(foreign_key_violations),
        "append_only_trigger_count": append_only_trigger_count,
    }
    if payload["database_integrity"] != expected_database_integrity:
        raise CloudAdvancementError(
            "Verification receipt database-integrity claims are invalid."
        )
    structural_checks = {
        "program_and_assurance_config_valid": True,
        "sqlite_integrity_valid": sqlite_integrity,
        "foreign_keys_valid": foreign_keys_valid,
        "append_only_controls_valid": append_only_valid,
        "event_chain_valid": True,
        "program_binding_valid": binding_valid,
        "assurance_binding_valid": binding_valid,
        "required_artifacts_present": True,
        "secrets_absent": True,
    }
    for name, expected in structural_checks.items():
        if bool(payload["checks"][name]) != expected:
            raise CloudAdvancementError(
                f"Verification receipt structural check {name} is invalid."
            )
    receipt_count = int(payload["assurance_history"]["event_count"])
    if len(events) < receipt_count:
        raise CloudAdvancementError(
            "Verification receipt references missing assurance history."
        )
    prefix_head = (
        str(events[receipt_count - 1]["event_hash"])
        if receipt_count
        else "0" * 64
    )
    if prefix_head != payload["assurance_history"]["history_head_sha256"]:
        raise CloudAdvancementError(
            "Verification receipt assurance history prefix is invalid."
        )
    prefix = events[:receipt_count]
    verified_at = parse_datetime(str(payload["verified_at"]))
    loop_rows = store._read_validated_loop_rows()
    loop_rows_as_of = (
        [
            row
            for row in loop_rows
            if parse_datetime(str(row["occurred_at"])) <= verified_at
        ]
        if loop_rows is not None
        else []
    )
    expected_loop_state = {
        "policy": "verify_if_present",
        "observation": (
            "verified" if loop_rows_as_of else "not_present"
        ),
        "event_count": len(loop_rows_as_of),
        "history_head_sha256": (
            str(loop_rows_as_of[-1]["event_hash"])
            if loop_rows_as_of
            else "0" * 64
        ),
    }
    if payload["loop_state"] != expected_loop_state:
        raise CloudAdvancementError(
            "Verification receipt loop-state observation is invalid."
        )
    if not payload["checks"]["loop_history_valid"]:
        raise CloudAdvancementError(
            "Verification receipt loop-history check is invalid."
        )
    expected_memory = store._memory_summary_from_events(
        prefix,
        verified_at,
        database_bytes=int(payload["working_memory"]["database_bytes"]),
        loop_rows=loop_rows,
    )
    current_only_fields = (
        {"source_drift_count", "sources_current"}
        if historical
        else set()
    )
    stable_expected_memory = {
        key: value
        for key, value in expected_memory.items()
        if key not in current_only_fields
    }
    stable_receipt_memory = {
        key: value
        for key, value in payload["working_memory"].items()
        if key not in current_only_fields
    }
    if stable_expected_memory != stable_receipt_memory:
        raise CloudAdvancementError(
            "Verification receipt working-memory summary is invalid."
        )
    if receipt_count == len(events) and int(
        payload["working_memory"]["database_bytes"]
    ) != current_database_bytes:
        raise CloudAdvancementError(
            "Verification receipt database-byte observation is invalid."
        )
    expected_metrics = store._metric_summary_from_events(prefix)
    if expected_metrics != payload["quantitative_accuracy"]:
        raise CloudAdvancementError(
            "Verification receipt quantitative summary is invalid."
        )
    history = payload["assurance_history"]
    anchor_count = int(history["anchor_event_count"])
    anchor_prefix_head = (
        str(events[anchor_count - 1]["event_hash"])
        if anchor_count
        else "0" * 64
    )
    if anchor_prefix_head != history["anchor_history_head_sha256"]:
        raise CloudAdvancementError(
            "Verification receipt anchor prefix is invalid."
        )
    if history["anchor_observation"] == "verified":
        checkpoint_paths: list[Path] = []
        configured_anchor = Path(
            str(
                selected_assurance["verification"]["anchor_receipt"]
            )
        )
        configured_candidate = (
            configured_anchor
            if configured_anchor.is_absolute()
            else root / configured_anchor
        ).resolve()
        if configured_candidate.exists():
            checkpoint_paths.append(configured_candidate)
        checkpoint_directory = _safe_runtime_path(
            root,
            Path(
                str(
                    selected_assurance["verification"][
                        "checkpoint_directory"
                    ]
                )
            ),
            "cloud assurance checkpoint directory",
        )
        if checkpoint_directory.exists():
            checkpoint_paths.extend(
                path.resolve()
                for path in checkpoint_directory.glob("*.json")
                if path.is_file()
            )
        current_receipt_path = (
            receipt_path
            if receipt_path.is_absolute()
            else root / receipt_path
        ).resolve()
        available_checkpoints: dict[str, dict[str, Any]] = {}
        for candidate in set(checkpoint_paths):
            if candidate == current_receipt_path:
                continue
            candidate_payload = validate_verification_receipt_payload(
                _load_assurance_json_object(candidate),
                root,
                schema_path or DEFAULT_VERIFICATION_RECEIPT_SCHEMA_PATH,
            )
            available_checkpoints[
                str(candidate_payload["receipt_digest"])
            ] = candidate_payload
        referenced_checkpoint = available_checkpoints.get(
            str(history["anchor_receipt_digest"])
        )
        if referenced_checkpoint is None:
            raise CloudAdvancementError(
                "Verification receipt references an unavailable trusted "
                "checkpoint."
            )
        referenced_history = referenced_checkpoint["assurance_history"]
        if (
            int(history["anchor_event_count"])
            != int(referenced_history["event_count"])
            or history["anchor_history_head_sha256"]
            != referenced_history["history_head_sha256"]
        ):
            raise CloudAdvancementError(
                "Verification receipt anchor tuple does not match its "
                "referenced checkpoint."
            )
        if int(history["trusted_checkpoint_count"]) > len(
            available_checkpoints
        ):
            raise CloudAdvancementError(
                "Verification receipt trusted-checkpoint count is invalid."
            )
    metric_source_paths = {
        _safe_input_path(
            root,
            Path(str(definition["source_ref"])),
            "quantitative performance source",
        )
        for definition in selected_assurance["quantitative_accuracy"][
            "metric_definitions"
        ]
    }
    metric_source_bytes = sum(
        len(
            _read_bounded_file(
                path,
                int(selected_assurance["provenance"]["max_source_bytes"]),
                "Quantitative performance source",
            )
        )
        for path in metric_source_paths
    )
    if int(
        payload["performance"]["workload"]["metric_source_count"]
    ) != len(metric_source_paths) or int(
        payload["performance"]["workload"]["metric_source_bytes"]
    ) != metric_source_bytes:
        raise CloudAdvancementError(
            "Verification receipt performance source workload is invalid."
        )
    return payload


def load_default_assurance(
    project_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    assurance = load_assurance_config(project_root)
    program = load_program(
        project_root,
        Path(str(assurance["program_config"])),
    )
    return program, assurance
