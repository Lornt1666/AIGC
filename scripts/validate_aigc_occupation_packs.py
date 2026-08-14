from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.nexus.occupation import OccupationPack


DEFAULT_DIRECTORY = PROJECT_ROOT / "config" / "occupation_packs"
DEFAULT_SCHEMA = PROJECT_ROOT / "schemas" / "aigc_occupation_pack.schema.json"


def validate_pack_directory(directory: Path, schema_path: Path) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    records: list[dict[str, Any]] = []
    ids: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        try:
            raw_bytes = path.read_bytes()
            value = json.loads(raw_bytes)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot load {path}: {exc}") from None
        errors = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
        if errors:
            location = "/".join(str(item) for item in errors[0].absolute_path) or "<root>"
            raise ValueError(f"{path.name} schema violation at {location}: {errors[0].message}")
        try:
            pack = OccupationPack.model_validate(value)
        except ValidationError as exc:
            raise ValueError(f"{path.name} semantic violation: {exc.errors()[0]['msg']}") from None
        if pack.pack_id in ids:
            raise ValueError(f"duplicate occupation pack id: {pack.pack_id}")
        ids.add(pack.pack_id)
        records.append(
            {
                "pack_id": pack.pack_id,
                "version": pack.version,
                "status": pack.status,
                "capability_count": len(pack.capabilities),
                "sha256": sha256(raw_bytes).hexdigest(),
                "grants_external_authority": False,
            }
        )
    required_pack_ids = {
        "OCC-SOFTWARE_RESEARCH_ASSISTANT",
        "OCC-ADMINISTRATIVE_COORDINATOR",
        "OCC-DATA_ANALYSIS_REPORTING",
        "OCC-DEEP_RESEARCH_ANALYST",
    }
    missing = sorted(required_pack_ids - ids)
    if missing:
        raise ValueError(f"required occupation packs are missing: {', '.join(missing)}")
    return {
        "status": "PASS",
        "pack_count": len(records),
        "certified_pack_count": sum(item["status"] == "CERTIFIED" for item in records),
        "external_authority_granted": False,
        "external_action_performed": False,
        "packs": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate_pack_directory(args.directory, args.schema)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
