from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ci_revision_evidence import (  # noqa: E402
    CIRevisionEvidenceError,
    build_receipt,
    read_git_head,
    write_receipt,
)


DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "artifacts" / "ci_revision_evidence" / "ci_revision_evidence_receipt.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify that CI checked out the exact expected AIGC revision.")
    parser.add_argument(
        "--expected",
        default=os.environ.get("AIGC_EXPECTED_REVISION", ""),
        help="Expected full commit SHA. Defaults to AIGC_EXPECTED_REVISION.",
    )
    parser.add_argument(
        "--event",
        default=os.environ.get("GITHUB_EVENT_NAME", "unknown"),
        help="CI event name used for the evidence receipt.",
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    expected = str(args.expected).strip()
    if not expected:
        raise CIRevisionEvidenceError("AIGC_EXPECTED_REVISION or --expected is required.")

    actual = read_git_head(args.project_root.resolve())
    receipt = build_receipt(expected, actual, str(args.event))
    write_receipt(receipt, args.output)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
