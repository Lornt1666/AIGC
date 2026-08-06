from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate_gemini_staging_authorization import (
    StagingAuthorizationError,
    validate_authorization,
)


class StagingDeploymentError(RuntimeError):
    """Raised before or during a permit-bound staging deployment."""


_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


def _run(
    command: Sequence[str],
    *,
    capture: bool = False,
) -> str:
    completed = subprocess.run(
        list(command),
        check=False,
        capture_output=capture,
        text=True,
    )
    if completed.returncode != 0:
        raise StagingDeploymentError(
            f"Command failed without exposing command output: {command[0]}"
        )
    return completed.stdout.strip() if capture else ""


def _git_release_sha(expected: str) -> None:
    head = _run(["git", "rev-parse", "HEAD"], capture=True)
    if head != expected:
        raise StagingDeploymentError(
            "Authorized release SHA does not match repository HEAD"
        )
    dirty = _run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        capture=True,
    )
    if dirty:
        raise StagingDeploymentError(
            "Staging deployment requires a clean repository"
        )


def build_plan(payload: dict[str, Any]) -> dict[str, Any]:
    cloud = payload["cloud"]
    project = cloud["project_id"]
    region = cloud["primary_region"]
    sha = payload["release_revision"]
    image_base = (
        f"{region}-docker.pkg.dev/{project}/"
        f"{cloud['artifact_registry_repository']}/aigc-gemini"
    )
    tagged_image = f"{image_base}:{sha}"
    return {
        "project_id": project,
        "region": region,
        "release_revision": sha,
        "tagged_image_for_build_only": tagged_image,
        "operator_service": cloud["operator_service_name"],
        "judge_service": cloud["judge_service_name"],
        "deployment_image_form": f"{image_base}@sha256:<resolved-by-registry>",
        "traffic_migration_performed": False,
        "live_model_call_performed": False,
        "external_business_action_performed": False,
    }


def deploy(
    payload: dict[str, Any],
    *,
    output: Path,
) -> dict[str, Any]:
    summary = validate_authorization(payload, gate="deploy")
    _git_release_sha(summary["release_revision"])
    cloud = payload["cloud"]
    accounts = payload["service_accounts"]
    refs = payload["secret_manager_exact_version_refs"]
    project = summary["project_id"]
    region = summary["region"]
    sha = summary["release_revision"]
    image_base = (
        f"{region}-docker.pkg.dev/{project}/"
        f"{cloud['artifact_registry_repository']}/aigc-gemini"
    )
    tagged_image = f"{image_base}:{sha}"

    # Read-only prerequisite checks. This script never creates IAM, databases,
    # buckets, secrets, budgets, or Artifact Registry repositories.
    _run(
        [
            "gcloud",
            "artifacts",
            "repositories",
            "describe",
            cloud["artifact_registry_repository"],
            "--location",
            region,
            "--project",
            project,
        ]
    )
    _run(
        [
            "gcloud",
            "sql",
            "instances",
            "describe",
            cloud["cloud_sql_instance_connection_name"].split(":")[-1],
            "--project",
            project,
        ]
    )
    for bucket in (
        cloud["evidence_bucket"],
        cloud["judge_receipt_bucket"],
    ):
        _run(
            [
                "gcloud",
                "storage",
                "buckets",
                "describe",
                f"gs://{bucket}",
                "--project",
                project,
            ]
        )
    for account in accounts.values():
        _run(
            [
                "gcloud",
                "iam",
                "service-accounts",
                "describe",
                account,
                "--project",
                project,
            ]
        )
    for reference in refs.values():
        _run(
            [
                "gcloud",
                "secrets",
                "versions",
                "describe",
                reference.rsplit("/", 1)[-1],
                "--secret",
                reference.split("/secrets/", 1)[1].split("/", 1)[0],
                "--project",
                project,
            ]
        )

    build_id = _run(
        [
            "gcloud",
            "builds",
            "submit",
            "--project",
            project,
            "--config",
            "cloudbuild.gemini.yaml",
            "--ignore-file",
            ".gcloudignore.gemini",
            "--substitutions",
            f"_IMAGE_URI={tagged_image}",
            "--format",
            "value(id)",
            ".",
        ],
        capture=True,
    )
    digest = _run(
        [
            "gcloud",
            "artifacts",
            "docker",
            "images",
            "describe",
            tagged_image,
            "--project",
            project,
            "--format",
            "value(image_summary.digest)",
        ],
        capture=True,
    )
    if not _DIGEST.fullmatch(digest):
        raise StagingDeploymentError(
            "Artifact Registry did not return an immutable image digest"
        )
    immutable_image = f"{image_base}@{digest}"
    authorization_sha256 = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    operator_env = {
        "AIGC_ENV": "production",
        "AIGC_SURFACE": "operator",
        "AIGC_GEMINI_ENABLED": "true",
        "AIGC_RELEASE_REVISION": sha,
        "GOOGLE_CLOUD_PROJECT": project,
        "GOOGLE_CLOUD_LOCATION": cloud["vertex_location"],
        "AIGC_GEMINI_MODEL": payload.get("gemini_model", ""),
        "AIGC_GEMINI_MAX_ATTEMPTS": "1",
        "AIGC_IMAGE_DIGEST": digest,
        "AIGC_SECRET_ACCESS_MANIFEST_PATH": (
            "/app/config/gemini_secret_access_manifest.json"
        ),
        "AIGC_DEPLOYMENT_AUTHORIZATION_SHA256": authorization_sha256,
        "AIGC_GEMINI_EVIDENCE_BACKEND": "gcs",
        "AIGC_GEMINI_EVIDENCE_BUCKET": cloud["evidence_bucket"],
        "AIGC_GEMINI_EVIDENCE_PREFIX": "product-evidence/gemini",
        "AIGC_GEMINI_EVIDENCE_READINESS_OBJECT": (
            "product-evidence/gemini/readiness.json"
        ),
        "AIGC_GEMINI_CONTROL_DSN_SECRET_REF": refs[
            "runtime_control_dsn"
        ],
        "AIGC_OPERATOR_TOKEN_SECRET_REF": refs["operator_token"],
        "AIGC_OPERATOR_BINDING_KEY_SECRET_REF": refs[
            "operator_binding_key"
        ],
        "AIGC_RUNTIME_ADMIN_TOKEN_SECRET_REF": refs[
            "runtime_admin_token"
        ],
        "AIGC_RUNTIME_ADMIN_BINDING_KEY_SECRET_REF": refs[
            "runtime_admin_binding_key"
        ],
    }
    if not operator_env["AIGC_GEMINI_MODEL"]:
        raise StagingDeploymentError(
            "Authorization must record the exact gemini_model"
        )
    judge_env = {
        "AIGC_ENV": "production",
        "AIGC_SURFACE": "judge",
        "AIGC_GEMINI_ENABLED": "false",
        "AIGC_RELEASE_REVISION": sha,
        "GOOGLE_CLOUD_PROJECT": project,
        "AIGC_JUDGE_TOKEN_SECRET_REF": refs["judge_token"],
        "AIGC_JUDGE_BINDING_KEY_SECRET_REF": refs["judge_binding_key"],
        "AIGC_JUDGE_RECEIPT_BUCKET": cloud["judge_receipt_bucket"],
        "AIGC_JUDGE_RECEIPT_PREFIX": "judge-receipts/v1",
        "AIGC_JUDGE_READINESS_OBJECT": (
            "judge-receipts/v1/readiness.json"
        ),
        "AIGC_IMAGE_DIGEST": digest,
        "AIGC_SECRET_ACCESS_MANIFEST_PATH": (
            "/app/config/gemini_secret_access_manifest.json"
        ),
        "AIGC_DEPLOYMENT_AUTHORIZATION_SHA256": authorization_sha256,
    }

    operator_target = _deploy_surface(
        project=project,
        region=region,
        service=cloud["operator_service_name"],
        image=immutable_image,
        service_account=accounts["operator_runtime"],
        environment=operator_env,
        cloud_sql_instance=cloud["cloud_sql_instance_connection_name"],
    )
    judge_target = _deploy_surface(
        project=project,
        region=region,
        service=cloud["judge_service_name"],
        image=immutable_image,
        service_account=accounts["judge_runtime"],
        environment=judge_env,
        cloud_sql_instance=None,
    )
    receipt = {
        "schema_version": "aigc.gemini-staging-deployment-receipt.v1",
        "project_id": project,
        "region": region,
        "release_revision": sha,
        "build_id": build_id,
        "image_digest": digest,
        "immutable_image_uri": immutable_image,
        "operator_service": cloud["operator_service_name"],
        "operator_revision": operator_target["revision"],
        "operator_candidate_url": operator_target["url"],
        "operator_service_url": operator_target["service_url"],
        "judge_service": cloud["judge_service_name"],
        "judge_revision": judge_target["revision"],
        "judge_candidate_url": judge_target["url"],
        "judge_service_url": judge_target["service_url"],
        "traffic_migration_performed": False,
        "live_model_call_performed": False,
        "external_business_action_performed": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def _deploy_surface(
    *,
    project: str,
    region: str,
    service: str,
    image: str,
    service_account: str,
    environment: dict[str, str],
    cloud_sql_instance: str | None,
) -> dict[str, str]:
    env_file = Path("/tmp") / f"{service}-env.yaml"
    env_file.write_text(
        "\n".join(
            f"{key}: {json.dumps(value)}"
            for key, value in sorted(environment.items())
        )
        + "\n",
        encoding="utf-8",
    )
    command = [
        "gcloud",
        "run",
        "deploy",
        service,
        "--project",
        project,
        "--region",
        region,
        "--platform",
        "managed",
        "--image",
        image,
        "--service-account",
        service_account,
        "--no-allow-unauthenticated",
        "--no-traffic",
        "--tag",
        f"candidate-{environment['AIGC_RELEASE_REVISION'][:8]}",
        "--min-instances",
        "0",
        "--max-instances",
        "2",
        "--concurrency",
        "8",
        "--timeout",
        "60",
        "--env-vars-file",
        str(env_file),
        "--labels",
        f"aigc-release-sha={environment['AIGC_RELEASE_REVISION']}",
        "--format",
        "value(status.latestCreatedRevisionName)",
    ]
    if cloud_sql_instance:
        command.extend(["--add-cloudsql-instances", cloud_sql_instance])
    try:
        revision = _run(command, capture=True)
    finally:
        try:
            env_file.unlink()
        except FileNotFoundError:
            pass
    if not revision:
        raise StagingDeploymentError(
            f"Cloud Run did not return a revision for {service}"
        )
    described = json.loads(
        _run(
            [
                "gcloud",
                "run",
                "services",
                "describe",
                service,
                "--project",
                project,
                "--region",
                region,
                "--format",
                "json",
            ],
            capture=True,
        )
    )
    traffic = described.get("status", {}).get("traffic", [])
    service_url = described.get("status", {}).get("url", "")
    target = next(
        (
            item
            for item in traffic
            if item.get("revisionName") == revision
            and item.get("tag")
            == f"candidate-{environment['AIGC_RELEASE_REVISION'][:8]}"
        ),
        None,
    )
    url = target.get("url", "") if isinstance(target, dict) else ""
    if not isinstance(url, str) or not url.startswith("https://"):
        raise StagingDeploymentError(
            f"Cloud Run did not return a candidate URL for {service}"
        )
    if not isinstance(service_url, str) or not service_url.startswith(
        "https://"
    ):
        raise StagingDeploymentError(
            f"Cloud Run did not return a service URL for {service}"
        )
    return {
        "revision": revision,
        "url": url,
        "service_url": service_url,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("authorization", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "reports/artifacts/gemini_staging/deployment-receipt.json"
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the permit-bound Cloud Build and Cloud Run deployment.",
    )
    args = parser.parse_args()
    payload = json.loads(args.authorization.read_text(encoding="utf-8"))
    if args.execute:
        result = deploy(payload, output=args.output)
    else:
        validate_authorization(payload, gate="deploy")
        result = build_plan(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StagingAuthorizationError, StagingDeploymentError) as exc:
        raise SystemExit(f"Staging deployment blocked: {exc}") from exc
