from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.ci_dependency_review_receipt import (  # noqa: E402
    build_dependency_review_receipt,
    write_receipt,
)


DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "reports"
    / "artifacts"
    / "ci_dependency_review"
    / "ci_dependency_review_receipt.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect every AIGC workflow against the reviewed CI dependency manifest "
            "and emit a revision-bound review receipt."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--source-revision",
        default=None,
        help="Optional full commit SHA. Defaults to the checked-out Git HEAD.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    output_path = args.output
    if not output_path.is_absolute():
        output_path = project_root / output_path

    receipt = build_dependency_review_receipt(
        project_root,
        source_revision=args.source_revision,
    )
    write_receipt(project_root, receipt, output_path)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["validation_conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
