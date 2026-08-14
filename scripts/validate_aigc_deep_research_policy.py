from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
from pydantic import ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.nexus.research import DeepResearchPolicy


DEFAULT_POLICY = PROJECT_ROOT / "config" / "aigc_deep_research_policy.v1.json"
DEFAULT_SCHEMA = PROJECT_ROOT / "schemas" / "aigc_deep_research_policy.schema.json"


def validate_policy(policy_path: Path, schema_path: Path) -> dict[str, object]:
    raw_bytes = policy_path.read_bytes()
    value = json.loads(raw_bytes)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        location = "/".join(str(item) for item in errors[0].absolute_path) or "<root>"
        raise ValueError(f"schema violation at {location}: {errors[0].message}")
    policy = DeepResearchPolicy.model_validate(value)
    return {
        "status": "PASS",
        "policy_id": policy.policy_id,
        "policy_sha256": sha256(raw_bytes).hexdigest(),
        "stage_count": len(policy.stages),
        "source_tier_count": len(policy.source_ladder),
        "provider_dispatch_enabled": False,
        "provider_call_count": 0,
        "external_action_performed": False,
        "authority_granted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate_policy(args.policy, args.schema)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
