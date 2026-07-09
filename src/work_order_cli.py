from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.work_order import run_cockpit_smoke, run_governance_smoke, run_work_order  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    if args.command == "work-order":
        result = run_work_order(root, args.input, args.artifact_root)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "governance-smoke":
        result = run_governance_smoke(root)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "cockpit-smoke":
        print(json.dumps(run_cockpit_smoke(root), ensure_ascii=False, indent=2))
        return 0
    raise ValueError(f"Unhandled command: {args.command}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC governed work-order dry-run CLI.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    work_order = subparsers.add_parser("work-order", help="Run a governed work-order dry run.")
    work_order.add_argument("--input", type=Path, default=PROJECT_ROOT / "config" / "example_work_order.json")
    work_order.add_argument("--artifact-root", type=Path, default=None)

    subparsers.add_parser("governance-smoke", help="Run the example work-order governance smoke test.")
    subparsers.add_parser("cockpit-smoke", help="Run a cockpit-safe work-order smoke test without Streamlit side effects.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
