from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError
from jsonschema.validators import validator_for


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "schemas"


class ContractValidationError(ValueError):
    """Raised when an AIGC artifact or schema does not satisfy its contract."""


@dataclass(frozen=True)
class ValidationResult:
    schema_name: str
    path: str
    record_count: int
    valid: bool


def load_schema(name: str, schema_dir: Path | None = None) -> Dict[str, Any]:
    """Load and structurally validate a JSON Schema document.

    The declared ``$schema`` dialect is honored when supported by ``jsonschema``.
    Invalid or unsupported schema documents fail closed before artifact validation.
    """
    schema_path = _schema_path(name, schema_dir)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    try:
        with schema_path.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ContractValidationError(f"Schema {schema_path} is not valid JSON: {exc}") from exc
    if not isinstance(schema, dict):
        raise ContractValidationError(f"Schema {name} is not a JSON object.")
    try:
        validator_cls = validator_for(schema)
        validator_cls.check_schema(schema)
    except SchemaError as exc:
        raise ContractValidationError(f"Schema {name} is invalid: {exc.message}") from exc
    return schema


def validate_artifact(schema_name: str, data: Any, schema_dir: Path | None = None) -> Any:
    """Validate one artifact with a standards-compliant JSON Schema validator.

    This replaces the former hand-written subset validator so governance schemas
    can rely on Draft 2020-12 controls including ``const``, ``pattern``,
    ``format``, ``additionalProperties``, ``uniqueItems``, and length/range
    constraints. Validation failures are deterministic, bounded, and fail closed.
    """
    schema = load_schema(schema_name, schema_dir=schema_dir)
    validator_cls = validator_for(schema)
    validator = validator_cls(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=_validation_error_sort_key)
    if errors:
        rendered = "; ".join(_render_validation_error(error) for error in errors[:10])
        raise ContractValidationError(f"{schema_name} validation failed: {rendered}")
    return data


def validate_file(schema_name: str, path: str | Path, schema_dir: Path | None = None) -> ValidationResult:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Artifact file not found: {file_path}")
    payload = _load_payload(file_path)
    records = payload if isinstance(payload, list) else [payload]
    for index, record in enumerate(records):
        try:
            validate_artifact(schema_name, record, schema_dir=schema_dir)
        except ContractValidationError as exc:
            raise ContractValidationError(
                f"{file_path} record {index} failed {schema_name}: {exc}"
            ) from exc
    return ValidationResult(
        schema_name=schema_name,
        path=str(file_path),
        record_count=len(records),
        valid=True,
    )


def validate_jsonl_file(schema_name: str, path: str | Path, schema_dir: Path | None = None) -> ValidationResult:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Artifact file not found: {file_path}")
    count = 0
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ContractValidationError(f"{file_path}:{line_number} invalid JSONL: {exc}") from exc
            try:
                validate_artifact(schema_name, payload, schema_dir=schema_dir)
            except ContractValidationError as exc:
                raise ContractValidationError(
                    f"{file_path}:{line_number} failed {schema_name}: {exc}"
                ) from exc
            count += 1
    return ValidationResult(
        schema_name=schema_name,
        path=str(file_path),
        record_count=count,
        valid=True,
    )


def list_schema_names(schema_dir: Path | None = None) -> List[str]:
    root = schema_dir or SCHEMA_DIR
    return sorted(path.name.removesuffix(".schema.json") for path in root.glob("*.schema.json"))


def _schema_path(name: str, schema_dir: Path | None = None) -> Path:
    root = schema_dir or SCHEMA_DIR
    clean_name = name.removesuffix(".schema.json")
    return root / f"{clean_name}.schema.json"


def _load_payload(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ContractValidationError(f"{path} is not valid JSON: {exc}") from exc


def _validation_error_sort_key(error: ValidationError) -> tuple[str, str]:
    return ("/".join(str(part) for part in error.absolute_path), error.message)


def _render_validation_error(error: ValidationError) -> str:
    path = "$"
    if error.absolute_path:
        path += "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}"
            for part in error.absolute_path
        )
    return f"{path}: {error.message}"
