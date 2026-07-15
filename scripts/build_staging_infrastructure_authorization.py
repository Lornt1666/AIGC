from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.staging_infrastructure_authorization import (  # noqa: E402
    APPLY_SCHEMA,
    DISCOVERY_SCHEMA,
    PLAN_SCHEMA,
    TERRAFORM_ROOT,
    canonical_digest,
    file_digest,
    load_json,
    parse_time,
    recursive_terraform_fingerprint,
    repository_revision,
    validate_plan_authorization,
    validate_schema,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def receipt_id(prefix: str, material: dict[str, object]) -> str:
    digest = canonical_digest(material)
    return f"{prefix}-{digest[:24].upper()}"


def common_parser(subparsers: argparse._SubParsersAction) -> None:
    for name in ("plan", "apply"):
        parser = subparsers.choices[name]
        parser.add_argument("--operator-name", required=True)
        parser.add_argument(
            "--decision",
            choices=("APPROVED", "DENIED"),
            required=True,
        )
        parser.add_argument(
            "--reason",
            action="append",
            default=[],
            help="Required for DENIED; prohibited for APPROVED.",
        )
        parser.add_argument("--output", required=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build contract-valid staging infrastructure authorization receipts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan")
    plan.add_argument("--discovery-evidence", required=True)
    plan.add_argument("--project-id", required=True)
    plan.add_argument("--monthly-budget-cad", type=float, default=50)
    plan.add_argument("--ttl-minutes", type=int, default=120)

    apply = subparsers.add_parser("apply")
    apply.add_argument("--plan-authorization", required=True)
    apply.add_argument("--saved-plan", required=True)
    apply.add_argument("--ttl-minutes", type=int, default=30)

    common_parser(subparsers)
    return parser.parse_args()


def reason_codes(args: argparse.Namespace) -> list[str]:
    reasons = [str(value).strip().upper().replace(" ", "_") for value in args.reason]
    reasons = [value for value in reasons if value]
    if args.decision == "APPROVED" and reasons:
        raise SystemExit("APPROVED receipts cannot include reason codes")
    if args.decision == "DENIED" and not reasons:
        raise SystemExit("DENIED receipts require at least one --reason")
    return reasons


def build_plan(args: argparse.Namespace) -> dict[str, object]:
    if args.ttl_minutes < 1 or args.ttl_minutes > 240:
        raise SystemExit("Plan authorization TTL must be between 1 and 240 minutes")
    if args.monthly_budget_cad <= 0 or args.monthly_budget_cad > 50:
        raise SystemExit("Staging monthly budget must be greater than 0 and at most CAD 50")

    discovery = validate_schema(
        DISCOVERY_SCHEMA,
        load_json(args.discovery_evidence),
    )
    revision = repository_revision(PROJECT_ROOT)
    fingerprint = recursive_terraform_fingerprint(TERRAFORM_ROOT)
    now = utc_now()
    reasons = reason_codes(args)
    approved = args.decision == "APPROVED"
    material = {
        "decision": args.decision,
        "revision": revision,
        "project_id": args.project_id,
        "terraform_fingerprint": fingerprint,
        "discovery_receipt_id": discovery["receipt_id"],
        "discovery_digest": canonical_digest(discovery),
        "issued_at": now.isoformat(),
    }
    receipt = {
        "contract_id": "AIGC-STAGING-INFRASTRUCTURE-PLAN-AUTHORIZATION-001",
        "contract_version": "1.0.0",
        "receipt_id": receipt_id("SIP", material),
        "decision": args.decision,
        "reason_codes": reasons,
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "approved_by_name": args.operator_name,
        "environment": "isolated_staging",
        "exact_revision": revision,
        "project_id": args.project_id,
        "terraform_root": "infra/terraform/gcp",
        "terraform_fingerprint": fingerprint,
        "component": "cloud_sql",
        "monthly_budget_cad": args.monthly_budget_cad,
        "provider_discovery_evidence_receipt_id": discovery["receipt_id"],
        "provider_discovery_evidence_digest": canonical_digest(discovery),
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=args.ttl_minutes)).isoformat(),
        "resource_creation_authorized": approved,
        "cloud_sql_enabled": approved,
        "terraform_plan_authorized": approved,
        "terraform_apply_authorized": False,
        "provider_mutation_authorized": False,
        "production_deployment_authorized": False,
        "production_data_allowed": False,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "external_action_performed": False,
    }
    receipt = validate_schema(PLAN_SCHEMA, receipt)
    if approved:
        evaluation = validate_plan_authorization(
            authorization=receipt,
            discovery_evidence=discovery,
            project_root=PROJECT_ROOT,
            terraform_root=TERRAFORM_ROOT,
            exact_revision=revision,
            evaluated_at=now,
        )
        if not evaluation.effective:
            raise SystemExit(
                "Approved plan authority is ineffective: "
                + ",".join(evaluation.reason_codes)
            )
    return receipt


def build_apply(args: argparse.Namespace) -> dict[str, object]:
    if args.ttl_minutes < 1 or args.ttl_minutes > 60:
        raise SystemExit("Apply authorization TTL must be between 1 and 60 minutes")
    plan_authorization = validate_schema(
        PLAN_SCHEMA,
        load_json(args.plan_authorization),
    )
    plan_path = Path(args.saved_plan).resolve()
    if not plan_path.is_file():
        raise SystemExit(f"Saved plan does not exist: {plan_path}")

    revision = repository_revision(PROJECT_ROOT)
    fingerprint = recursive_terraform_fingerprint(TERRAFORM_ROOT)
    now = utc_now()
    reasons = reason_codes(args)
    approved = args.decision == "APPROVED"
    if approved:
        plan_reasons: list[str] = []
        if plan_authorization["decision"] != "APPROVED":
            plan_reasons.append("PLAN_AUTHORIZATION_DENIED")
        if plan_authorization["exact_revision"] != revision:
            plan_reasons.append("PLAN_AUTHORIZATION_REVISION_MISMATCH")
        if plan_authorization["terraform_fingerprint"] != fingerprint:
            plan_reasons.append("PLAN_AUTHORIZATION_TERRAFORM_DRIFT")
        if now >= parse_time(plan_authorization["expires_at"]):
            plan_reasons.append("PLAN_AUTHORIZATION_EXPIRED")
        if plan_reasons:
            raise SystemExit(
                "Apply authority cannot be approved: " + ",".join(plan_reasons)
            )

    saved_plan_digest = file_digest(plan_path)
    material = {
        "decision": args.decision,
        "revision": revision,
        "project_id": plan_authorization["project_id"],
        "terraform_fingerprint": fingerprint,
        "plan_authorization_digest": canonical_digest(plan_authorization),
        "saved_plan_digest": saved_plan_digest,
        "issued_at": now.isoformat(),
    }
    receipt = {
        "contract_id": "AIGC-STAGING-INFRASTRUCTURE-APPLY-AUTHORIZATION-001",
        "contract_version": "1.0.0",
        "receipt_id": receipt_id("SIA", material),
        "decision": args.decision,
        "reason_codes": reasons,
        "approved_by_role": "ACCOUNTABLE_OPERATOR",
        "approved_by_name": args.operator_name,
        "environment": "isolated_staging",
        "exact_revision": revision,
        "project_id": plan_authorization["project_id"],
        "terraform_root": "infra/terraform/gcp",
        "terraform_fingerprint": fingerprint,
        "component": "cloud_sql",
        "plan_authorization_receipt_id": plan_authorization["receipt_id"],
        "plan_authorization_digest": canonical_digest(plan_authorization),
        "saved_plan_digest": saved_plan_digest,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=args.ttl_minutes)).isoformat(),
        "single_use": True,
        "provider_mutation_authorized": approved,
        "terraform_apply_authorized": approved,
        "production_deployment_authorized": False,
        "production_data_allowed": False,
        "operator_review_required": True,
        "automatic_apply_allowed": False,
        "terraform_apply_performed": False,
        "external_action_performed": False,
    }
    return validate_schema(APPLY_SCHEMA, receipt)


def main() -> int:
    args = parse_args()
    receipt = build_plan(args) if args.command == "plan" else build_apply(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"receipt": str(output), **receipt}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
