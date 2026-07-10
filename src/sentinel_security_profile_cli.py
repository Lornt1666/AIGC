from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.sentinel_security_profile import run_sentinel_security_profile  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_sentinel_security_profile(
        project_root=args.root.resolve(),
        profile_path=args.profile,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the AIGC Sentinel security profile report.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--profile", type=Path, default=PROJECT_ROOT / "config" / "sentinel_security_profile.json")
    parser.add_argument("--artifact-root", type=Path, default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
