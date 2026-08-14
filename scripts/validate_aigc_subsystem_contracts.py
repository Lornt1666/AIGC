#!/usr/bin/env python3
"""Validate the five local AIGC subsystem contracts and emit a receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.nexus.subsystem_contracts import build_local_validation_receipt, load_contract_set


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "aigc_subsystem_contracts.v1.json")
    parser.add_argument("--schema", type=Path, default=ROOT / "schemas" / "aigc_subsystem_contracts.schema.json")
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()

    contract_set = load_contract_set(args.config, args.schema)
    receipt = build_local_validation_receipt(contract_set)
    print(json.dumps(receipt, sort_keys=True, indent=2))
    if args.require_pass and receipt["terminal_status"] != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
