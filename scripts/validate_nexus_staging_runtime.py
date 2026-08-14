from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import statistics
import subprocess
import time
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.state_reducer import ReconciliationRequired, reduce_observed_state
from src.domain.epistemic.models import ArtifactState
from src.domain.nexus.contracts import ExecutionReceipt


class NexusStagingValidationError(RuntimeError):
    pass


REGION = "northamerica-northeast1"
_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_RESOURCE = re.compile(r"^[a-z][a-z0-9-]{0,61}[a-z0-9]$")
_REVISION = re.compile(r"^[a-z][a-z0-9-]{0,61}[a-z0-9]$")
_RELEASE_SHA = re.compile(r"^[a-f0-9]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


def _https_origin(value: str, *, name: str) -> tuple[str, str]:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{name} must be an HTTPS origin without credentials, path, query, fragment, or port")
    host = parsed.hostname.lower()
    if not host.endswith(".run.app"):
        raise ValueError(f"{name} must be a Google-managed Cloud Run origin")
    return f"https://{host}", host


@dataclass(frozen=True)
class VerifiedCandidateTarget:
    project_id: str
    region: str
    service: str
    revision: str
    release_sha: str
    image_digest: str
    candidate_url: str
    audience: str

    def __post_init__(self) -> None:
        if not _PROJECT.fullmatch(self.project_id):
            raise ValueError("candidate project_id is invalid")
        if self.region != REGION:
            raise ValueError(f"candidate region must equal {REGION}")
        if not _RESOURCE.fullmatch(self.service) or not _REVISION.fullmatch(self.revision):
            raise ValueError("candidate service/revision identity is invalid")
        if not _RELEASE_SHA.fullmatch(self.release_sha):
            raise ValueError("candidate release_sha is invalid")
        if not _IMAGE_DIGEST.fullmatch(self.image_digest):
            raise ValueError("candidate image_digest is invalid")
        candidate_origin, candidate_host = _https_origin(self.candidate_url, name="candidate_url")
        audience_origin, audience_host = _https_origin(self.audience, name="audience")
        if candidate_host != audience_host and not candidate_host.endswith("---" + audience_host):
            raise ValueError("candidate_url is not bound to the audience Cloud Run service")
        object.__setattr__(self, "candidate_url", candidate_origin)
        object.__setattr__(self, "audience", audience_origin)


def _gcloud_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise NexusStagingValidationError("unable to resolve the authorized Cloud Run candidate")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise NexusStagingValidationError("Cloud Run candidate metadata is invalid JSON") from exc
    if not isinstance(value, dict):
        raise NexusStagingValidationError("Cloud Run candidate metadata must be an object")
    return value


def resolve_candidate_target(
    *,
    project_id: str,
    service: str,
    revision: str,
    release_sha: str,
    image_digest: str,
) -> VerifiedCandidateTarget:
    described = _gcloud_json(
        [
            "gcloud", "run", "services", "describe", service,
            "--project", project_id,
            "--region", REGION,
            "--format", "json",
        ]
    )
    status = described.get("status") or {}
    audience = str(status.get("url") or "")
    expected_tag = f"candidate-{release_sha[:8]}"
    matching = [
        item
        for item in (status.get("traffic") or [])
        if isinstance(item, dict)
        and item.get("tag") == expected_tag
        and item.get("revisionName") == revision
    ]
    if len(matching) != 1:
        raise NexusStagingValidationError("exact tagged candidate revision was not found")
    candidate_url = str(matching[0].get("url") or "")

    revision_metadata = _gcloud_json(
        [
            "gcloud", "run", "revisions", "describe", revision,
            "--project", project_id,
            "--region", REGION,
            "--format", "json",
        ]
    )
    containers = ((revision_metadata.get("spec") or {}).get("containers") or [])
    observed_image = str(containers[0].get("image") or "") if containers and isinstance(containers[0], dict) else ""
    if not observed_image.endswith("@" + image_digest):
        raise NexusStagingValidationError("candidate revision does not run the authorized image digest")
    labels = (revision_metadata.get("metadata") or {}).get("labels") or {}
    if labels.get("aigc-release-sha") != release_sha:
        raise NexusStagingValidationError("candidate revision release label mismatch")

    return VerifiedCandidateTarget(
        project_id=project_id,
        region=REGION,
        service=service,
        revision=revision,
        release_sha=release_sha,
        image_digest=image_digest,
        candidate_url=candidate_url,
        audience=audience,
    )


def _identity_token(audience: str) -> str:
    completed = subprocess.run(
        ["gcloud", "auth", "print-identity-token", f"--audiences={audience}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise NexusStagingValidationError("unable to obtain staging identity token")
    return completed.stdout.strip()


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]


def _canonical_reconciliation_check() -> dict[str, object]:
    state = ArtifactState(stage="staging_validation", revision=1)
    receipt = ExecutionReceipt(
        receipt_id="EXEC-STAGING-RECON01",
        change_set_id="CHG-STAGING-RECON01",
        parent_state_hash=canonical_sha256(state),
        execution_status="indeterminate",
        external_action_performed=True,
        reconciliation_required=True,
    )
    try:
        reduce_observed_state(state, receipt)
    except ReconciliationRequired:
        return {
            "canonical_reconciliation_boundary": "PASS",
            "state_advanced": False,
            "deployed_fault_injection_performed": False,
        }
    raise NexusStagingValidationError("indeterminate receipt advanced canonical state")


def validate_candidate(
    *,
    target: VerifiedCandidateTarget,
    requests: int = 20,
    concurrency: int = 4,
    token_supplier: Callable[[str], str] = _identity_token,
) -> dict[str, Any]:
    if requests < 1 or requests > 200 or concurrency < 1 or concurrency > 20:
        raise ValueError("validation load bounds are invalid")
    token = token_supplier(target.audience)
    headers = {"Authorization": f"Bearer {token}"}
    base = target.candidate_url.rstrip("/")
    try:
        with httpx.Client(timeout=15.0, follow_redirects=False) as client:
            health = client.get(base + "/health", headers=headers)
            ready = client.get(base + "/ready", headers=headers)
            observability = client.get(base + "/observability", headers=headers)
            invalid = client.get(base + "/definitely-not-a-route", headers=headers)
            unauthenticated = client.get(base + "/ready")
        if health.status_code != 200 or health.json().get("ok") is not True:
            raise NexusStagingValidationError("authenticated health probe failed")
        if ready.status_code != 200 or ready.json().get("ready") is not True:
            raise NexusStagingValidationError("authenticated readiness probe failed")
        if observability.status_code != 200:
            raise NexusStagingValidationError("observability probe failed")
        observable = observability.json()
        if observable.get("secret_values_exposed") is not False:
            raise NexusStagingValidationError("observability surface may expose secret values")
        if invalid.status_code != 404:
            raise NexusStagingValidationError("invalid authenticated route did not fail closed")
        if unauthenticated.status_code not in {401, 403, 404}:
            raise NexusStagingValidationError("unauthenticated candidate request was not denied")

        latencies: list[float] = []
        statuses: list[int] = []

        def one_request() -> tuple[int, float]:
            started = time.perf_counter()
            response = httpx.get(base + "/ready", headers=headers, timeout=15.0)
            return response.status_code, max(0.0, (time.perf_counter() - started) * 1000.0)

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(one_request) for _ in range(requests)]
            for future in as_completed(futures):
                status, latency_ms = future.result()
                statuses.append(status)
                latencies.append(latency_ms)
        failures = sum(1 for value in statuses if value != 200)
        if failures:
            raise NexusStagingValidationError(
                f"readiness load validation observed {failures} failed requests"
            )
        reconciliation = _canonical_reconciliation_check()
        return {
            "schema_version": "aigc.nexus-staging-validation-receipt.v1",
            "project_id": target.project_id,
            "region": target.region,
            "service": target.service,
            "revision": target.revision,
            "release_sha": target.release_sha,
            "image_digest": target.image_digest,
            "candidate_url": target.candidate_url,
            "audience": target.audience,
            "authenticated_health": "PASS",
            "authenticated_readiness": "PASS",
            "unauthenticated_access": "DENIED",
            "invalid_route": "FAIL_CLOSED",
            "observability_secret_values_exposed": False,
            "load_requests": requests,
            "load_concurrency": concurrency,
            "load_failures": failures,
            "latency_ms_mean": round(statistics.fmean(latencies), 3),
            "latency_ms_p50": round(_percentile(latencies, 0.50), 3),
            "latency_ms_p95": round(_percentile(latencies, 0.95), 3),
            "latency_ms_max": round(max(latencies), 3),
            **reconciliation,
            "provider_calls_performed": 0,
            "production_activation": False,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        token = ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = resolve_candidate_target(
        project_id=args.project_id,
        service=args.service,
        revision=args.revision,
        release_sha=args.release_sha,
        image_digest=args.image_digest,
    )
    result = validate_candidate(
        target=target,
        requests=args.requests,
        concurrency=args.concurrency,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NexusStagingValidationError as exc:
        raise SystemExit(f"Nexus staging validation failed: {exc}") from exc
