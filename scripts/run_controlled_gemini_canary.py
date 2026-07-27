from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.gemini_workflow.secret_broker import OmegaXSecretAccess
from scripts.validate_gemini_staging_authorization import (
    validate_authorization,
)


class ControlledCanaryError(RuntimeError):
    """Raised when a one-call permit or runtime receipt fails closed."""


_SHA = re.compile(r"^[a-f0-9]{40}$")
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_REQUIRED_CI_ARTIFACTS = {
    "gemini-workflow-offline-smoke",
    "test-results",
    "terraform-validation",
}


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_ci_receipt(
    receipt: dict[str, Any],
    *,
    release_revision: str,
) -> None:
    if receipt.get("schema_version") != (
        "aigc.github-actions-ci-receipt.v1"
    ):
        raise ControlledCanaryError("CI receipt schema is invalid")
    if receipt.get("repository") != "Lornt1666/AIGC":
        raise ControlledCanaryError("CI receipt targets another repository")
    if receipt.get("conclusion") != "success":
        raise ControlledCanaryError("CI receipt is not successful")
    if receipt.get("head_sha") != release_revision:
        raise ControlledCanaryError("CI receipt is for another release SHA")
    if not isinstance(receipt.get("steps_executed"), int) or receipt[
        "steps_executed"
    ] <= 0:
        raise ControlledCanaryError(
            "A zero-step Actions job is not a valid CI receipt"
        )
    run_url = receipt.get("run_url")
    if (
        not isinstance(run_url, str)
        or not run_url.startswith(
            "https://github.com/Lornt1666/AIGC/actions/runs/"
        )
    ):
        raise ControlledCanaryError("CI receipt run URL is invalid")
    artifacts = receipt.get("required_artifacts")
    if not isinstance(artifacts, list) or not _REQUIRED_CI_ARTIFACTS.issubset(
        {str(item).split("-", 1)[0] for item in artifacts}
    ):
        # Accept artifact names with release suffixes by prefix below.
        if not isinstance(artifacts, list) or any(
            not any(str(item).startswith(prefix) for item in artifacts)
            for prefix in _REQUIRED_CI_ARTIFACTS
        ):
            raise ControlledCanaryError(
                "CI receipt is missing required artifact families"
            )


def validate_live_permit(
    permit: dict[str, Any],
    *,
    authorization: dict[str, Any],
    deployment: dict[str, Any],
    input_sha256: str,
    now: datetime | None = None,
) -> None:
    if permit.get("schema_version") != (
        "aigc.gemini-live-assessment-permit.v1"
    ):
        raise ControlledCanaryError("Live assessment permit schema is invalid")
    if permit.get("authorized") is not True:
        raise ControlledCanaryError("Live assessment is not authorized")
    if permit.get("maximum_model_calls") != 1:
        raise ControlledCanaryError(
            "Live assessment permit must allow exactly one model call"
        )
    maximum_tokens = permit.get("maximum_reserved_tokens")
    if (
        isinstance(maximum_tokens, bool)
        or not isinstance(maximum_tokens, int)
        or not 256 <= maximum_tokens <= 4096
    ):
        raise ControlledCanaryError(
            "Live assessment token reservation is invalid"
        )
    expected = {
        "project_id": authorization["cloud"]["project_id"],
        "region": authorization["cloud"]["primary_region"],
        "operator_service_name": authorization["cloud"][
            "operator_service_name"
        ],
        "release_revision": authorization["release_revision"],
        "image_digest": deployment["image_digest"],
        "cloud_run_revision": deployment["operator_revision"],
        "input_fixture_sha256": input_sha256,
        "model": authorization["gemini_model"],
    }
    for name, value in expected.items():
        if permit.get(name) != value:
            raise ControlledCanaryError(
                f"Live assessment permit does not match {name}"
            )
    if not _SHA.fullmatch(str(permit["release_revision"])):
        raise ControlledCanaryError("Permit release SHA is invalid")
    if not _DIGEST.fullmatch(str(permit["image_digest"])):
        raise ControlledCanaryError("Permit image digest is invalid")
    if not str(permit.get("authorized_by", "")).strip():
        raise ControlledCanaryError("Permit has no accountable authorizer")
    expires_at = _timestamp(permit.get("expires_at"), "expires_at")
    if expires_at <= (now or datetime.now(timezone.utc)):
        raise ControlledCanaryError("Live assessment permit is expired")
    _timestamp(permit.get("authorized_at"), "authorized_at")
    required_phrase = (
        "AUTHORIZE ONE STAGING GEMINI ASSESSMENT "
        f"{permit['release_revision']} {permit['image_digest']} "
        f"{input_sha256}"
    )
    if permit.get("approval_phrase") != required_phrase:
        raise ControlledCanaryError(
            "Live assessment approval phrase does not bind the exact release"
        )


def run_canary(
    *,
    authorization: dict[str, Any],
    deployment: dict[str, Any],
    ci_receipt: dict[str, Any],
    permit: dict[str, Any],
    intake: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    validate_authorization(authorization, gate="live")
    release_revision = authorization["release_revision"]
    validate_ci_receipt(ci_receipt, release_revision=release_revision)
    input_sha256 = canonical_sha256(intake)
    validate_live_permit(
        permit,
        authorization=authorization,
        deployment=deployment,
        input_sha256=input_sha256,
    )
    candidate_url = str(deployment.get("operator_candidate_url", "")).rstrip(
        "/"
    )
    service_url = str(deployment.get("operator_service_url", "")).rstrip("/")
    if not candidate_url.startswith("https://"):
        raise ControlledCanaryError(
            "Deployment receipt has no HTTPS operator candidate URL"
        )
    if not service_url.startswith("https://"):
        raise ControlledCanaryError(
            "Deployment receipt has no HTTPS operator service URL"
        )
    identity_token = _command_output(
        [
            "gcloud",
            "auth",
            "print-identity-token",
            "--audiences",
            service_url,
        ]
    )
    secret_environment = dict(os.environ)
    secret_environment["AIGC_OPERATOR_TOKEN_SECRET_REF"] = authorization[
        "secret_manager_exact_version_refs"
    ]["operator_token"]
    secret_environment["AIGC_DEPLOYMENT_AUTHORIZATION_SHA256"] = (
        canonical_sha256(authorization)
    )
    operator_token, _secret_receipt = (
        OmegaXSecretAccess.from_environment(
            project_id=authorization["cloud"]["project_id"],
            environ=secret_environment,
        ).resolve("gemini-operator-authentication")
    )
    headers = {
        "Authorization": f"Bearer {identity_token}",
        "X-AIGC-Operator-Token": operator_token,
        "X-AIGC-Operator-Label": "controlled-staging-canary",
        "Origin": candidate_url,
    }
    with httpx.Client(timeout=65.0, trust_env=False) as client:
        ready = client.get(f"{candidate_url}/readyz", headers=headers)
        if ready.status_code != 200:
            raise ControlledCanaryError(
                "Operator candidate failed readiness before the live call"
            )
        ready_payload = ready.json()
        if (
            ready_payload.get("ready") is not True
            or ready_payload.get("generative_call_performed") is not False
            or ready_payload.get("external_action_performed") is not False
        ):
            raise ControlledCanaryError(
                "Operator readiness receipt is unsafe or incomplete"
            )

        idempotency_key = (
            "staging-canary-"
            f"{release_revision[:12]}-{input_sha256[:24]}"
        )
        headers["Idempotency-Key"] = idempotency_key
        try:
            response = client.post(
                f"{candidate_url}/api/gemini/workflows",
                headers=headers,
                json=intake,
            )
        except httpx.HTTPError as exc:
            _write_unknown_outcome(
                output,
                release_revision=release_revision,
                input_sha256=input_sha256,
                idempotency_key=idempotency_key,
                failure_class=type(exc).__name__,
            )
            raise ControlledCanaryError(
                "Live request outcome is unknown; do not retry with a new key"
            ) from exc

    if response.status_code != 200:
        _write_unknown_outcome(
            output,
            release_revision=release_revision,
            input_sha256=input_sha256,
            idempotency_key=idempotency_key,
            failure_class=f"HTTP_{response.status_code}",
        )
        raise ControlledCanaryError(
            "Controlled assessment did not return a valid success receipt; "
            "the outcome is non-retriable without a new explicit permit"
        )
    try:
        result = response.json()
    except (ValueError, TypeError) as exc:
        _write_unknown_outcome(
            output,
            release_revision=release_revision,
            input_sha256=input_sha256,
            idempotency_key=idempotency_key,
            failure_class="InvalidSuccessResponse",
        )
        raise ControlledCanaryError(
            "Live response was not valid JSON; do not retry without a new "
            "explicit permit"
        ) from exc
    payload = result.get("payload", {})
    runtime = result.get("runtime_receipt", {})
    evidence_uri = runtime.get("evidence_object_uri")
    evidence_generation = runtime.get("evidence_generation")
    if (
        result.get("event_type") != "gemini_execution"
        or result.get("model_api_call_status") != "confirmed"
        or result.get("model_api_call_performed") is not True
        or result.get("external_business_action_performed") is not False
        or payload.get("live_model_call") is not True
        or payload.get("transport") != "vertex_ai"
        or payload.get("model") != authorization["gemini_model"]
        or runtime.get("state") != "completed"
        or runtime.get("source_revision") != release_revision
        or runtime.get("runtime_revision")
        != deployment["operator_revision"]
        or runtime.get("image_digest") != deployment["image_digest"]
        or not isinstance(evidence_uri, str)
        or not evidence_uri.startswith("gs://")
        or not isinstance(evidence_generation, int)
        or evidence_generation <= 0
    ):
        _write_unknown_outcome(
            output,
            release_revision=release_revision,
            input_sha256=input_sha256,
            idempotency_key=idempotency_key,
            failure_class="RuntimeEvidenceContractMismatch",
        )
        raise ControlledCanaryError(
            "Live response did not satisfy the runtime evidence contract; "
            "do not retry without a new explicit permit"
        )
    usage = payload.get("usage", {})
    receipt = {
        "schema_version": "aigc.gemini-runtime-receipt.v1",
        "environment": "staging",
        "business_identity": "RegenExcalibur",
        "repository": "Lornt1666/AIGC",
        "release_revision": release_revision,
        "image_digest": deployment["image_digest"],
        "cloud_run_revision": deployment["operator_revision"],
        "provider": "google_vertex_ai",
        "model": payload["model"],
        "location": authorization["cloud"]["vertex_location"],
        "response_id_present": bool(payload.get("response_id")),
        "latency_ms": payload.get("latency_ms"),
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "candidate_tokens": usage.get("candidate_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "workflow_run_id": result["run_id"],
        "input_sha256": payload.get("input_sha256"),
        "assessment_sha256": payload.get("assessment_sha256"),
        "policy_outcome": payload.get("policy", {}).get("outcome"),
        "model_api_call_status": "confirmed",
        "model_api_call_performed": True,
        "external_business_action_performed": False,
        "idempotency_key_sha256": hashlib.sha256(
            idempotency_key.encode("utf-8")
        ).hexdigest(),
        "evidence": {
            "object_uri": evidence_uri,
            "generation": evidence_generation,
            "record_sha256": result.get("record_sha256"),
        },
        "ci": ci_receipt,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def _command_output(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise ControlledCanaryError(
            "Google Cloud identity-token acquisition failed"
        )
    return completed.stdout.strip()


def _timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ControlledCanaryError(f"Permit {name} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ControlledCanaryError(f"Permit {name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ControlledCanaryError(f"Permit {name} needs a timezone")
    return parsed.astimezone(timezone.utc)


def _write_unknown_outcome(
    output: Path,
    *,
    release_revision: str,
    input_sha256: str,
    idempotency_key: str,
    failure_class: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": (
                    "aigc.gemini-runtime-attempt-unknown.v1"
                ),
                "release_revision": release_revision,
                "input_sha256": input_sha256,
                "idempotency_key_sha256": hashlib.sha256(
                    idempotency_key.encode("utf-8")
                ).hexdigest(),
                "model_api_call_status": "attempted_outcome_unknown",
                "model_api_call_performed": None,
                "failure_class": failure_class,
                "retry_authorized": False,
                "external_business_action_performed": False,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ControlledCanaryError(f"{path.name} must contain a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("authorization", type=Path)
    parser.add_argument("deployment_receipt", type=Path)
    parser.add_argument("ci_receipt", type=Path)
    parser.add_argument("live_permit", type=Path)
    parser.add_argument("intake_fixture", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "reports/artifacts/gemini_staging/runtime-receipt.json"
        ),
    )
    args = parser.parse_args()
    receipt = run_canary(
        authorization=_load(args.authorization),
        deployment=_load(args.deployment_receipt),
        ci_receipt=_load(args.ci_receipt),
        permit=_load(args.live_permit),
        intake=_load(args.intake_fixture),
        output=args.output,
    )
    print(
        json.dumps(
            {
                "receipt_path": str(args.output),
                "workflow_run_id": receipt["workflow_run_id"],
                "model_api_call_performed": True,
                "external_business_action_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ControlledCanaryError as exc:
        raise SystemExit(f"Controlled Gemini canary blocked: {exc}") from exc
