from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.core.pr_platform_snapshot_request import (
    REQUEST_PATH,
    evaluate_repository_snapshot_request,
    write_receipt,
)
from src.core.pr_dependency_graph_drift import SNAPSHOT_PATH


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Validate a read-only GitHub platform snapshot against the governed AIGC snapshot request packet.'
    )
    parser.add_argument('--project-root', default='.')
    parser.add_argument('--request', default=str(REQUEST_PATH))
    parser.add_argument('--snapshot', default=str(SNAPSHOT_PATH))
    parser.add_argument('--evaluated-at')
    parser.add_argument(
        '--output',
        default='reports/artifacts/pr_platform_snapshot_request/pr_platform_snapshot_request_receipt.json',
    )
    args = parser.parse_args()

    receipt = evaluate_repository_snapshot_request(
        Path(args.project_root),
        request_path=args.request,
        snapshot_path=args.snapshot,
        evaluated_at=args.evaluated_at,
    )
    write_receipt(receipt, args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt['conclusion'] == 'COMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
