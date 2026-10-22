"""Deterministic, fail-closed incident recovery gates for AIGC.

This is a reference policy module, not a GitHub client, human identity provider,
production scheduler, or authorization to execute repairs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import re


GATE_SEQUENCE = (
    "detect_and_preserve",
    "diagnose_and_reproduce",
    "exact_head_evidence",
    "safe_recovery",
    "independent_review_and_remediation",
    "repository_protection_readback",
    "acceptance_and_provenance",
    "operational_readiness_handoff",
)
SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class RecoveryGateError(ValueError):
    """Raised when evidence is incomplete, stale, or fails a recovery gate."""


@dataclass(frozen=True)
class GateDecision:
    status: str
    gate_id: str
    reason: str
    candidate_sha: str
    evidence_digest: str | None = None


def _required_text(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RecoveryGateError(f"missing_or_invalid_{key}")
    return value.strip()


def validate_incident_record(record: Mapping[str, Any], candidate_sha: str) -> dict[str, Any]:
    """Validate an incident record without promoting a hypothesis to root cause."""
    if not isinstance(record, Mapping):
        raise RecoveryGateError("incident_record_must_be_object")
    if not GIT_SHA_RE.fullmatch(candidate_sha or ""):
        raise RecoveryGateError("candidate_sha_invalid")
    source_sha = _required_text(record, "source_commit_sha")
    if not GIT_SHA_RE.fullmatch(source_sha):
        raise RecoveryGateError("source_commit_sha_invalid")
    if source_sha != candidate_sha:
        raise RecoveryGateError("incident_evidence_commit_mismatch")
    for key in ("incident_id", "severity", "failure_signature", "detected_at", "owner"):
        _required_text(record, key)
    refs = record.get("evidence_refs")
    if not isinstance(refs, list) or not refs or any(not isinstance(x, str) or not x.strip() for x in refs):
        raise RecoveryGateError("incident_evidence_refs_missing")
    digest = _required_text(record, "evidence_digest")
    if not SHA256_RE.fullmatch(digest):
        raise RecoveryGateError("incident_evidence_digest_invalid")
    return {
        "status": "VALID",
        "incident_id": record["incident_id"],
        "source_commit_sha": source_sha,
        "evidence_digest": digest if digest.startswith("sha256:") else f"sha256:{digest}",
        "evidence_ref_count": len(refs),
        "root_cause_status": "UNCONFIRMED",
    }


def assess_root_cause(assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Only call a cause confirmed when a referenced reproduction reproduces it."""
    if not isinstance(assessment, Mapping):
        raise RecoveryGateError("root_cause_assessment_must_be_object")
    hypothesis = _required_text(assessment, "hypothesis")
    evidence_refs = assessment.get("supporting_evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        raise RecoveryGateError("root_cause_supporting_evidence_missing")
    reproduction_id = assessment.get("reproduction_id")
    outcome = assessment.get("reproduction_outcome")
    if not isinstance(reproduction_id, str) or not reproduction_id.strip():
        return {"status": "HYPOTHESIS", "hypothesis": hypothesis, "reason": "reproduction_not_supplied"}
    if outcome == "REPRODUCED":
        return {
            "status": "CONFIRMED_BY_REPRODUCTION",
            "hypothesis": hypothesis,
            "reproduction_id": reproduction_id,
            "evidence_refs": list(evidence_refs),
        }
    if outcome == "FALSIFIED":
        return {
            "status": "FALSIFIED",
            "hypothesis": hypothesis,
            "reproduction_id": reproduction_id,
            "evidence_refs": list(evidence_refs),
        }
    return {
        "status": "HYPOTHESIS",
        "hypothesis": hypothesis,
        "reproduction_id": reproduction_id,
        "reason": "reproduction_outcome_not_discriminating",
    }


def validate_exact_head_ci_receipt(receipt: Mapping[str, Any], candidate_sha: str) -> GateDecision:
    """Require a complete successful receipt for the exact candidate commit."""
    if not isinstance(receipt, Mapping):
        raise RecoveryGateError("ci_receipt_must_be_object")
    if not GIT_SHA_RE.fullmatch(candidate_sha or ""):
        raise RecoveryGateError("candidate_sha_invalid")
    observed_sha = _required_text(receipt, "observed_sha")
    if observed_sha != candidate_sha:
        raise RecoveryGateError("ci_receipt_commit_mismatch")
    run_id = receipt.get("workflow_run_id")
    attempt = receipt.get("workflow_run_attempt")
    if not isinstance(run_id, int) or run_id <= 0 or not isinstance(attempt, int) or attempt <= 0:
        raise RecoveryGateError("ci_run_identity_invalid")
    if receipt.get("status") != "completed" or receipt.get("conclusion") != "success":
        return GateDecision("BLOCK", "exact_head_evidence", "workflow_not_successful", candidate_sha)
    required_jobs = receipt.get("required_jobs")
    job_results = receipt.get("job_results")
    if not isinstance(required_jobs, list) or not required_jobs or not isinstance(job_results, Mapping):
        raise RecoveryGateError("required_job_evidence_missing")
    for job in required_jobs:
        if not isinstance(job, str) or not job.strip():
            raise RecoveryGateError("required_job_name_invalid")
        if job_results.get(job) != "success":
            return GateDecision("BLOCK", "exact_head_evidence", f"required_job_not_success:{job}", candidate_sha)
    skipped_stages = receipt.get("skipped_required_stages", [])
    if not isinstance(skipped_stages, list):
        raise RecoveryGateError("skipped_stage_evidence_invalid")
    if skipped_stages:
        return GateDecision("BLOCK", "exact_head_evidence", "required_stage_skipped", candidate_sha)
    failed_tests = receipt.get("failed_or_error_test_count")
    if not isinstance(failed_tests, int) or failed_tests != 0:
        return GateDecision("BLOCK", "exact_head_evidence", "test_failures_or_missing_test_count", candidate_sha)
    artifact_digest = _required_text(receipt, "artifact_digest")
    if not SHA256_RE.fullmatch(artifact_digest):
        raise RecoveryGateError("artifact_digest_invalid")
    evidence_digest = _required_text(receipt, "evidence_digest")
    if not SHA256_RE.fullmatch(evidence_digest):
        raise RecoveryGateError("evidence_digest_invalid")
    return GateDecision(
        "PASS", "exact_head_evidence", "exact_head_ci_and_artifacts_verified",
        candidate_sha, evidence_digest if evidence_digest.startswith("sha256:") else f"sha256:{evidence_digest}",
    )


def side_effect_retry_allowed(outcome: str, reconciliation: str | None = None) -> bool:
    """Never retry an uncertain side effect until explicitly reconciled."""
    if outcome in {"NOT_STARTED", "DEFINITELY_NOT_APPLIED"}:
        return True
    if outcome == "UNKNOWN":
        return reconciliation in {"RECONCILED_NOT_APPLIED", "IDEMPOTENT_REPLAY_PROVEN_SAFE"}
    if outcome in {"SUCCEEDED", "APPLIED"}:
        return False
    return False


def validate_gate_progress(
    gate_id: str,
    candidate_sha: str,
    gate_results: Mapping[str, str],
    evidence_sha: str,
) -> GateDecision:
    """Require ordered prior gates and exact-SHA evidence before advancing."""
    if gate_id not in GATE_SEQUENCE:
        raise RecoveryGateError("unknown_recovery_gate")
    if not GIT_SHA_RE.fullmatch(candidate_sha or "") or evidence_sha != candidate_sha:
        raise RecoveryGateError("gate_evidence_commit_mismatch")
    index = GATE_SEQUENCE.index(gate_id)
    for prior in GATE_SEQUENCE[:index]:
        if gate_results.get(prior) != "PASS":
            return GateDecision("BLOCK", gate_id, f"prior_gate_not_passed:{prior}", candidate_sha)
    if gate_results.get(gate_id) != "PASS":
        return GateDecision("BLOCK", gate_id, "gate_not_passed", candidate_sha)
    return GateDecision("PASS", gate_id, "ordered_gate_evidence_matches_candidate", candidate_sha)
