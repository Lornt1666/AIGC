from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.chatlog_scoped_observer_access import run_chatlog_observer_packet  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_chatlog_observer_packet(
        project_root=args.root.resolve(),
        policy_path=args.policy,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a scoped, redacted chat-log observer packet without sharing backend access.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--policy", type=Path, default=PROJECT_ROOT / "config" / "chatlog_scoped_observer_access.json")
    parser.add_argument("--artifact-root", type=Path, default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
