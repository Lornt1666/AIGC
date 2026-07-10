from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.security_privacy_wiring import run_security_privacy_wiring  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_security_privacy_wiring(
        project_root=args.root.resolve(),
        request_path=args.request,
        policy_path=args.policy,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AIGC Security & Privacy Wiring Gate.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--request", type=Path, default=PROJECT_ROOT / "config" / "counterparty_request_example.json")
    parser.add_argument("--policy", type=Path, default=PROJECT_ROOT / "config" / "security_privacy_wiring_policy.json")
    parser.add_argument("--artifact-root", type=Path, default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
