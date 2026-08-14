from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.regenexcalibur.orchestrator import seed_regenexcalibur_universe


def validate() -> dict[str, object]:
    seed = json.loads(
        (ROOT / "config" / "regenexcalibur_universe_seed.v1.json").read_text(
            encoding="utf-8"
        )
    )
    schema = json.loads(
        (ROOT / "schemas" / "regenexcalibur_universe_seed.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(seed)
    return seed_regenexcalibur_universe(seed=seed, requested_evolution_depth=1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RegenExcalibur Genesis")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = validate()
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
