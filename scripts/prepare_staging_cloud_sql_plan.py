from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.staging_infrastructure_authorization import (  # noqa: E402
    TERRAFORM_ROOT,
    load_json,
    validate_plan_authorization,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate an exact-revision Cloud SQL staging plan authorization "
            "and write ephemeral Terraform activation variables."
        )
    )
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--discovery-evidence", required=True)
    parser.add_argument(
        "--output-dir",
        default="artifacts/staging/cloud-sql-plan",
    )
    parser.add_argument(
        "--terraform-root",
        default=str(TERRAFORM_ROOT),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    authorization_path = Path(args.authorization).resolve()
    discovery_path = Path(args.discovery_evidence).resolve()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    authorization = load_json(authorization_path)
    discovery = load_json(discovery_path)
    evaluation = validate_plan_authorization(
        authorization=authorization,
        discovery_evidence=discovery,
        project_root=PROJECT_ROOT,
        terraform_root=Path(args.terraform_root),
    )

    evaluation_path = output_dir / "plan-authorization-evaluation.json"
    evaluation_path.write_text(
        json.dumps(evaluation.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not evaluation.effective:
        print(json.dumps(evaluation.to_dict(), indent=2))
        return 2

    tfvars = {
        "environment": "staging",
        "project_id": evaluation.project_id,
        "primary_region": "northamerica-northeast2",
        "recovery_region": "northamerica-northeast1",
        "exact_revision": evaluation.exact_revision,
        "release_gate_receipt_id": "",
        "release_gate_result": "DENY",
        "deployment_authorized": False,
        "resource_creation_authorized": True,
        "staging_plan_authorization_path": str(authorization_path),
        "staging_terraform_fingerprint": evaluation.terraform_fingerprint,
        "cloud_sql_enabled": True,
        "monthly_budget_cad": authorization["monthly_budget_cad"],
    }
    tfvars_path = output_dir / "activation.auto.tfvars.json"
    tfvars_path.write_text(
        json.dumps(tfvars, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        **evaluation.to_dict(),
        "activation_tfvars": str(tfvars_path),
        "authorization_receipt_id": authorization["receipt_id"],
        "provider_discovery_evidence_receipt_id": discovery["receipt_id"],
        "next_step": "TERRAFORM_INIT_VALIDATE_AND_SAVED_PLAN",
        "terraform_apply_authorized": False,
        "external_action_performed": False,
    }
    summary_path = output_dir / "plan-preparation-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
