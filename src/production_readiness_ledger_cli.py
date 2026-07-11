from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.production_readiness_ledger import run_production_readiness_ledger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate AIGC capability completion and production readiness using repository evidence."
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_production_readiness_ledger(
        args.root,
        ledger_path=args.ledger,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
