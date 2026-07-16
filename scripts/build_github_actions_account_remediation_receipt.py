from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.github_actions_account_remediation import (  # noqa: E402
    build_account_remediation_receipt,
    exact_git_revision,
    git_branch,
    git_is_ancestor,
    parse_time,
)


RESTRICTION_CATEGORIES = (
    "ACTIONS_MINUTES",
    "SPENDING_LIMIT",
    "BILLING_PAYMENT",
    "ACTIONS_POLICY",
    "RUNNER_POLICY",
    "OTHER",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a contract-valid, exact-target GitHub Actions account-remediation "
            "receipt. Do not include card numbers, security codes, bank details, or secrets."
        )
    )
    parser.add_argument("--operator-name", required=True)
    parser.add_argument("--observed-banner", required=True)
    parser.add_argument(
        "--restriction-category",
        choices=RESTRICTION_CATEGORIES,
        required=True,
    )
    parser.add_argument("--remediation-summary", required=True)
    parser.add_argument("--billing-ui-evidence-reference", required=True)
    parser.add_argument(
        "--remediation-completed-at",
        required=True,
        help="ISO-8601 date-time with timezone, for example 2026-07-16T01:00:00-06:00.",
    )
    parser.add_argument(
        "--exact-head",
        required=True,
        help=(
            "Exact PR #123 target head. It must be an ancestor of the current "
            "remediation-tooling checkout."
        ),
    )
    parser.add_argument(
        "--hosted-rerun-id",
        type=int,
        default=None,
        help="Optional GitHub Actions run ID requested after remediation.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/governance/github-actions-account-remediation.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tooling_revision = exact_git_revision(PROJECT_ROOT)
    tooling_branch = git_branch(PROJECT_ROOT)
    exact_head = args.exact_head.strip()
    target_is_ancestor = git_is_ancestor(
        exact_head,
        tooling_revision,
        project_root=PROJECT_ROOT,
    )
    if not target_is_ancestor:
        raise SystemExit(
            "The requested PR #123 target head is not an ancestor of the current "
            "remediation-tooling checkout. Use the approved stacked tooling branch."
        )

    completed_at: datetime = parse_time(args.remediation_completed_at)
    receipt = build_account_remediation_receipt(
        exact_head=exact_head,
        tooling_revision=tooling_revision,
        tooling_branch=tooling_branch,
        target_is_ancestor_of_tooling_revision=target_is_ancestor,
        operator_name=args.operator_name,
        observed_banner=args.observed_banner,
        restriction_category=args.restriction_category,
        remediation_summary=args.remediation_summary,
        billing_ui_evidence_reference=args.billing_ui_evidence_reference,
        remediation_completed_at=completed_at,
        hosted_rerun_id=args.hosted_rerun_id,
    )

    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "receipt_path": str(output),
                "receipt_id": receipt["receipt_id"],
                "exact_head": receipt["exact_head"],
                "tooling_revision": receipt["tooling_revision"],
                "tooling_branch": receipt["tooling_branch"],
                "target_is_ancestor_of_tooling_revision": True,
                "hosted_rerun_requested": receipt["hosted_rerun_requested"],
                "hosted_rerun_id": receipt["hosted_rerun_id"],
                "merge_authorized": False,
                "terraform_apply_authorized": False,
                "external_action_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
