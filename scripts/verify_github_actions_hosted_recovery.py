from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.github_actions_account_remediation import (  # noqa: E402
    GitHubActionsRemediationError,
    load_json,
    verify_hosted_recovery_observation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read GitHub PR, workflow, job, and artifact metadata through gh api and "
            "issue a fail-closed hosted-recovery verification receipt. This command "
            "performs no GitHub mutation."
        )
    )
    parser.add_argument("--repository", default="Lornt1666/AIGC")
    parser.add_argument("--pr-number", type=int, default=123)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--remediation-receipt", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument(
        "--output",
        default="artifacts/governance/github-actions-hosted-recovery-verification.json",
    )
    parser.add_argument(
        "--observation-output",
        default="artifacts/governance/github-actions-hosted-recovery-observation.json",
    )
    return parser.parse_args()


def gh_api(gh: str, endpoint: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [gh, "api", "--method", "GET", endpoint],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", "") or ""
        raise GitHubActionsRemediationError(
            f"Read-only GitHub API request failed for {endpoint}: {stderr.strip()}"
        ) from exc
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise GitHubActionsRemediationError(
            f"GitHub API returned invalid JSON for {endpoint}"
        ) from exc
    if not isinstance(value, dict):
        raise GitHubActionsRemediationError(
            f"GitHub API response must be an object for {endpoint}"
        )
    return value


def filtered_observation(
    *,
    pull_request: dict[str, Any],
    workflow_run: dict[str, Any],
    workflow_jobs: dict[str, Any],
    workflow_artifacts: dict[str, Any],
) -> dict[str, Any]:
    head = pull_request.get("head") if isinstance(pull_request.get("head"), dict) else {}
    jobs = workflow_jobs.get("jobs") if isinstance(workflow_jobs.get("jobs"), list) else []
    artifacts = (
        workflow_artifacts.get("artifacts")
        if isinstance(workflow_artifacts.get("artifacts"), list)
        else []
    )
    return {
        "contract_id": "AIGC-GITHUB-ACTIONS-HOSTED-RECOVERY-OBSERVATION-001",
        "pull_request": {
            "number": pull_request.get("number"),
            "state": pull_request.get("state"),
            "merge_commit_sha": pull_request.get("merge_commit_sha"),
            "head": {
                "sha": head.get("sha"),
                "ref": head.get("ref"),
            },
        },
        "workflow_run": {
            key: workflow_run.get(key)
            for key in (
                "id",
                "name",
                "event",
                "status",
                "conclusion",
                "head_branch",
                "head_sha",
                "created_at",
                "run_started_at",
                "updated_at",
                "pull_requests",
            )
        },
        "workflow_jobs": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "status": item.get("status"),
                "conclusion": item.get("conclusion"),
                "steps": [
                    {
                        "name": step.get("name"),
                        "status": step.get("status"),
                        "conclusion": step.get("conclusion"),
                    }
                    for step in item.get("steps", [])
                    if isinstance(step, dict)
                ],
            }
            for item in jobs
            if isinstance(item, dict)
        ],
        "workflow_artifacts": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "expired": item.get("expired"),
                "size_in_bytes": item.get("size_in_bytes"),
                "workflow_run": item.get("workflow_run"),
            }
            for item in artifacts
            if isinstance(item, dict)
        ],
        "github_api_read_performed": True,
        "github_api_mutation_performed": False,
        "operator_review_required": True,
        "merge_authorized": False,
        "external_action_performed": False,
    }


def resolve_output(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    args = parse_args()
    if args.repository != "Lornt1666/AIGC":
        raise SystemExit("This contract is bound to Lornt1666/AIGC")
    if args.pr_number != 123:
        raise SystemExit("This recovery contract is bound to PR #123")

    gh = shutil.which("gh")
    if gh is None:
        raise SystemExit("GitHub CLI is required. Install gh and run gh auth login first.")
    try:
        subprocess.run(
            [gh, "auth", "status"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            "GitHub CLI is not authenticated. Run gh auth login with repo and actions read access."
        ) from exc

    repository = args.repository
    pull_request = gh_api(gh, f"repos/{repository}/pulls/{args.pr_number}")
    workflow_run = gh_api(gh, f"repos/{repository}/actions/runs/{args.run_id}")
    workflow_jobs = gh_api(
        gh,
        f"repos/{repository}/actions/runs/{args.run_id}/jobs?filter=latest&per_page=100",
    )
    workflow_artifacts = gh_api(
        gh,
        f"repos/{repository}/actions/runs/{args.run_id}/artifacts?per_page=100",
    )
    remediation_receipt = load_json(args.remediation_receipt)
    if remediation_receipt.get("hosted_rerun_requested") is True:
        signed_run_id = remediation_receipt.get("hosted_rerun_id")
        if signed_run_id != args.run_id:
            raise SystemExit(
                "The GAR receipt is bound to a different hosted rerun ID. "
                "Issue a new remediation receipt for the run being verified."
            )

    observation = filtered_observation(
        pull_request=pull_request,
        workflow_run=workflow_run,
        workflow_jobs=workflow_jobs,
        workflow_artifacts=workflow_artifacts,
    )
    observation_path = resolve_output(args.observation_output)
    observation_path.parent.mkdir(parents=True, exist_ok=True)
    observation_path.write_text(
        json.dumps(observation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    verification = verify_hosted_recovery_observation(
        remediation_receipt=remediation_receipt,
        pull_request=pull_request,
        workflow_run=workflow_run,
        workflow_jobs=workflow_jobs,
        workflow_artifacts=workflow_artifacts,
        expected_head=args.expected_head,
    )
    output = resolve_output(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verification_path": str(output),
                "observation_path": str(observation_path),
                "receipt_id": verification["receipt_id"],
                "workflow_run_id": verification["workflow_run_id"],
                "checkout_executed": True,
                "steps_executed": True,
                "required_artifacts_present": True,
                "merge_authorized": False,
                "terraform_apply_authorized": False,
                "external_action_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
