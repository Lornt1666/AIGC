from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.provider_discovery_automation import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_FIXTURE_PATH,
    DEFAULT_TEMPLATE_PATH,
    load_catalog,
    load_fixture,
    load_template,
    run_mock_discovery,
    write_mock_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the AIGC provider-discovery kit in mock-only mode."
    )
    parser.add_argument(
        "--repository-revision",
        required=True,
        help="Exact 40-character repository revision to bind to the simulation.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/provider_discovery_simulation",
        help="Output directory for generated offline artifacts.",
    )
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG_PATH),
        help="Command catalog path.",
    )
    parser.add_argument(
        "--fixture",
        default=str(DEFAULT_FIXTURE_PATH),
        help="Synthetic fixture path.",
    )
    parser.add_argument(
        "--template",
        default=str(DEFAULT_TEMPLATE_PATH),
        help="Staging procurement template path.",
    )
    parser.add_argument(
        "--created-at",
        default=None,
        help="Optional RFC3339 timestamp for deterministic replay.",
    )
    parser.add_argument(
        "--rollback-reference",
        default="branch:codex/provider-discovery-automation-kit-v1",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    created_at = (
        datetime.fromisoformat(args.created_at.replace("Z", "+00:00"))
        if args.created_at
        else datetime.now(timezone.utc)
    )
    report = run_mock_discovery(
        catalog=load_catalog(args.catalog),
        fixture=load_fixture(args.fixture),
        template=load_template(args.template),
        repository_revision=args.repository_revision,
        created_at=created_at,
        rollback_reference=args.rollback_reference,
    )
    paths = write_mock_outputs(Path(args.output_dir), report)
    print(
        json.dumps(
            {
                "mode": report["execution_mode"],
                "result": report["result"],
                "no_network": report["no_network"],
                "provider_action_performed": report["provider_action_performed"],
                "external_action_performed": report["external_action_performed"],
                "outputs": [str(path) for path in paths],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
