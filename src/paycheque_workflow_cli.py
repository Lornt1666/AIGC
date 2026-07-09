from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.paycheque_workflow import run_paycheque_workflow  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_paycheque_workflow(
        project_root=args.root.resolve(),
        config_path=args.input,
        artifact_root=args.artifact_root,
        trigger=args.trigger,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the governed AIGC paycheque pipeline without external commits.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "config" / "paycheque_workflow.json")
    parser.add_argument("--artifact-root", type=Path, default=None)
    parser.add_argument("--trigger", default="GenerateDailyPipeline")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
