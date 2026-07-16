from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
REMEDIATION_SCHEMA = (
    ROOT / "schemas" / "github_actions_account_remediation_receipt.schema.json"
)
RECOVERY_SCHEMA = (
    ROOT / "schemas" / "github_actions_hosted_recovery_verification.schema.json"
)

REPOSITORY = "Lornt1666/AIGC"
ISSUE_NUMBER = 124
PULL_REQUEST_NUMBER = 123

REQUIRED_WORKFLOW_STEPS = (
    "Checkout",
    "Set up Python",
    "Set up Terraform",
    "Install dependencies",
    "Validate contracts",
    "Validate provider discovery kit contracts",
    "Validate AEC-001 constitutional substrate",
    "Scan committed content for secret-like content",
    "Run procurement smoke stages",
    "Run provider discovery mock-only smoke",
    "Upload provider discovery simulation",
    "Validate inert Terraform staging foundation",
    "Upload Terraform validation evidence",
    "Run tests",
    "Upload test evidence",
    "Evaluate production readiness evidence",
    "Upload production readiness receipt",
)

REQUIRED_ARTIFACT_PREFIXES = {
    "provider_discovery_artifact_present": "provider-discovery-simulation-",
    "terraform_artifact_present": "terraform-validation-",
    "test_artifact_present": "test-results-",
    "readiness_artifact_present": "production-readiness-",
}

PLACEHOLDER_VALUES = {
    "",
    "tbd",
    "todo",
    "unknown",
    "pending",
    "n/a",
    "none",
    "not supplied",
    "placeholder",
}

CARD_NUMBER_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){12,19}(?!\d)")
SENSITIVE_BILLING_TERMS = re.compile(
    r"\b(?:cvv|cvc|card\s*number|security\s*code|bank\s*account|routing\s*number)\b",
    flags=re.IGNORECASE,
)
HEX40 = re.compile(r"^[a-f0-9]{40}$")


class GitHubActionsRemediationError(ValueError):
    """Raised when account-remediation or hosted-recovery evidence is invalid."""


def utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def utc_now() -> str:
    return utc().isoformat()


def parse_time(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise GitHubActionsRemediationError(f"Invalid date-time: {value!r}") from exc
    return utc(parsed)


def load_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GitHubActionsRemediationError(
            f"Unable to load JSON object: {resolved}"
        ) from exc
    if not isinstance(value, dict):
        raise GitHubActionsRemediationError(f"Expected JSON object: {resolved}")
    return value


def canonical_digest(value: Mapping[str, Any]) -> str:
    material = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256(material.encode("utf-8")).hexdigest()


def validate_schema(
    schema_path: str | Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(dict(value)),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        messages: list[str] = []
        for error in errors[:12]:
            location = "$"
            if error.absolute_path:
                location += "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error.absolute_path
                )
            messages.append(f"{location}: {error.message}")
        raise GitHubActionsRemediationError(
            "Contract validation failed: " + "; ".join(messages)
        )
    return dict(value)


def _run_git(
    args: Sequence[str],
    *,
    project_root: str | Path = ROOT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=Path(project_root),
            check=check,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GitHubActionsRemediationError(
            "Unable to inspect the local Git repository"
        ) from exc


def exact_git_revision(project_root: str | Path = ROOT) -> str:
    completed = _run_git(["rev-parse", "HEAD"], project_root=project_root)
    revision = completed.stdout.strip()
    if not HEX40.fullmatch(revision):
        raise GitHubActionsRemediationError(
            "Repository revision is not an exact lowercase 40-character SHA"
        )
    return revision


def git_branch(project_root: str | Path = ROOT) -> str:
    completed = _run_git(["branch", "--show-current"], project_root=project_root)
    branch = completed.stdout.strip()
    return branch or "DETACHED_HEAD"


def git_repository_clean(project_root: str | Path = ROOT) -> bool:
    completed = _run_git(
        ["status", "--porcelain=v1", "--untracked-files=all"],
        project_root=project_root,
    )
    return not completed.stdout.strip()


def git_is_ancestor(
    ancestor: str,
    descendant: str,
    *,
    project_root: str | Path = ROOT,
) -> bool:
    if not HEX40.fullmatch(ancestor) or not HEX40.fullmatch(descendant):
        raise GitHubActionsRemediationError(
            "Git ancestry checks require exact lowercase 40-character SHAs"
        )
    completed = _run_git(
        ["merge-base", "--is-ancestor", ancestor, descendant],
        project_root=project_root,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        raise GitHubActionsRemediationError("Unable to determine Git ancestry")
    return completed.returncode == 0


def remediation_attestation(operator_name: str) -> str:
    return (
        f"I, {operator_name.strip()}, attest that I performed the GitHub account "
        "or organization remediation described in this receipt. This attestation "
        "does not approve PR #123, replace hosted CI, authorize merge, authorize "
        "Terraform apply, authorize provider mutation, or authorize any external action."
    )


def _is_placeholder(value: str) -> bool:
    normalized = " ".join(value.strip().lower().split())
    return (
        normalized in PLACEHOLDER_VALUES
        or "<" in value
        or ">" in value
        or "${" in value
    )


def _reject_sensitive_billing_text(*values: str) -> None:
    text = "\n".join(values)
    if CARD_NUMBER_PATTERN.search(text) or SENSITIVE_BILLING_TERMS.search(text):
        raise GitHubActionsRemediationError(
            "Do not place card numbers, security codes, bank details, or raw payment data "
            "in the remediation receipt"
        )


def _receipt_id(prefix: str, material: Mapping[str, Any]) -> str:
    return f"{prefix}-{canonical_digest(material)[:24].upper()}"


def build_account_remediation_receipt(
    *,
    exact_head: str,
    tooling_revision: str,
    tooling_branch: str,
    tooling_repository_clean: bool,
    target_is_ancestor_of_tooling_revision: bool,
    operator_name: str,
    observed_banner: str,
    restriction_category: str,
    remediation_summary: str,
    billing_ui_evidence_reference: str,
    remediation_completed_at: datetime,
    hosted_rerun_id: int | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    completed = utc(remediation_completed_at)
    created = utc(created_at)
    if completed > created + timedelta(minutes=5):
        raise GitHubActionsRemediationError(
            "remediation_completed_at cannot be materially later than receipt creation"
        )
    if not HEX40.fullmatch(exact_head):
        raise GitHubActionsRemediationError("exact_head must be an exact Git SHA")
    if not HEX40.fullmatch(tooling_revision):
        raise GitHubActionsRemediationError(
            "tooling_revision must be an exact Git SHA"
        )
    tooling_branch = tooling_branch.strip()
    if not tooling_branch:
        raise GitHubActionsRemediationError("tooling_branch is required")
    if tooling_repository_clean is not True:
        raise GitHubActionsRemediationError(
            "The remediation tooling checkout must be clean"
        )
    if target_is_ancestor_of_tooling_revision is not True:
        raise GitHubActionsRemediationError(
            "The target PR head must be an ancestor of the remediation tooling revision"
        )

    operator_name = operator_name.strip()
    observed_banner = observed_banner.strip()
    remediation_summary = remediation_summary.strip()
    evidence_reference = billing_ui_evidence_reference.strip()
    for label, value in (
        ("operator_name", operator_name),
        ("observed_banner", observed_banner),
        ("remediation_summary", remediation_summary),
        ("billing_ui_evidence_reference", evidence_reference),
    ):
        if _is_placeholder(value):
            raise GitHubActionsRemediationError(
                f"{label} must contain an actual observed value, not a placeholder"
            )
    _reject_sensitive_billing_text(
        observed_banner,
        remediation_summary,
        evidence_reference,
    )

    rerun_requested = hosted_rerun_id is not None
    material = {
        "repository": REPOSITORY,
        "issue_number": ISSUE_NUMBER,
        "pull_request_number": PULL_REQUEST_NUMBER,
        "exact_head": exact_head,
        "tooling_revision": tooling_revision,
        "tooling_branch": tooling_branch,
        "tooling_repository_clean": True,
        "operator_name": operator_name,
        "restriction_category": restriction_category,
        "remediation_completed_at": completed.isoformat(),
        "hosted_rerun_id": hosted_rerun_id,
        "created_at": created.isoformat(),
    }
    receipt = {
        "contract_id": "AIGC-GITHUB-ACTIONS-ACCOUNT-REMEDIATION-001",
        "contract_version": "1.2.0",
        "receipt_id": _receipt_id("GAR", material),
        "repository": REPOSITORY,
        "issue_number": ISSUE_NUMBER,
        "pull_request_number": PULL_REQUEST_NUMBER,
        "exact_head": exact_head,
        "tooling_revision": tooling_revision,
        "tooling_branch": tooling_branch,
        "tooling_repository_clean": True,
        "target_is_ancestor_of_tooling_revision": True,
        "operator_role": "ACCOUNTABLE_OPERATOR",
        "operator_name": operator_name,
        "observed_banner": observed_banner,
        "restriction_category": restriction_category,
        "remediation_summary": remediation_summary,
        "billing_ui_evidence_reference": evidence_reference,
        "remediation_completed_at": completed.isoformat(),
        "hosted_rerun_requested": rerun_requested,
        "hosted_rerun_id": hosted_rerun_id,
        "attestation": remediation_attestation(operator_name),
        "account_restriction_confirmed": True,
        "raw_payment_details_present": False,
        "raw_secret_values_present": False,
        "operator_review_required": True,
        "hosted_ci_replacement": False,
        "merge_authorized": False,
        "terraform_apply_authorized": False,
        "provider_mutation_authorized": False,
        "external_action_performed": False,
        "created_at": created.isoformat(),
    }
    return validate_account_remediation_receipt(
        receipt,
        expected_head=exact_head,
        evaluated_at=created,
    )


def validate_account_remediation_receipt(
    receipt: Mapping[str, Any],
    *,
    expected_head: str | None = None,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    value = validate_schema(REMEDIATION_SCHEMA, receipt)
    if expected_head and value["exact_head"] != expected_head:
        raise GitHubActionsRemediationError(
            "Account-remediation receipt is bound to a different PR head"
        )
    expected_attestation = remediation_attestation(str(value["operator_name"]))
    if value["attestation"] != expected_attestation:
        raise GitHubActionsRemediationError("Account-remediation attestation mismatch")
    for label in (
        "observed_banner",
        "remediation_summary",
        "billing_ui_evidence_reference",
    ):
        if _is_placeholder(str(value[label])):
            raise GitHubActionsRemediationError(
                f"{label} contains a placeholder rather than observed evidence"
            )
    _reject_sensitive_billing_text(
        str(value["observed_banner"]),
        str(value["remediation_summary"]),
        str(value["billing_ui_evidence_reference"]),
    )
    if value["tooling_repository_clean"] is not True:
        raise GitHubActionsRemediationError(
            "Remediation tooling is not recorded as clean"
        )
    if value["target_is_ancestor_of_tooling_revision"] is not True:
        raise GitHubActionsRemediationError(
            "Remediation tooling is not proven to contain the target PR head"
        )
    completed = parse_time(value["remediation_completed_at"])
    created = parse_time(value["created_at"])
    now = utc(evaluated_at)
    if completed > created + timedelta(minutes=5):
        raise GitHubActionsRemediationError(
            "Remediation completion cannot be later than receipt creation"
        )
    if created > now + timedelta(minutes=5):
        raise GitHubActionsRemediationError("Receipt creation time is in the future")
    return value


def _as_object(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GitHubActionsRemediationError(f"{label} must be a JSON object")
    return dict(value)


def _as_list(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise GitHubActionsRemediationError(f"{label} must be a JSON list")
    return list(value)


def _current_pr_head(pr: Mapping[str, Any]) -> tuple[str, str]:
    head = _as_object(pr.get("head"), label="pull_request.head")
    sha = str(head.get("sha", ""))
    ref = str(head.get("ref", ""))
    if not HEX40.fullmatch(sha) or not ref:
        raise GitHubActionsRemediationError(
            "Pull request does not expose an exact head SHA and branch"
        )
    return sha, ref


def _run_pr_binding_observed(
    run: Mapping[str, Any],
    *,
    expected_head: str,
) -> bool:
    pull_requests = run.get("pull_requests", [])
    if not isinstance(pull_requests, list):
        return False
    for item in pull_requests:
        if not isinstance(item, dict) or item.get("number") != PULL_REQUEST_NUMBER:
            continue
        head = item.get("head", {})
        if isinstance(head, dict) and head.get("sha") == expected_head:
            return True
    return False


def verify_hosted_recovery_observation(
    *,
    remediation_receipt: Mapping[str, Any],
    pull_request: Mapping[str, Any],
    workflow_run: Mapping[str, Any],
    workflow_jobs: Mapping[str, Any] | Sequence[Any],
    workflow_artifacts: Mapping[str, Any] | Sequence[Any],
    expected_head: str,
    verification_tooling_revision: str,
    verification_tooling_branch: str,
    verification_tooling_repository_clean: bool,
    target_is_ancestor_of_verification_tooling_revision: bool,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    remediation = validate_account_remediation_receipt(
        remediation_receipt,
        expected_head=expected_head,
        evaluated_at=evaluated_at,
    )
    if not HEX40.fullmatch(verification_tooling_revision):
        raise GitHubActionsRemediationError(
            "verification_tooling_revision must be an exact Git SHA"
        )
    verification_tooling_branch = verification_tooling_branch.strip()
    if not verification_tooling_branch:
        raise GitHubActionsRemediationError(
            "verification_tooling_branch is required"
        )
    if verification_tooling_repository_clean is not True:
        raise GitHubActionsRemediationError(
            "The hosted-recovery verification tooling checkout must be clean"
        )
    if target_is_ancestor_of_verification_tooling_revision is not True:
        raise GitHubActionsRemediationError(
            "The target PR head must be an ancestor of the verification tooling revision"
        )

    pr = _as_object(pull_request, label="pull_request")
    run = _as_object(workflow_run, label="workflow_run")
    if pr.get("number") != PULL_REQUEST_NUMBER:
        raise GitHubActionsRemediationError("Unexpected pull request number")
    if pr.get("state") != "open":
        raise GitHubActionsRemediationError("PR #123 must remain open during recovery")
    pr_head, pr_branch = _current_pr_head(pr)
    if pr_head != expected_head:
        raise GitHubActionsRemediationError("Current PR head no longer matches expected_head")

    if run.get("id") is None or int(run["id"]) < 1:
        raise GitHubActionsRemediationError("Workflow run ID is missing")
    run_id = int(run["id"])
    if remediation["hosted_rerun_requested"] is True:
        if remediation["hosted_rerun_id"] != run_id:
            raise GitHubActionsRemediationError(
                "Hosted workflow run does not match the GAR-signed rerun ID"
            )
    if run.get("name") != "AIGC CI":
        raise GitHubActionsRemediationError("Unexpected workflow name")
    if run.get("event") != "pull_request":
        raise GitHubActionsRemediationError("Workflow must be a pull_request run")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise GitHubActionsRemediationError(
            "Hosted workflow has not completed successfully"
        )
    if run.get("head_branch") != pr_branch:
        raise GitHubActionsRemediationError("Workflow head branch does not match PR head")

    workflow_head_sha = str(run.get("head_sha", ""))
    merge_commit_sha = str(pr.get("merge_commit_sha", ""))
    allowed_shas = {expected_head}
    if HEX40.fullmatch(merge_commit_sha):
        allowed_shas.add(merge_commit_sha)
    if workflow_head_sha not in allowed_shas:
        raise GitHubActionsRemediationError(
            "Workflow head SHA is not bound to the expected PR candidate"
        )
    if not _run_pr_binding_observed(run, expected_head=expected_head):
        raise GitHubActionsRemediationError(
            "Workflow run does not expose an exact PR #123 head binding"
        )

    started = parse_time(run.get("run_started_at") or run.get("created_at"))
    completed = parse_time(run.get("updated_at"))
    remediation_completed = parse_time(remediation["remediation_completed_at"])
    if started < remediation_completed:
        raise GitHubActionsRemediationError(
            "Workflow run started before the account remediation completed"
        )
    if completed < started:
        raise GitHubActionsRemediationError(
            "Workflow completion time precedes its start time"
        )

    if isinstance(workflow_jobs, dict):
        jobs = _as_list(workflow_jobs.get("jobs", []), label="workflow_jobs.jobs")
    else:
        jobs = _as_list(list(workflow_jobs), label="workflow_jobs")
    validate_job = next(
        (
            dict(item)
            for item in jobs
            if isinstance(item, dict) and item.get("name") == "validate"
        ),
        None,
    )
    if validate_job is None:
        raise GitHubActionsRemediationError("Hosted workflow validate job is missing")
    if (
        validate_job.get("status") != "completed"
        or validate_job.get("conclusion") != "success"
    ):
        raise GitHubActionsRemediationError(
            "Hosted workflow validate job did not complete successfully"
        )
    steps = _as_list(validate_job.get("steps", []), label="validate_job.steps")
    if not steps:
        raise GitHubActionsRemediationError("Hosted workflow contains no executed steps")
    by_name = {
        str(item.get("name")): dict(item)
        for item in steps
        if isinstance(item, dict) and item.get("name")
    }
    required_step_receipts: list[dict[str, str]] = []
    for name in REQUIRED_WORKFLOW_STEPS:
        step = by_name.get(name)
        if step is None:
            raise GitHubActionsRemediationError(f"Required workflow step is missing: {name}")
        if step.get("status") != "completed" or step.get("conclusion") != "success":
            raise GitHubActionsRemediationError(
                f"Required workflow step did not succeed: {name}"
            )
        required_step_receipts.append(
            {
                "name": name,
                "status": "completed",
                "conclusion": "success",
            }
        )

    if isinstance(workflow_artifacts, dict):
        artifacts = _as_list(
            workflow_artifacts.get("artifacts", []),
            label="workflow_artifacts.artifacts",
        )
    else:
        artifacts = _as_list(list(workflow_artifacts), label="workflow_artifacts")
    artifact_names: list[str] = []
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        if item.get("expired") is True:
            continue
        workflow_ref = item.get("workflow_run")
        if isinstance(workflow_ref, dict) and workflow_ref.get("id") not in {
            None,
            run_id,
        }:
            continue
        name = str(item.get("name", ""))
        if name:
            artifact_names.append(name)
    artifact_names = sorted(set(artifact_names))
    artifact_flags = {
        flag: any(name.startswith(prefix) for name in artifact_names)
        for flag, prefix in REQUIRED_ARTIFACT_PREFIXES.items()
    }
    missing_artifacts = [flag for flag, present in artifact_flags.items() if not present]
    if missing_artifacts:
        raise GitHubActionsRemediationError(
            "Hosted workflow evidence artifacts are missing: "
            + ", ".join(missing_artifacts)
        )

    verified = utc(evaluated_at)
    material = {
        "repository": REPOSITORY,
        "pull_request_number": PULL_REQUEST_NUMBER,
        "exact_head": expected_head,
        "verification_tooling_revision": verification_tooling_revision,
        "verification_tooling_repository_clean": True,
        "remediation_receipt_id": remediation["receipt_id"],
        "workflow_run_id": run_id,
        "verified_at": verified.isoformat(),
    }
    receipt = {
        "contract_id": "AIGC-GITHUB-ACTIONS-HOSTED-RECOVERY-VERIFICATION-001",
        "contract_version": "1.2.0",
        "receipt_id": _receipt_id("GHR", material),
        "repository": REPOSITORY,
        "issue_number": ISSUE_NUMBER,
        "pull_request_number": PULL_REQUEST_NUMBER,
        "exact_head": expected_head,
        "verification_tooling_revision": verification_tooling_revision,
        "verification_tooling_branch": verification_tooling_branch,
        "verification_tooling_repository_clean": True,
        "target_is_ancestor_of_verification_tooling_revision": True,
        "remediation_receipt_id": remediation["receipt_id"],
        "remediation_receipt_digest": canonical_digest(remediation),
        "workflow_run_id": run_id,
        "workflow_name": "AIGC CI",
        "workflow_event": "pull_request",
        "workflow_status": "completed",
        "workflow_conclusion": "success",
        "workflow_head_sha": workflow_head_sha,
        "workflow_head_branch": pr_branch,
        "run_started_at": started.isoformat(),
        "run_completed_at": completed.isoformat(),
        "current_pr_head_matches_expected": True,
        "run_pr_binding_observed": True,
        "checkout_executed": True,
        "steps_executed": True,
        "required_steps": required_step_receipts,
        "artifact_names": artifact_names,
        **artifact_flags,
        "github_api_read_performed": True,
        "github_api_mutation_performed": False,
        "verification_mode": "READ_ONLY_GITHUB_API",
        "operator_review_required": True,
        "hosted_ci_replacement": False,
        "merge_authorized": False,
        "terraform_apply_authorized": False,
        "provider_mutation_authorized": False,
        "external_action_performed": False,
        "verified_at": verified.isoformat(),
    }
    return validate_schema(RECOVERY_SCHEMA, receipt)
