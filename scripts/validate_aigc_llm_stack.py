from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_stack.orchestrator import plan_llm_lifecycle


def validate() -> dict[str, object]:
    config = json.loads(
        (ROOT / "config" / "aigc_llm_stack.v1.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (ROOT / "schemas" / "aigc_llm_stack.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(config)
    for relative_path in config["data"]["paths"]:
        path = ROOT / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"declared data fixture does not exist: {path}")
        if path.stat().st_size > config["resources"]["maximum_dataset_bytes"]:
            raise ValueError("declared data exceeds maximum_dataset_bytes")
    return plan_llm_lifecycle(config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the governed AIGC LLM stack")
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
