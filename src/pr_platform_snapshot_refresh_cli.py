from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.core.pr_platform_snapshot_refresh import (
    DEFAULT_OUTPUT_ROOT,
    PlatformSnapshotRefreshError,
    build_refresh_bundle,
    write_refresh_bundle,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            'Validate an ephemeral AIGC PR platform snapshot, gate graph-drift '
            'evaluation behind snapshot completeness, and write one review bundle.'
        )
    )
    parser.add_argument('--project-root', default='.')
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--output-root', default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument(
        '--evaluated-at',
        help='Optional RFC3339 evaluation time. Defaults to the current UTC time.',
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = build_refresh_bundle(
            project_root=Path(args.project_root),
            snapshot_path=Path(args.snapshot),
            evaluated_at=args.evaluated_at,
        )
        output_directory = write_refresh_bundle(
            result,
            output_root=Path(args.output_root),
        )
    except (OSError, ValueError, PlatformSnapshotRefreshError) as exc:
        print(json.dumps({'status': 'ERROR', 'error': str(exc)}, sort_keys=True))
        return 2

    payload = {
        'status': result['bundle']['bundle_conclusion'],
        'bundle_id': result['bundle']['bundle_id'],
        'output_directory': str(output_directory),
        'operator_review_required': True,
        'automatic_mutation_allowed': False,
        'external_action_performed': False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    return 0 if result['bundle']['bundle_conclusion'] in {
        'CURRENT',
        'CURRENT_WITH_DECLARED_EXCLUSIONS',
    } else 1


if __name__ == '__main__':
    raise SystemExit(main())
