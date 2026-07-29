from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIAGNOSIS_PATH = PROJECT_ROOT / "config" / "github_actions_zero_step_diagnosis.json"
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "artifacts"
    / "governance"
    / "github-actions-zero-step-live-diagnosis.json"
)
DEFAULT_REPOSITORY = "Lornt1666/AIGC"
DEFAULT_RUN_ID = 29556582162
DEFAULT_JOB_ID = 87809827885
API_ROOT = "https://api.github.com"
STATUS_URL = "https://www.githubstatus.com/api/v2/status.json"


class PreflightError(RuntimeError):
    """Raised when the read-only diagnostic cannot collect required evidence."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PreflightError(f"Expected JSON object at {path}")
    return payload


def write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def _request_json(
    url: str,
    *,
    token: str | None = None,
    optional: bool = False,
) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AIGC-GitHub-Actions-Preflight/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            if not isinstance(payload, dict):
                return {"value": payload, "http_status": response.status}
            return {**payload, "http_status": response.status}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        error_payload: dict[str, Any] = {
            "http_status": exc.code,
            "error": "HTTPError",
            "message": body[:2000],
        }
        if optional:
            return error_payload
        raise PreflightError(f"GET {url} failed with HTTP {exc.code}: {body[:500]}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        if optional:
            return {
                "http_status": None,
                "error": type(exc).__name__,
                "message": str(exc)[:1000],
            }
        raise PreflightError(f"GET {url} failed: {exc}") from exc


def _api_get(
    repository: str,
    suffix: str,
    *,
    token: str,
    optional: bool = False,
) -> dict[str, Any]:
    return _request_json(
        f"{API_ROOT}/repos/{repository}{suffix}",
        token=token,
        optional=optional,
    )


def _annotation_text(annotations: Mapping[str, Any]) -> str:
    values = annotations.get("value")
    if not isinstance(values, list):
        return ""
    fragments: list[str] = []
    for item in values:
        if not isinstance(item, Mapping):
            continue
        for key in ("title", "message", "raw_details"):
            value = str(item.get(key) or "").strip()
            if value:
                fragments.append(value)
    return "\n".join(fragments)


def classify_live_snapshot(
    *,
    permissions: Mapping[str, Any],
    selected_actions: Mapping[str, Any],
    job: Mapping[str, Any],
    annotations: Mapping[str, Any],
    status: Mapping[str, Any],
) -> dict[str, Any]:
    text = _annotation_text(annotations).lower()
    status_description = str(
        ((status.get("status") or {}) if isinstance(status.get("status"), Mapping) else {}).get(
            "description"
        )
        or ""
    ).lower()
    steps = job.get("steps")
    step_count = len(steps) if isinstance(steps, list) else 0
    enabled = permissions.get("enabled")
    allowed_actions = str(permissions.get("allowed_actions") or "unknown")

    if enabled is False:
        classification = "REPOSITORY_ACTIONS_DISABLED"
        confidence = "high"
    elif any(term in text for term in ("billing", "payment", "spending", "budget", "minute")):
        classification = "ACCOUNT_BILLING_OR_USAGE_BLOCK"
        confidence = "high"
    elif any(term in text for term in ("not allowed", "not permitted", "policy")):
        classification = "ACTIONS_POLICY_BLOCK"
        confidence = "high"
    elif step_count == 0 and "operational" in status_description:
        classification = "HOSTED_RUNNER_NOT_ALLOCATED_ACCOUNT_OR_REPOSITORY_ELIGIBILITY_BLOCK"
        confidence = "high"
    elif step_count == 0:
        classification = "HOSTED_RUNNER_NOT_ALLOCATED_PLATFORM_OR_ACCOUNT_BLOCK"
        confidence = "medium"
    else:
        classification = "WORKFLOW_EXECUTION_REACHED_RUNNER"
        confidence = "high"

    return {
        "classification": classification,
        "confidence": confidence,
        "repository_actions_enabled": enabled,
        "allowed_actions": allowed_actions,
        "selected_actions_snapshot_available": selected_actions.get("http_status") == 200,
        "step_count": step_count,
        "annotation_text_present": bool(text),
        "github_status_description": status_description or "unknown",
        "external_action_performed": False,
    }


def collect(
    *,
    repository: str,
    run_id: int,
    job_id: int,
    diagnosis_path: str | Path = DEFAULT_DIAGNOSIS_PATH,
    token: str,
) -> dict[str, Any]:
    diagnosis = deepcopy(load_json(diagnosis_path))

    repository_snapshot = _api_get(repository, "", token=token)
    permissions = _api_get(repository, "/actions/permissions", token=token)
    workflow_permissions = _api_get(
        repository,
        "/actions/permissions/workflow",
        token=token,
        optional=True,
    )
    selected_actions = _api_get(
        repository,
        "/actions/permissions/selected-actions",
        token=token,
        optional=True,
    )
    run = _api_get(repository, f"/actions/runs/{run_id}", token=token)
    jobs = _api_get(
        repository,
        f"/actions/runs/{run_id}/jobs?filter=latest&per_page=100",
        token=token,
    )
    artifacts = _api_get(repository, f"/actions/runs/{run_id}/artifacts", token=token)
    annotations = _api_get(
        repository,
        f"/check-runs/{job_id}/annotations",
        token=token,
        optional=True,
    )
    status = _request_json(STATUS_URL, optional=True)

    job_items = jobs.get("jobs")
    job = next(
        (
            dict(item)
            for item in job_items
            if isinstance(item, Mapping) and int(item.get("id", -1)) == job_id
        ),
        {},
    ) if isinstance(job_items, list) else {}

    classification = classify_live_snapshot(
        permissions=permissions,
        selected_actions=selected_actions,
        job=job,
        annotations=annotations,
        status=status,
    )

    diagnosis["live_snapshot"] = {
        "collected_at": utc_now(),
        "repository": {
            "full_name": repository_snapshot.get("full_name"),
            "private": repository_snapshot.get("private"),
            "archived": repository_snapshot.get("archived"),
            "disabled": repository_snapshot.get("disabled"),
            "visibility": repository_snapshot.get("visibility"),
        },
        "actions_permissions": permissions,
        "workflow_permissions": workflow_permissions,
        "selected_actions": selected_actions,
        "run": {
            "id": run.get("id"),
            "name": run.get("name"),
            "event": run.get("event"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "head_sha": run.get("head_sha"),
            "run_attempt": run.get("run_attempt"),
        },
        "job": {
            "id": job.get("id"),
            "name": job.get("name"),
            "status": job.get("status"),
            "conclusion": job.get("conclusion"),
            "steps": job.get("steps") or [],
        },
        "artifacts": {
            "total_count": artifacts.get("total_count", 0),
            "names": [
                str(item.get("name"))
                for item in artifacts.get("artifacts") or []
                if isinstance(item, Mapping)
            ],
        },
        "annotations": annotations,
        "github_status": status,
        "classification": classification,
        "token_recorded": False,
        "external_action_performed": False,
    }
    diagnosis["observed_at"] = utc_now()
    diagnosis["external_action_performed"] = False
    return diagnosis


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect read-only GitHub Actions permissions, run, job, annotation and status evidence"
    )
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--run-id", type=int, default=DEFAULT_RUN_ID)
    parser.add_argument("--job-id", type=int, default=DEFAULT_JOB_ID)
    parser.add_argument("--diagnosis", default=str(DEFAULT_DIAGNOSIS_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    args = parser.parse_args()

    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if not token:
        raise PreflightError(
            "Set GH_TOKEN or GITHUB_TOKEN to a token with repository Administration: read and Actions: read. "
            "The token is used only for GET requests and is never written to output."
        )

    result = collect(
        repository=args.repository,
        run_id=args.run_id,
        job_id=args.job_id,
        diagnosis_path=args.diagnosis,
        token=token,
    )
    output = write_json(args.output, result)
    print(json.dumps({
        "status": "collected",
        "output": str(output),
        "classification": result["live_snapshot"]["classification"],
        "token_recorded": False,
        "external_action_performed": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
