#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.autopoiesis import (
    AutopoieticKernel,
    CycleRequest,
    load_ecosystem_config,
    load_fabric_registry,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "aigc_autopoietic_ecosystem.v1.json"
DEFAULT_FABRIC = ROOT / "config" / "aigc_adapter_fabric.v1.json"
DEFAULT_REQUEST = ROOT / "config" / "aigc_autopoietic_local_cycle.example.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one finite, deterministic, zero-egress AIGC autopoietic local-shadow cycle."
        )
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--fabric", type=Path, default=DEFAULT_FABRIC)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional local JSON receipt path. No path means stdout only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ecosystem = load_ecosystem_config(args.config)
    fabric = load_fabric_registry(args.fabric)
    request = CycleRequest.model_validate_json(args.request.read_text(encoding="utf-8"))
    kernel = AutopoieticKernel(
        policy=ecosystem.policy,
        templates=ecosystem.templates,
    )
    result = kernel.run_cycle(request)
    payload = {
        "schema_version": "aigc.autopoietic-cli-result.v1",
        "ecosystem_id": ecosystem.ecosystem_id,
        "fabric_registry_id": fabric.registry_id,
        "fabric_registry_sha256": fabric.digest,
        "state": result.state.model_dump(mode="json"),
        "receipt": result.receipt.model_dump(mode="json"),
        "deficits": [item.model_dump(mode="json") for item in result.deficits],
        "candidate": result.candidate.model_dump(mode="json") if result.candidate else None,
        "verification": (
            result.verification.model_dump(mode="json") if result.verification else None
        ),
        "shadow_telemetry": (
            result.shadow_telemetry.model_dump(mode="json")
            if result.shadow_telemetry
            else None
        ),
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    sys.stdout.write(encoded)
    return 0 if result.receipt.terminal_status.value in {"PASS", "AWAITING_OPERATOR"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
