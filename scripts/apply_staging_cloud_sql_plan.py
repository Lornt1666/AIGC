from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.staging_infrastructure_authorization import (  # noqa: E402
    TERRAFORM_ROOT,
    file_digest,
    load_json,
    validate_apply_authorization,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a single-use staging apply authorization against one "
            "exact saved Terraform plan."
        )
    )
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--plan-authorization", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument(
        "--terraform-root",
        default=str(TERRAFORM_ROOT),
    )
    parser.add_argument(
        "--receipt-output",
        default="artifacts/staging/cloud-sql-apply/apply-execution-receipt.json",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Invoke terraform apply after successful validation.",
    )
    return parser.parse_args()


def write_receipt(
    path: Path,
    *,
    authorization: dict[str, object],
    plan_path: Path,
    result: str,
    exit_code: int | None,
    external_action_performed: bool,
) -> None:
    material = "|".join(
        (
            str(authorization["receipt_id"]),
            file_digest(plan_path),
            result,
            str(exit_code),
        )
    )
    receipt = {
        "contract_id": "AIGC-STAGING-INFRASTRUCTURE-APPLY-EXECUTION-001",
        "contract_version": "1.0.0",
        "receipt_id": "SAE-" + sha256(material.encode("utf-8")).hexdigest()[:24].upper(),
        "apply_authorization_receipt_id": authorization["receipt_id"],
        "exact_revision": authorization["exact_revision"],
        "project_id": authorization["project_id"],
        "component": "cloud_sql",
        "saved_plan_digest": file_digest(plan_path),
        "result": result,
        "terraform_exit_code": exit_code,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "operator_review_required": True,
        "post_apply_evidence_required": True,
        "external_action_performed": external_action_performed,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    authorization = load_json(args.authorization)
    plan_authorization = load_json(args.plan_authorization)
    plan_path = Path(args.plan).resolve()
    if not plan_path.is_file():
        raise SystemExit(f"Saved Terraform plan does not exist: {plan_path}")

    evaluation = validate_apply_authorization(
        authorization=authorization,
        plan_authorization=plan_authorization,
        saved_plan_path=plan_path,
        project_root=PROJECT_ROOT,
        terraform_root=Path(args.terraform_root),
    )
    print(json.dumps(evaluation.to_dict(), indent=2))
    if not evaluation.effective:
        return 2

    receipt_path = Path(args.receipt_output)
    if not args.execute:
        write_receipt(
            receipt_path,
            authorization=authorization,
            plan_path=plan_path,
            result="VALIDATED_NOT_EXECUTED",
            exit_code=None,
            external_action_performed=False,
        )
        print(
            "Apply authorization is effective. No provider action occurred; "
            "rerun with --execute only after accountable review."
        )
        return 0

    terraform = shutil.which("terraform")
    if terraform is None:
        raise SystemExit("terraform is required for --execute")

    completed = subprocess.run(
        [terraform, "apply", "-input=false", "-auto-approve", str(plan_path)],
        cwd=Path(args.terraform_root),
        check=False,
    )
    result = "APPLIED" if completed.returncode == 0 else "FAILED"
    write_receipt(
        receipt_path,
        authorization=authorization,
        plan_path=plan_path,
        result=result,
        exit_code=completed.returncode,
        external_action_performed=True,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
