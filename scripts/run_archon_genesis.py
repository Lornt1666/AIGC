#!/usr/bin/env python3
"""Run ARCHON-GENESIS in deterministic design-time mode and emit proposal artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archon_genesis import compile_architecture, render_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", default="config/archon_genesis_aigc_brief.json")
    parser.add_argument("--output-dir", default="reports/archon_genesis")
    args = parser.parse_args()
    brief_path = (ROOT / args.brief).resolve()
    output_dir = (ROOT / args.output_dir).resolve()
    if ROOT not in brief_path.parents or ROOT not in output_dir.parents:
        parser.error("brief and output directory must remain inside the repository")
    if not brief_path.is_file():
        parser.error(f"brief does not exist: {brief_path}")
    try:
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        compiled = compile_architecture(brief)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ARCHON-GENESIS compilation blocked: {exc}", file=sys.stderr)
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "ARCHON_GENESIS_PROPOSAL.json").write_text(
        json.dumps(compiled, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "ARCHON_GENESIS_PROPOSAL.md").write_text(
        render_report(compiled), encoding="utf-8"
    )
    print(json.dumps({
        "status": compiled["architecture_status"],
        "agent_count": compiled["agent_count"],
        "source_brief_digest": compiled["source_brief_digest"],
        "output_digest": compiled["output_digest"],
        "output_dir": str(output_dir),
        "execution_performed": False,
        "release_decision": "BLOCK",
    }, sort_keys=True))
    return 0 if compiled["architecture_status"] != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
