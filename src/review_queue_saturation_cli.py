from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.core.review_queue_saturation import evaluate_repository_saturation, write_receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Evaluate the AIGC review queue saturation policy without mutating repository or platform state.'
    )
    parser.add_argument('--project-root', default='.')
    parser.add_argument(
        '--output',
        default='reports/artifacts/review_queue_saturation/review_queue_saturation_receipt.json',
    )
    parser.add_argument('--evaluated-at', default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    receipt = evaluate_repository_saturation(
        Path(args.project_root),
        evaluated_at=args.evaluated_at,
    )
    write_receipt(receipt, Path(args.project_root) / args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
