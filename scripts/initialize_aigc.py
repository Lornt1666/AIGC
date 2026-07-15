from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.operator_initialization import run_operator_initialization  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AIGC's safe, local one-click initialization sequence."
    )
    parser.add_argument("--continue-on-failure", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = run_operator_initialization(
            PROJECT_ROOT,
            stop_on_failure=not args.continue_on_failure,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "INITIALIZATION_BLOCKED",
                    "error": str(exc),
                    "operator_review_required": True,
                    "external_action_performed": False,
                },
                indent=2,
            )
        )
        return 1

    print(json.dumps(receipt.to_dict(), indent=2))
    return 0 if receipt.status == "READY_FOR_OPERATOR_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
