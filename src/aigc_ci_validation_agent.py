"""Read-only CI observation, evidence normalization, and repair triage for AIGC.

This module never mutates GitHub, edits files, reruns workflows, or makes release decisions.
All release authority remains with the canonical Release Assurance Agent.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

SCHEMA_VERSION = "aigc-ci-observation/1.0"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\\s*[:=]\\s*)[^\\s,;]+"),
    re.compile(r"(?i)(bearer\\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(token|password|secret|api[_-]?key)(\\s*[:=]\\s*)[^\\s,;]+"),
)
MAX_DIAGNOSTIC_LENGTH = 500


def sanitize_diagnostic(value: Any) -> str:
    """Reduce diagnostic text to a bounded, redacted summary."""
    text = str(value or "")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_DIAGNOSTIC_LENGTH]


def normalize_observation(
    *,
    repository: str,
    expected_sha: str,
    run: Mapping[str, Any] | None,
    jobs: list[Mapping[str, Any]] | None,
    artifacts: list[Mapping[str, Any]] | None,
    stage_records: Mapping[str, Any] | None = None,
    independent_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize API observations into a consistent fail-closed evidence record.

    A green status string is never trusted in isolation: run/job/step state, exact
    commit, artifact identity, stage records, and independent review are evaluated
    separately. Artifact metadata is not treated as proof of artifact contents.
    """
    reasons: list[str] = []
    run = run if isinstance(run, Mapping) else {}
    jobs = jobs if isinstance(jobs, list) else []
    artifacts = artifacts if isinstance(artifacts, list) else []
    stage_records = stage_records if isinstance(stage_records, Mapping) else {}

    observed_sha = str(run.get("head_sha", ""))
    run_id = run.get("id")
    run_status = str(run.get("status", "missing"))
    run_conclusion = str(run.get("conclusion", ""))
    if not FULL_SHA.fullmatch(expected_sha):
        reasons.append("invalid_expected_sha")
    if not run:
        reasons.append("workflow_run_missing")
    if observed_sha != expected_sha:
        reasons.append("stale_or_mismatched_commit")
    if run_status != "completed":
        reasons.append("workflow_not_completed")
    if run_conclusion != "success":
        reasons.append("workflow_not_successful")

    normalized_jobs = []
    step_failures = []
    for job in jobs:
        steps = job.get("steps") if isinstance(job.get("steps"), list) else []
        normalized_steps = []
        for step in steps:
            item = {
                "name": sanitize_diagnostic(step.get("name", "")),
                "status": str(step.get("status", "unknown")),
                "conclusion": str(step.get("conclusion", "unknown")),
                "number": step.get("number"),
            }
            normalized_steps.append(item)
            if item["conclusion"] == "failure":
                step_failures.append({"job": sanitize_diagnostic(job.get("name", "")), **item})
        normalized_jobs.append({
            "id": job.get("id"),
            "name": sanitize_diagnostic(job.get("name", "")),
            "status": str(job.get("status", "unknown")),
            "conclusion": str(job.get("conclusion", "unknown")),
            "steps": normalized_steps,
        })
    if not jobs:
        reasons.append("workflow_jobs_missing")
    if step_failures:
        reasons.append("workflow_step_failure")

    matching_artifacts = [
        a for a in artifacts
        if not a.get("expired", False)
        and isinstance(a.get("name"), str)
        and expected_sha in a.get("name", "")
    ]
    if not matching_artifacts:
        reasons.append("exact_head_artifact_missing")
    artifact_summaries = [{
        "id": a.get("id"),
        "name": sanitize_diagnostic(a.get("name", "")),
        "digest": str(a.get("digest", "")),
        "expired": bool(a.get("expired", False)),
        "head_sha": str((a.get("workflow_run") or {}).get("head_sha", "")),
    } for a in artifacts]
    for artifact in matching_artifacts:
        artifact_sha = str((artifact.get("workflow_run") or {}).get("head_sha", ""))
        if artifact_sha != expected_sha:
            reasons.append("artifact_commit_mismatch")

    normalized_stages = []
    for name, record in sorted(stage_records.items()):
        if not isinstance(record, Mapping):
            reasons.append("malformed_stage_record:" + sanitize_diagnostic(name))
            continue
        record_sha = str(record.get("target_sha", ""))
        status = str(record.get("status", "unknown")).lower()
        normalized_stages.append({
            "stage_id": sanitize_diagnostic(name),
            "status": status,
            "target_sha": record_sha,
            "run_id": record.get("run_id"),
            "tested_tree_sha": str(record.get("tested_tree_sha", "")),
            "record_sha256": str(record.get("record_sha256", "")),
        })
        if record_sha != expected_sha:
            reasons.append("stage_commit_mismatch:" + sanitize_diagnostic(name))
        if status not in {"success", "passed", "pass"}:
            reasons.append("stage_not_success:" + sanitize_diagnostic(name))
        # API job failure overrides a stage record that claims success.
        if step_failures and status in {"success", "passed", "pass"}:
            reasons.append("claimed_stage_success_conflicts_with_workflow_failure")

    review_ok = (
        isinstance(independent_review, Mapping)
        and independent_review.get("approved") is True
        and independent_review.get("subject_sha") == expected_sha
        and isinstance(independent_review.get("reviewer_identity"), str)
        and bool(independent_review.get("reviewer_identity", "").strip())
        and independent_review.get("authenticated") is True
    )
    if not review_ok:
        reasons.append("independent_review_missing_or_invalid")

    # Deduplicate but preserve deterministic ordering.
    reasons = sorted(set(reasons))
    decision = "OBSERVATION_COMPLETE" if not reasons else "BLOCK"
    return {
        "schema_version": SCHEMA_VERSION,
        "repository": sanitize_diagnostic(repository),
        "expected_sha": expected_sha,
        "observed_sha": observed_sha,
        "workflow_run_id": run_id,
        "workflow_run_status": run_status,
        "workflow_run_conclusion": run_conclusion,
        "jobs": normalized_jobs,
        "failed_steps": step_failures,
        "artifacts": artifact_summaries,
        "stages": normalized_stages,
        "independent_review_valid": review_ok,
        "decision": decision,
        "reasons": reasons,
        "release_decision": "BLOCK",
        "production_authority": False,
        "merge_authority": False,
        "deployment_authority": False,
        "automatic_changes_performed": False,
    }


def diagnose_failure(observation: Mapping[str, Any], diagnostic_text: str = "") -> dict[str, Any]:
    """Offer minimal, non-executing repair proposals from observable signals."""
    reasons = set(observation.get("reasons", [])) if isinstance(observation, Mapping) else set()
    failed_steps = observation.get("failed_steps", []) if isinstance(observation, Mapping) else []
    text = sanitize_diagnostic(diagnostic_text).lower()
    proposals = []
    if "ModuleNotFoundError" in diagnostic_text or "module not found" in text:
        proposals.append({
            "category": "python_import_path",
            "proposal": "Verify package layout and test import path; prefer explicit src-layout configuration or a scoped PYTHONPATH=src for the affected test invocation.",
            "protected_controls_changed": False,
            "approval_required": True,
        })
    elif "pip check" in text or "dependency conflict" in text:
        proposals.append({
            "category": "dependency_integrity",
            "proposal": "Inspect the declared requirement constraints and resolver output; propose the smallest compatible version-constraint correction without removing the dependency gate.",
            "protected_controls_changed": False,
            "approval_required": True,
        })
    elif "redaction" in text or "secret scan" in text:
        proposals.append({
            "category": "secret_scanning",
            "proposal": "Inspect the specific flagged source text and revise benign wording or remove the actual secret; do not weaken or bypass the scanner.",
            "protected_controls_changed": False,
            "approval_required": True,
        })
    elif failed_steps:
        proposals.append({
            "category": "failed_workflow_step",
            "proposal": "Inspect the named failed step's sanitized logs and reproduce it in an isolated checkout of the exact SHA before proposing a minimal patch.",
            "protected_controls_changed": False,
            "approval_required": True,
        })
    else:
        proposals.append({
            "category": "insufficient_diagnostic_evidence",
            "proposal": "Collect the missing run/job/step/artifact evidence before proposing a patch; make no repository changes.",
            "protected_controls_changed": False,
            "approval_required": True,
        })
    return {
        "schema_version": "aigc-ci-repair-proposal/1.0",
        "classification": proposals[0]["category"],
        "sanitized_diagnostic": sanitize_diagnostic(diagnostic_text),
        "proposals": proposals,
        "automatic_changes_performed": False,
        "release_decision": "BLOCK",
    }
