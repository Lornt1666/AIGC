"""CLI wrapper for RX-148 closure evaluation; reads a JSON snapshot and writes JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aigc_runtime.closure_workflow import evaluate_closure


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate AIGC RX-148 release evidence closure (no side effects).")
    parser.add_argument("snapshot", help="Path to a JSON evidence snapshot acquired from trusted sources.")
    parser.add_argument("--output", help="Optional path for the machine-readable result; defaults to stdout.")
    args = parser.parse_args()
    try:
        raw = Path(args.snapshot).read_text(encoding="utf-8")
        snapshot = json.loads(raw)
        result = evaluate_closure(snapshot)
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"disposition": "BLOCK", "error": str(exc), "side_effects_performed": False}, sort_keys=True), file=sys.stderr)
        return 2
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0 if result["disposition"] == "RX19_APPROVED_EVIDENCE_ONLY_NO_ACTION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
