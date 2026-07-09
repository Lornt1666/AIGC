from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.counterparty_request_intake import run_counterparty_request_intake  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_counterparty_request_intake(
        project_root=args.root.resolve(),
        request_path=args.request,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a counterparty request and acceptance review packet before approving external work actions.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--request", type=Path, default=PROJECT_ROOT / "config" / "counterparty_request_example.json")
    parser.add_argument("--artifact-root", type=Path, default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
