"""Bounded read-only CLI for Ω Mission OS projections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.mission_os.projection import compose_projection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a validated Ω Mission OS read-only projection.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mission", type=Path, default=Path("config/mission.example.json"))
    parser.add_argument("--database", type=Path, default=None)
    args = parser.parse_args(argv)

    snapshot = compose_projection(args.root, args.mission, args.database)
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
