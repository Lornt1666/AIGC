from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ci_merge_candidate_evidence import (  # noqa: E402
    CIMergeCandidateEvidenceError,
    build_receipt,
    git_is_ancestor,
    write_receipt,
)
from src.core.ci_revision_evidence import read_git_head  # noqa: E402


DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "reports"
    / "artifacts"
    / "ci_merge_candidate_evidence"
    / "ci_merge_candidate_evidence_receipt.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the checked-out GitHub pull-request merge candidate."
    )
    parser.add_argument(
        "--base",
        default=os.environ.get("AIGC_BASE_REVISION", ""),
        help="Pull-request base commit SHA.",
    )
    parser.add_argument(
        "--head",
        default=os.environ.get("AIGC_HEAD_REVISION", ""),
        help="Immutable pull-request head commit SHA.",
    )
    parser.add_argument(
        "--expected-merge",
        default=os.environ.get("AIGC_EXPECTED_MERGE_REVISION", ""),
        help="Expected GitHub merge-candidate SHA.",
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not str(args.base).strip() or not str(args.head).strip() or not str(args.expected_merge).strip():
        raise CIMergeCandidateEvidenceError(
            "Base, head and expected merge revisions are required."
        )

    root = args.project_root.resolve()
    actual = read_git_head(root)
    receipt = build_receipt(
        str(args.base),
        str(args.head),
        str(args.expected_merge),
        actual,
        base_is_ancestor=git_is_ancestor(root, str(args.base), actual),
        head_is_ancestor=git_is_ancestor(root, str(args.head), actual),
    )
    write_receipt(receipt, args.output)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
