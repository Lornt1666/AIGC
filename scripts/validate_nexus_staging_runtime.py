from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess
import time
from typing import Any, Callable

import httpx

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.state_reducer import ReconciliationRequired, reduce_observed_state
from src.domain.epistemic.models import ArtifactState
from src.domain.nexus.contracts import ExecutionReceipt


class NexusStagingValidationError(RuntimeError):
    pass


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
    candidate_url: str,
    audience: str,
    requests: int = 20,
    concurrency: int = 4,
    token_supplier: Callable[[str], str] = _identity_token,
) -> dict[str, Any]:
    if not candidate_url.startswith("https://") or not audience.startswith("https://"):
        raise ValueError("candidate_url and audience must be HTTPS URLs")
    if requests < 1 or requests > 200 or concurrency < 1 or concurrency > 20:
        raise ValueError("validation load bounds are invalid")
    token = token_supplier(audience)
    headers = {"Authorization": f"Bearer {token}"}
    base = candidate_url.rstrip("/")
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
            "candidate_url": candidate_url,
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
    parser.add_argument("--candidate-url", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_candidate(
        candidate_url=args.candidate_url,
        audience=args.audience,
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
