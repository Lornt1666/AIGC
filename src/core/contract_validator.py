from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "schemas"


class ContractValidationError(ValueError):
    """Raised when an AIGC artifact does not match its contract."""


@dataclass(frozen=True)
class ValidationResult:
    schema_name: str
    path: str
    record_count: int
    valid: bool


def load_schema(name: str, schema_dir: Path | None = None) -> Dict[str, Any]:
    schema_path = _schema_path(name, schema_dir)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    if not isinstance(schema, dict):
        raise ContractValidationError(f"Schema {name} is not a JSON object.")
    return schema


def validate_artifact(schema_name: str, data: Any, schema_dir: Path | None = None) -> Any:
    schema = load_schema(schema_name, schema_dir=schema_dir)
    errors = list(_validate_value(data, schema, "$"))
    if errors:
        raise ContractValidationError(
            f"{schema_name} validation failed: " + "; ".join(errors[:10])
        )
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


def _validate_value(value: Any, schema: Dict[str, Any], path: str) -> Iterable[str]:
    expected_type = schema.get("type")
    if expected_type and not _matches_type(value, expected_type):
        yield f"{path} expected {expected_type}, got {_json_type(value)}"
        return

    enum_values = schema.get("enum")
    if enum_values is not None and value not in enum_values:
        yield f"{path} expected one of {enum_values}, got {value!r}"

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                yield f"{path}.{key} is required"
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value:
                yield from _validate_value(value[key], child_schema, f"{path}.{key}")

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            yield f"{path} expected at least {min_items} items"
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                yield from _validate_value(item, item_schema, f"{path}[{index}]")


def _matches_type(value: Any, expected_type: str | List[str]) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_type(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _json_type(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    return type(value).__name__
