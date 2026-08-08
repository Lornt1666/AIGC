from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Sequence
from urllib.request import Request, urlopen

from scripts.validate_quebec_cloud_authorization import (
    AuthorizationError,
    validate as validate_quebec_authorization,
)


REGION = "northamerica-northeast1"
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


class NexusStagingDeploymentError(RuntimeError):
    pass


class NexusStagingMutationIndeterminate(NexusStagingDeploymentError):
    pass


def _run(command: Sequence[str], *, capture: bool = False, mutating: bool = False) -> str:
    completed = subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        error_type = NexusStagingMutationIndeterminate if mutating else NexusStagingDeploymentError
        raise error_type(f"command failed: {command[0]} {command[1] if len(command) > 1 else ''}")
    return completed.stdout.strip() if capture else ""


def _git_identity(expected_sha: str, expected_tree: str) -> None:
    observed_sha = _run(["git", "rev-parse", "HEAD"], capture=True)
    observed_tree = _run(["git", "rev-parse", "HEAD^{tree}"], capture=True)
    if observed_sha != expected_sha or observed_tree != expected_tree:
        raise NexusStagingDeploymentError("authorized release SHA/tree does not match checkout")
    dirty = _run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        capture=True,
    )
    if dirty:
        raise NexusStagingDeploymentError("staging deployment requires a clean checkout")


def _authorization_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def build_plan(payload: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    summary = validate_quebec_authorization(payload, gate="staging", manifest=manifest)
    resources = payload["resources"]
    project = summary["project_id"]
    release_sha = summary["release_sha"]
    image_base = (
        f"{REGION}-docker.pkg.dev/{project}/"
        f"{resources['artifact_registry_repository']}/aigc-nexus"
    )
    return {
        "schema_version": "aigc.nexus-staging-plan.v1",
        "project_id": project,
        "region": REGION,
        "release_sha": release_sha,
        "release_tree_sha": summary["release_tree_sha"],
        "build_tag": f"{image_base}:{release_sha}",
        "deployment_image_form": f"{image_base}@sha256:<registry-resolved>",
        "service": resources["operator_service"],
        "cloud_sql_instance": f"{project}:{REGION}:{resources['cloud_sql_instance']}",
        "health_path": "/health",
        "readiness_path": "/ready",
        "observability_path": "/observability",
        "public_traffic": False,
        "traffic_migration": False,
        "live_model_call": False,
        "production_activation": False,
    }


def _authenticated_json(url: str, *, audience: str) -> dict[str, Any]:
    token = _run(
        ["gcloud", "auth", "print-identity-token", f"--audiences={audience}"],
        capture=True,
    )
    if not token:
        raise NexusStagingDeploymentError("gcloud did not return an identity token")
    request = Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        token = ""
    if not isinstance(payload, dict):
        raise NexusStagingDeploymentError("candidate probe returned invalid JSON")
    return payload


def _candidate_target(*, project: str, service: str) -> dict[str, str]:
    described = json.loads(
        _run(
            [
                "gcloud", "run", "services", "describe", service,
                "--project", project,
                "--region", REGION,
                "--format", "json",
            ],
            capture=True,
        )
    )
    status = described.get("status") or {}
    service_url = str(status.get("url") or "")
    traffic = status.get("traffic") or []
    tagged = [item for item in traffic if isinstance(item, dict) and item.get("tag")]
    if not tagged:
        raise NexusStagingDeploymentError("Cloud Run did not return a tagged candidate URL")
    candidate = tagged[-1]
    return {
        "service_url": service_url,
        "candidate_url": str(candidate.get("url") or ""),
        "revision": str(candidate.get("revisionName") or ""),
    }


def deploy(
    payload: dict[str, Any],
    manifest: dict[str, Any],
    *,
    output: Path,
) -> dict[str, Any]:
    summary = validate_quebec_authorization(payload, gate="staging", manifest=manifest)
    _git_identity(summary["release_sha"], summary["release_tree_sha"])
    resources = payload["resources"]
    accounts = payload["service_accounts"]
    refs = payload["exact_secret_version_refs"]
    project = summary["project_id"]
    release_sha = summary["release_sha"]
    service = resources["operator_service"]
    repository = resources["artifact_registry_repository"]
    image_base = f"{REGION}-docker.pkg.dev/{project}/{repository}/aigc-nexus"
    tagged_image = f"{image_base}:{release_sha}"

    # Read-only existence checks occur before the first cloud mutation.
    _run([
        "gcloud", "artifacts", "repositories", "describe", repository,
        "--project", project, "--location", REGION,
    ])
    _run([
        "gcloud", "sql", "instances", "describe", resources["cloud_sql_instance"],
        "--project", project,
    ])
    _run([
        "gcloud", "iam", "service-accounts", "describe", accounts["operator"],
        "--project", project,
    ])

    build_id = _run(
        [
            "gcloud", "builds", "submit", ".",
            "--project", project,
            "--region", REGION,
            "--config", "cloudbuild.nexus.yaml",
            "--ignore-file", ".gcloudignore.nexus",
            "--substitutions", f"_IMAGE_URI={tagged_image}",
            "--format", "value(id)",
        ],
        capture=True,
        mutating=True,
    )
    digest = _run(
        [
            "gcloud", "artifacts", "docker", "images", "describe", tagged_image,
            "--project", project,
            "--format", "value(image_summary.digest)",
        ],
        capture=True,
    )
    if not _DIGEST.fullmatch(digest):
        raise NexusStagingDeploymentError("Artifact Registry returned an invalid digest")
    immutable_image = f"{image_base}@{digest}"

    environment = {
        "AIGC_ENV": "staging",
        "AIGC_RELEASE_REVISION": release_sha,
        "AIGC_IMAGE_DIGEST": digest,
        "AIGC_REGION": REGION,
        # This is a non-secret reference, not the secret value. The runtime resolves
        # the exact regional secret through the Montréal Secret Manager endpoint.
        "AIGC_NEXUS_RUNTIME_CONTROL_DSN_SECRET_REF": refs["runtime_control_dsn"],
        "AIGC_DEPLOYMENT_AUTHORIZATION_SHA256": _authorization_hash(payload),
        "AIGC_LIVE_PROVIDER_EXECUTION_ENABLED": "false",
        "AIGC_PRODUCTION_ACTIVATION": "false",
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as handle:
        env_path = Path(handle.name)
        for key, value in sorted(environment.items()):
            handle.write(f"{key}: {json.dumps(value)}\n")
    try:
        _run(
            [
                "gcloud", "run", "deploy", service,
                "--project", project,
                "--region", REGION,
                "--platform", "managed",
                "--image", immutable_image,
                "--service-account", accounts["operator"],
                "--no-allow-unauthenticated",
                "--no-traffic",
                "--tag", f"candidate-{release_sha[:8]}",
                "--min-instances", "0",
                "--max-instances", "2",
                "--concurrency", "8",
                "--timeout", "60",
                "--env-vars-file", str(env_path),
                "--add-cloudsql-instances",
                f"{project}:{REGION}:{resources['cloud_sql_instance']}",
                "--deploy-health-check",
                "--startup-probe", "httpGet.path=/ready,httpGet.port=8080,timeoutSeconds=2,periodSeconds=5,failureThreshold=24",
                "--liveness-probe", "httpGet.path=/health,httpGet.port=8080,timeoutSeconds=2,periodSeconds=10,failureThreshold=3",
                "--readiness-probe", "httpGet.path=/ready,httpGet.port=8080,timeoutSeconds=2,periodSeconds=5,failureThreshold=3",
                "--labels", f"aigc-release-sha={release_sha}",
            ],
            mutating=True,
        )
    finally:
        env_path.unlink(missing_ok=True)

    target = _candidate_target(project=project, service=service)
    if not target["service_url"].startswith("https://") or not target["candidate_url"].startswith("https://"):
        raise NexusStagingDeploymentError("Cloud Run candidate URLs are invalid")
    ready = _authenticated_json(
        target["candidate_url"].rstrip("/") + "/ready",
        audience=target["service_url"],
    )
    receipt = {
        "schema_version": "aigc.nexus-staging-deployment-receipt.v1",
        "deployment_status": "succeeded" if ready.get("ready") is True else "deployed_not_ready",
        "repository": "Lornt1666/AIGC",
        "project_id": project,
        "region": REGION,
        "release_sha": release_sha,
        "release_tree_sha": summary["release_tree_sha"],
        "authorization_sha256": _authorization_hash(payload),
        "resource_manifest_sha256": payload["resource_manifest_sha256"],
        "build_id": build_id,
        "image_digest": digest,
        "immutable_image_uri": immutable_image,
        "service": service,
        "revision": target["revision"],
        "candidate_url": target["candidate_url"],
        "service_url": target["service_url"],
        "health_path": "/health",
        "readiness_path": "/ready",
        "readiness_verified": ready.get("ready") is True,
        "runtime_control_backend": ready.get("runtime_control_backend"),
        "traffic_migration_performed": False,
        "public_access_enabled": False,
        "live_model_call_performed": False,
        "production_activation": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if receipt["readiness_verified"] is not True:
        raise NexusStagingDeploymentError("candidate deployed but readiness proof failed")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("authorization", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/artifacts/nexus_staging/deployment-receipt.json"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.authorization.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.execute:
        result = deploy(payload, manifest, output=args.output)
    else:
        result = build_plan(payload, manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AuthorizationError, NexusStagingDeploymentError) as exc:
        raise SystemExit(f"Nexus staging deployment blocked: {exc}") from exc
