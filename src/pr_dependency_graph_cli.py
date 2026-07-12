from __future__ import annotations

import argparse
from pathlib import Path

from src.core.pr_dependency_graph import evaluate_graph, load_graph, write_receipt


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate the AIGC PR dependency graph and emit a read-only status receipt.')
    parser.add_argument('--project-root', default='.')
    parser.add_argument('--graph', default='governance/evolution/pr_dependency_graph_v1.json')
    parser.add_argument('--output', default='reports/artifacts/pr_dependency_graph/pr_dependency_status_receipt.json')
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    receipt = evaluate_graph(load_graph(root, args.graph))
    write_receipt(receipt, root / args.output)
    print(f"{receipt['conclusion']}: {receipt['node_count']} nodes, {len(receipt['blocked_nodes'])} blocked, {len(receipt['stale_base_nodes'])} stale-base")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
