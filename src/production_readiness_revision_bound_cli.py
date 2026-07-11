from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ci_revision_evidence import normalize_revision, verify_ci_revision  # noqa: E402
from src.core.production_readiness_ledger import run_production_readiness_ledger  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an AIGC production-readiness receipt bound to an exact checked-out revision."
    )
    parser.add_argument(
        "--expected",
        default=os.environ.get("AIGC_EXPECTED_REVISION", ""),
        help="Expected full commit SHA. Defaults to AIGC_EXPECTED_REVISION.",
    )
    parser.add_argument(
        "--event",
        default=os.environ.get("GITHUB_EVENT_NAME", "unknown"),
        help="CI event name used during revision verification.",
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--ledger", type=Path, default=None)
    parser.add_argument("--artifact-root", type=Path, default=None)
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> dict[str, object]:
    args = parse_args(argv)
    expected = normalize_revision(str(args.expected), "expected_revision")
    root = args.project_root.resolve()
    verify_ci_revision(root, expected, str(args.event))

    # The existing readiness engine reads GITHUB_SHA when it creates its receipt.
    # Bind that process-local value only after the checked-out revision is proven.
    previous_sha = os.environ.get("GITHUB_SHA")
    os.environ["GITHUB_SHA"] = expected
    try:
        result = run_production_readiness_ledger(
            root,
            ledger_path=args.ledger,
            artifact_root=args.artifact_root,
        )
    finally:
        if previous_sha is None:
            os.environ.pop("GITHUB_SHA", None)
        else:
            os.environ["GITHUB_SHA"] = previous_sha

    report = result["report"]
    if report["source_revision"] != expected:
        raise RuntimeError("Production-readiness receipt was not bound to the verified exact revision.")
    return result


def main(argv: list[str] | None = None) -> int:
    result = run(argv)
    print(json.dumps(result["report"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
