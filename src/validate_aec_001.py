from __future__ import annotations

import json
from pathlib import Path

from core.governance.constitution_gate import ConstitutionGate, load_json
from core.governance.constitutional_lifecycle import validate_governance_registry


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    constitution = load_json(root / "governance" / "constitution" / "aec_001.registry.json")
    governance_registry = json.loads((root / "governance" / "governance_registry.json").read_text(encoding="utf-8"))

    constitution_result = ConstitutionGate(constitution).validate_registry()
    governance_result = validate_governance_registry(governance_registry)

    reasons = sorted(set(constitution_result.reason_codes + governance_result.reason_codes))
    payload = {
        "constitution_id": "AEC-001",
        "constitution_version": constitution.get("version"),
        "constitution_gate_passed": constitution_result.passed,
        "governance_registry_passed": governance_result.passed,
        "reason_codes": reasons,
        "external_action_performed": False,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
