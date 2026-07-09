from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.approval_gated_external_actions import build_review_popup_packet, load_policy, run_policy_smoke  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    policy_path = args.policy or root / "config" / "approval_gated_external_actions.json"
    if args.command == "smoke":
        payload = run_policy_smoke(root, policy_path)
    else:
        policy = load_policy(policy_path)
        requested = {
            "action": args.action,
            "destination": args.destination,
            "payload": json.loads(args.payload_json),
            "risk_class": args.risk_class,
            "platform_terms_status": args.platform_terms_status,
            "cost_or_terms": json.loads(args.cost_or_terms_json),
            "rollback_or_correction_plan": args.rollback_or_correction_plan,
        }
        payload = build_review_popup_packet(policy, requested)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AIGC approval-gated external action popup packets without executing actions.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--policy", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("smoke", help="Validate policy and generate safe/blocked example popup packets.")
    build = subparsers.add_parser("build-popup", help="Build one review popup packet for an external action request.")
    build.add_argument("--action", required=True)
    build.add_argument("--destination", default="")
    build.add_argument("--payload-json", default="{}")
    build.add_argument("--risk-class", default="high")
    build.add_argument("--platform-terms-status", default="not_reviewed")
    build.add_argument("--cost-or-terms-json", default="{}")
    build.add_argument("--rollback-or-correction-plan", default="operator must define before proceeding")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
