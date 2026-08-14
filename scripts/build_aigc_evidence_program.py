#!/usr/bin/env python3
"""Build or verify the canonical AIGC evidence ledger and request bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.nexus.evidence_program import build_evidence_program

PROGRAM_PATH = ROOT / "reports/artifacts/aigc_evidence_program_local_validation.json"
REQUESTS_PATH = ROOT / "reports/evidence_requests/aigc_external_evidence_requests.v1.json"
REGISTRY_PATH = ROOT / "config/aigc_universal_integration_registry.v1.json"


def _serialized(value: dict[str, object]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program-output", type=Path, default=PROGRAM_PATH)
    parser.add_argument("--requests-output", type=Path, default=REQUESTS_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    program, requests = build_evidence_program(registry, ROOT)
    outputs = ((args.program_output, _serialized(program)), (args.requests_output, _serialized(requests)))
    if args.check:
        stale = [str(path) for path, content in outputs if not path.is_file() or path.read_text(encoding="utf-8") != content]
        if stale:
            print("Stale evidence artifacts: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("AIGC evidence program artifacts are current")
        return 0
    for path, content in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
