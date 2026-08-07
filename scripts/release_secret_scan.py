from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json

from src.security.redaction_scanner import RedactionScanner


RELEASE_PATHS = (
    ".github/workflows/aigc-ci.yml",
    "config/exact_sha_ci_validation_contract.json",
    "scripts/release_secret_scan.py",
    "scripts/run_exact_sha_ci_contract.py",
    "scripts/validate_colosseum_persistence.py",
    "scripts/verify_colosseum_false_authority.py",
    "src/colosseum",
    "schemas/colosseum",
    "schemas/employers",
    "schemas/engagement",
    "schemas/verification",
    "schemas/compute_exchange",
    "tests/colosseum",
    "docs/architecture/AIGC_COLOSSEUM_ORCHESTRATION_KERNEL_V1.md",
)


def main() -> int:
    scanner = RedactionScanner()
    findings = scanner.scan_paths([Path(item) for item in RELEASE_PATHS])
    payload = {
        "schema_version": "1.0.0",
        "paths": list(RELEASE_PATHS),
        "finding_count": len(findings),
        "findings": scanner.findings_as_dicts(findings),
        "external_action_performed": False,
        "production_activation_authorized": False,
    }
    print(json.dumps(payload, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
