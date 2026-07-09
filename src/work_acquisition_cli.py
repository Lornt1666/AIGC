from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.work_acquisition import run_work_acquisition  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_work_acquisition(
        project_root=args.root.resolve(),
        registry_path=args.registry,
        profile_path=args.profile,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare AIGC work acquisition and performance packets without external commitments.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--registry", type=Path, default=PROJECT_ROOT / "config" / "work_domain_registry.json")
    parser.add_argument("--profile", type=Path, default=PROJECT_ROOT / "config" / "work_acquisition_profile.json")
    parser.add_argument("--artifact-root", type=Path, default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
