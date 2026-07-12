from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.core.pr_dependency_graph_drift import evaluate_repository_drift, write_receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Compare the committed AIGC PR dependency graph with a read-only platform snapshot.'
    )
    parser.add_argument('--project-root', default='.')
    parser.add_argument(
        '--snapshot',
        default='governance/evolution/pr_platform_snapshot_2026_07_12T142738Z.json',
    )
    parser.add_argument(
        '--output',
        default='reports/artifacts/pr_dependency_graph_drift/pr_dependency_graph_drift_receipt.json',
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.project_root)
    receipt = evaluate_repository_drift(root, args.snapshot)
    write_receipt(receipt, root / args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 1 if receipt['conclusion'] == 'DRIFT_DETECTED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
