from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.communication_observer_access import run_observer_access_packet  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_observer_access_packet(
        project_root=args.root.resolve(),
        policy_path=args.policy,
        counterparty_path=args.counterparty_request,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a read-only employer/counterparty observer access packet.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--policy", type=Path, default=PROJECT_ROOT / "config" / "communication_observer_access.json")
    parser.add_argument("--counterparty-request", type=Path, default=PROJECT_ROOT / "config" / "counterparty_request_example.json")
    parser.add_argument("--artifact-root", type=Path, default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
