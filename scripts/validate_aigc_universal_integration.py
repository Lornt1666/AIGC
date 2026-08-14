#!/usr/bin/env python3
"""Validate and evaluate the AIGC universal integration registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.nexus.universal_integration import evaluate_registry, load_and_validate_registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("config/aigc_universal_integration_registry.v1.json"),
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("schemas/aigc_universal_integration_registry.schema.json"),
    )
    parser.add_argument("--require-production-ready", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    registry = load_and_validate_registry(args.registry, args.schema)
    readiness = evaluate_registry(registry)
    serialized = json.dumps(readiness.to_dict(), sort_keys=True, indent=2) + "\n"
    if args.check:
        target = args.output or Path(
            "reports/artifacts/aigc_universal_readiness_local_validation.json"
        )
        if not target.is_file() or target.read_text(encoding="utf-8") != serialized:
            print(f"Universal readiness receipt is stale: {target}", file=sys.stderr)
            return 1
        print(f"Universal readiness receipt is current: {target}")
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(serialized, end="")
    if args.require_production_ready and not readiness.production_ready:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
