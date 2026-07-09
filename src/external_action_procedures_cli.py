from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.external_action_procedures import run_external_action_procedure  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = json.loads(args.payload_json)
    if not isinstance(payload, dict):
        raise ValueError("--payload-json must decode to a JSON object")
    cost_or_terms = json.loads(args.cost_or_terms_json)
    if not isinstance(cost_or_terms, dict):
        raise ValueError("--cost-or-terms-json must decode to a JSON object")
    result = run_external_action_procedure(
        project_root=args.root.resolve(),
        action=args.action,
        destination=args.destination,
        payload=payload,
        risk_class=args.risk_class,
        platform_terms_status=args.platform_terms_status,
        cost_or_terms=cost_or_terms,
        rollback_or_correction_plan=args.rollback_or_correction_plan,
        policy_path=args.policy,
        controls_path=args.controls,
        artifact_root=args.artifact_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build professional AIGC external-action procedure packets without executing external actions.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--policy", type=Path, default=PROJECT_ROOT / "config" / "approval_gated_external_actions.json")
    parser.add_argument("--controls", type=Path, default=PROJECT_ROOT / "config" / "external_action_procedure_controls.json")
    parser.add_argument("--artifact-root", type=Path, default=None)
    parser.add_argument("--action", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--payload-json", default="{}")
    parser.add_argument("--risk-class", default="high")
    parser.add_argument("--platform-terms-status", default="review_required")
    parser.add_argument("--cost-or-terms-json", default="{}")
    parser.add_argument("--rollback-or-correction-plan", default="operator must define before proceeding")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
