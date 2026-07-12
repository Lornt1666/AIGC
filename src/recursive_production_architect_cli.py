from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.recursive_production_architect import run_recursive_production_architect


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the bounded AIGC evolution snapshot architect.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_recursive_production_architect(
        project_root=args.root,
        policy_path=args.policy,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
