from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.program_health import run_program_health, write_health_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    report = run_program_health(root)
    if args.write:
        path = write_health_report(root)
        print(f"Health report written: {path}")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.overall_status in {"healthy", "warning"} else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AIGC local program health checks.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--write", action="store_true", help="Write reports/artifacts/program_health/latest_program_health.json")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
