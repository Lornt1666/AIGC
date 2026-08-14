from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Sequence

import yaml

from scripts.aigc_external_release_procurement import ExternalReleaseContract, ProcurementError
from src.operations.nexus_provider_canary import ProviderCanaryPlan, build_invocation
from src.domain.nexus.contracts import ExecutionPermit, GovernanceDecision


REGION = "northamerica-northeast1"
IMMUTABLE_IMAGE = re.compile(r"^[a-z0-9.-]+-docker\.pkg\.dev/.+@sha256:[a-f0-9]{64}$")
MARKER = "AIGC_CANARY_RECEIPT:"


class CanaryLaunchError(RuntimeError):
    pass


class CanaryLaunchIndeterminate(CanaryLaunchError):
    pass


def _run(command: Sequence[str], *, mutating: bool = False) -> str:
    completed = subprocess.run(
        list(command), capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        error = CanaryLaunchIndeterminate if mutating else CanaryLaunchError
        raise error(f"command failed: {' '.join(command[:4])}")
    return completed.stdout.strip()


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanaryLaunchError(f"{path} must contain a JSON object")
    return value


def _validate_authority(
    procurement: ExternalReleaseContract,
    plan: ProviderCanaryPlan,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
) -> None:
    flag = (
        "gemini_canary_authorized"
        if plan.provider_id == "google_vertex_gemini"
        else "openai_canary_authorized"
    )
    if procurement.authority.get(flag) is not True:
        raise CanaryLaunchError(f"{flag} is not authorized")
    spend = Decimal(str(procurement.payload.get("provider_canary_spend_cad", 0)))
    if spend <= 0 or plan.maximum_cost_cad > spend:
        raise CanaryLaunchError("provider canary cost exceeds the procurement spend ceiling")
    invocation = build_invocation(plan, permit_id=permit.permit_id)
    if permit.request_digest != invocation.request_digest:
        raise CanaryLaunchError("permit request digest does not match the canary plan")
    if permit.maximum_invocations != 1:
        raise CanaryLaunchError("canary permit must be one-use")
    if decision.decision != "approved" or decision.decision_id != permit.governance_decision_id:
        raise CanaryLaunchError("canonical governance/permit binding is not approved")


def _receipt_from_logs(*, project: str, job_name: str) -> dict[str, Any]:
    filter_expr = (
        'resource.type="cloud_run_job" '
        f'AND resource.labels.job_name="{job_name}" '
        f'AND textPayload:"{MARKER}"'
    )
    entries = json.loads(
        _run(
            [
                "gcloud", "logging", "read", filter_expr,
                "--project", project,
                "--freshness", "15m",
                "--limit", "20",
                "--order", "desc",
                "--format", "json",
            ]
        )
        or "[]"
    )
    if not isinstance(entries, list):
        raise CanaryLaunchError("Cloud Logging returned invalid canary evidence")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("textPayload") or "")
        index = text.find(MARKER)
        if index < 0:
            continue
        candidate = text[index + len(MARKER):].strip()
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise CanaryLaunchError("canonical canary receipt marker was not found in Cloud Logging")


def launch(
    *,
    procurement: ExternalReleaseContract,
    deployment: dict[str, Any],
    plan: ProviderCanaryPlan,
    decision: GovernanceDecision,
    permit: ExecutionPermit,
    output: Path,
) -> dict[str, Any]:
    _validate_authority(procurement, plan, decision, permit)
    project = procurement.project_id
    if deployment.get("project_id") != project or deployment.get("region") != REGION:
        raise CanaryLaunchError("deployment receipt project/region mismatch")
    if deployment.get("release_sha") != plan.exact_revision:
        raise CanaryLaunchError("deployment receipt release SHA does not match canary plan")
    immutable_image = str(deployment.get("immutable_image_uri") or "")
    if not IMMUTABLE_IMAGE.fullmatch(immutable_image):
        raise CanaryLaunchError("deployment receipt does not contain an immutable image URI")

    prefix = procurement.prefix
    short_provider = "gemini" if plan.provider_id == "google_vertex_gemini" else "openai"
    job_name = f"{prefix}-{short_provider}-{permit.permit_id[-8:].lower()}"
    operator = f"{prefix}-operator@{project}.iam.gserviceaccount.com"
    cloud_sql = f"{project}:{REGION}:{prefix}-control"
    network = f"{prefix}-vpc"
    subnet = f"{prefix}-subnet"

    environment = {
        "AIGC_CANARY_PLAN_JSON": json.dumps(plan.model_dump(mode="json"), sort_keys=True),
        "AIGC_CANARY_GOVERNANCE_JSON": json.dumps(decision.model_dump(mode="json"), sort_keys=True),
        "AIGC_CANARY_PERMIT_JSON": json.dumps(permit.model_dump(mode="json"), sort_keys=True),
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as handle:
        env_path = Path(handle.name)
        yaml.safe_dump(environment, handle, sort_keys=True)
    try:
        _run(
            [
                "gcloud", "run", "jobs", "deploy", job_name,
                "--project", project,
                "--region", REGION,
                "--image", immutable_image,
                "--service-account", operator,
                "--tasks", "1",
                "--parallelism", "1",
                "--max-retries", "0",
                "--task-timeout", "180s",
                "--network", network,
                "--subnet", subnet,
                "--vpc-egress", "private-ranges-only",
                "--set-cloudsql-instances", cloud_sql,
                "--command", "python",
                "--args", "-m,src.operations.nexus_provider_canary",
                "--env-vars-file", str(env_path),
                "--labels", f"aigc-release-sha={plan.exact_revision},aigc-provider={short_provider}",
                "--quiet",
            ],
            mutating=True,
        )
        execution_name = _run(
            [
                "gcloud", "run", "jobs", "execute", job_name,
                "--project", project,
                "--region", REGION,
                "--wait",
                "--format", "value(metadata.name)",
                "--quiet",
            ],
            mutating=True,
        )
    finally:
        env_path.unlink(missing_ok=True)

    receipt = _receipt_from_logs(project=project, job_name=job_name)
    if receipt.get("provider_id") != plan.provider_id:
        raise CanaryLaunchError("retrieved canary receipt provider mismatch")
    attempt = receipt.get("attempt") or {}
    if attempt.get("status") != "succeeded":
        raise CanaryLaunchError("live provider canary did not produce a successful attempt")
    audit = receipt.get("audit") or {}
    if int(audit.get("provider_api_calls_performed", 0)) != 1:
        raise CanaryLaunchError("live canary receipt does not prove exactly one provider API call")
    result = {
        "schema_version": "aigc.nexus-provider-canary-job-receipt.v1",
        "project_id": project,
        "region": REGION,
        "job_name": job_name,
        "execution_name": execution_name,
        "immutable_image_uri": immutable_image,
        "provider_receipt": receipt,
        "automatic_retry": False,
        "job_max_retries": 0,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--procurement", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--governance", type=Path, required=True)
    parser.add_argument("--permit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    procurement = ExternalReleaseContract.load(args.procurement)
    plan = ProviderCanaryPlan.model_validate(_object(args.plan))
    decision = GovernanceDecision.model_validate(_object(args.governance))
    permit = ExecutionPermit.model_validate(_object(args.permit))
    result = launch(
        procurement=procurement,
        deployment=_object(args.deployment_receipt),
        plan=plan,
        decision=decision,
        permit=permit,
        output=args.output,
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProcurementError, CanaryLaunchError, ValueError) as exc:
        raise SystemExit(f"Nexus provider canary job blocked: {exc}") from exc
