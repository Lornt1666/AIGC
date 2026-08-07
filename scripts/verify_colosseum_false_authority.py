from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json

from scripts.validate_governed_orchestration_bundle import (
    build_governed_fixture,
)


PROHIBITED_TRUE_FIELDS = {
    "execution_authorized",
    "external_action_authorized",
    "merge_authorized",
    "deployment_authorized",
    "live_model_call_authorized",
    "financial_action_authorized",
    "external_action_performed",
    "production_activation_authorized",
    "external_authority_granted",
    "merge_authority_granted",
    "deployment_authority_granted",
    "live_model_call_authority_granted",
    "financial_authority_granted",
}


def walk(value: object, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if key in PROHIBITED_TRUE_FIELDS and item is not False:
                violations.append(f"{child} must be false")
            violations.extend(walk(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(walk(item, f"{path}[{index}]"))
    return violations


def main() -> int:
    bundle = build_governed_fixture().to_record()
    violations = walk(bundle)
    workflow = Path(".github/workflows/aigc-ci.yml").read_text(
        encoding="utf-8"
    )
    if "aigc-colosseum-orchestration-exact-head-" not in workflow:
        violations.append("workflow artifact name is not orchestration-scoped")
    if violations:
        raise SystemExit("\n".join(violations))
    print(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "false_authority": "PASS",
                "checked_fields": sorted(PROHIBITED_TRUE_FIELDS),
                "external_action_performed": False,
                "production_activation_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
