"""Fail-closed, deterministic evidence closure evaluator for AIGC RX-148.

This is a pure validation layer. It consumes a caller-supplied snapshot and does
not fetch GitHub, authenticate external identities, mutate repository state,
assign reviewers, merge, deploy, or release. Snapshot acquisition/authentication
must be supplied by a separately authorized adapter.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from collections.abc import Mapping
from typing import Any

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_ALLOWED_GATE_STATUSES = {"PASS", "BLOCK", "STALE", "UNVERIFIABLE", "NOT_STARTED"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _gate(gate_id: str, role: str, status: str, evidence: str, acceptance: str,
          reason: str, blockers: list[dict[str, str]]) -> dict[str, str]:
    if status not in _ALLOWED_GATE_STATUSES:
        status, reason = "UNVERIFIABLE", "internal_status_invalid"
    if status != "PASS":
        blockers.append({
            "gate_id": gate_id,
            "status": status,
            "accountable_role": role,
            "required_action": reason,
            "evidence_contract": evidence,
            "acceptance_test": acceptance,
        })
    return {
        "gate_id": gate_id, "status": status, "accountable_role": role,
        "evidence_contract": evidence, "acceptance_test": acceptance, "reason": reason,
    }


def evaluate_closure(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate closure gates against a complete snapshot; fail closed on ambiguity."""
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot_must_be_object")

    blockers: list[dict[str, str]] = []
    candidate = snapshot.get("candidate_sha")
    observed = snapshot.get("observed_head_sha")
    repository = snapshot.get("repository")
    pr_number = snapshot.get("pr_number")
    if not isinstance(repository, str) or not repository.strip():
        raise ValueError("repository_required")
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number < 1:
        raise ValueError("pr_number_invalid")
    if not _is_sha(candidate):
        raise ValueError("candidate_sha_invalid")

    observed_at = snapshot.get("observed_at")
    evaluation_time = snapshot.get("evaluation_time")
    freshness_state = "UNVERIFIABLE"
    if isinstance(observed_at, str) and isinstance(evaluation_time, str):
        try:
            observed_dt = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            evaluated_dt = datetime.fromisoformat(evaluation_time.replace("Z", "+00:00"))
            if observed_dt.tzinfo is not None and evaluated_dt.tzinfo is not None:
                age_seconds = (evaluated_dt - observed_dt).total_seconds()
                freshness_state = "PASS" if 0 <= age_seconds <= 120 else "STALE"
        except ValueError:
            freshness_state = "UNVERIFIABLE"
    if not _is_sha(observed) or snapshot.get("live_observation_authenticated") is not True or freshness_state == "UNVERIFIABLE" or snapshot.get("observation_source") != "github_api":
        g0_status, g0_reason = "UNVERIFIABLE", "authenticated_live_observation_missing_or_invalid"
    elif freshness_state == "STALE":
        g0_status, g0_reason = "STALE", "live_observation_outside_120_second_freshness_window"
    elif snapshot.get("pr_state") != "open" or snapshot.get("pr_merged") is not False:
        g0_status, g0_reason = "STALE", "candidate_PR_is_not_open_and_unmerged"
    elif snapshot.get("head_changed_during_acquisition") is True or observed != candidate:
        g0_status, g0_reason = "STALE", "live_head_or_base_changed_during_acquisition; reacquire_and_revalidate"
    else:
        g0_status, g0_reason = "PASS", "fresh_open_unmerged_PR_head_matches_candidate"

    gates: list[dict[str, str]] = []
    gates.append(_gate("G0_LIVE_RECONCILIATION", "closure-orchestrator", g0_status,
        "authenticated live PR metadata with repository, PR number, head/base SHAs, timestamp and GitHub API source",
        "freshly fetched head SHA equals candidate SHA; observation is complete", g0_reason, blockers))

    required_jobs = snapshot.get("required_ci_jobs")
    runs = snapshot.get("ci_runs")
    ci_status, ci_reason = "BLOCK", "required_ci_evidence_missing_or_invalid"
    if not isinstance(required_jobs, list) or not required_jobs or any(not isinstance(x, str) or not x for x in required_jobs):
        ci_status, ci_reason = "UNVERIFIABLE", "required_ci_job_policy_missing_or_invalid"
    elif not isinstance(runs, list):
        ci_status, ci_reason = "UNVERIFIABLE", "ci_run_collection_missing_or_invalid"
    elif observed != candidate:
        ci_status, ci_reason = "STALE", "live_head_mismatch_invalidates_ci"
    else:
        valid_runs = [
            run for run in runs
            if isinstance(run, Mapping)
            and run.get("head_sha") == candidate
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and isinstance(run.get("run_id"), int)
            and isinstance(run.get("run_attempt"), int)
            and run.get("run_attempt", 0) >= 1
            and isinstance(run.get("jobs"), list)
        ]
        failures_by_run = []
        for run in valid_runs:
            by_job: dict[str, list[Mapping[str, Any]]] = {}
            for job in run["jobs"]:
                if isinstance(job, Mapping) and isinstance(job.get("name"), str):
                    by_job.setdefault(job["name"], []).append(job)
            failures = []
            for name in sorted(set(required_jobs)):
                candidates = by_job.get(name, [])
                if not candidates:
                    failures.append(name + ":missing")
                elif not any(j.get("conclusion") == "success" and j.get("head_sha", candidate) == candidate for j in candidates):
                    failures.append(name + ":not_success")
            if not failures:
                failures_by_run.append(run)
            else:
                failures_by_run.append({**run, "_required_job_failures": failures})
        passing_runs = [r for r in failures_by_run if "_required_job_failures" not in r]
        if passing_runs:
            ci_status, ci_reason = "PASS", "all_required_jobs_success_for_exact_head_in_one_completed_run_attempt"
        elif not valid_runs:
            ci_status, ci_reason = "BLOCK", "no_completed_successful_run_attempt_for_exact_head"
        else:
            failures = sorted({f for run in failures_by_run for f in run.get("_required_job_failures", [])})
            ci_status, ci_reason = "BLOCK", "required_jobs_missing_skipped_failed_or_not_successful:" + ",".join(failures)
    gates.append(_gate("G1_EXACT_HEAD_CI", "engineering/CI owner", ci_status,
        "complete workflow/run-attempt/job inventory with run IDs, attempts, exact head SHA and required job names",
        "every policy-required job has a successful completed result for the current candidate; no missing or skipped required job",
        ci_reason, blockers))

    artifact = snapshot.get("artifact")
    artifact_status, artifact_reason = "BLOCK", "artifact_evidence_missing_or_invalid"
    if not isinstance(artifact, Mapping):
        artifact_status, artifact_reason = "UNVERIFIABLE", "artifact_manifest_missing"
    elif observed != candidate:
        artifact_status, artifact_reason = "STALE", "live_head_mismatch_invalidates_artifact_binding"
    elif artifact.get("head_sha") != candidate or not _is_digest(artifact.get("sha256")) or not isinstance(artifact.get("run_id"), int) or not isinstance(artifact.get("run_attempt"), int) or not isinstance(artifact.get("files"), list) or not artifact.get("files"):
        artifact_status, artifact_reason = "BLOCK", "artifact_sha_digest_run_attempt_or_file_manifest_mismatch"
    elif artifact.get("bytes_verified") is not True or artifact.get("manifest_verified") is not True:
        artifact_status, artifact_reason = "UNVERIFIABLE", "trusted_adapter_has_not_verified_downloaded_bytes_and_file_manifest"
    elif not all(isinstance(f, Mapping) and isinstance(f.get("path"), str) and _is_digest(f.get("sha256")) and isinstance(f.get("size"), int) and f.get("size", -1) >= 0 for f in artifact["files"]):
        artifact_status, artifact_reason = "BLOCK", "artifact_file_manifest_malformed"
    elif len({f["path"] for f in artifact["files"]}) != len(artifact["files"]):
        artifact_status, artifact_reason = "BLOCK", "artifact_file_manifest_duplicate_paths"
    elif not any(isinstance(run, Mapping) and run.get("run_id") == artifact.get("run_id") and run.get("run_attempt") == artifact.get("run_attempt") and run.get("head_sha") == candidate and run.get("status") == "completed" and run.get("conclusion") == "success" for run in (runs if isinstance(runs, list) else [])):
        artifact_status, artifact_reason = "BLOCK", "artifact_run_attempt_does_not_match_successful_exact_head_ci"
    else:
        artifact_status, artifact_reason = "PASS", "artifact_manifest_well_formed_and_bound_to_candidate_and_ci_attempt"
    gates.append(_gate("G2_ARTIFACT_INTEGRITY", "engineering/evidence owner", artifact_status,
        "artifact SHA-256, file manifest, sizes, source SHA, workflow run ID and attempt",
        "recomputed digest and file inventory match trusted downloaded bytes and exact-head run",
        artifact_reason, blockers))

    protection = snapshot.get("protection")
    pstatus, preason = "BLOCK", "effective_protection_not_verified"
    if not isinstance(protection, Mapping):
        pstatus, preason = "UNVERIFIABLE", "authenticated_admin_protection_readback_missing"
    elif protection.get("authenticated") is not True or protection.get("status") != "VERIFIED" or protection.get("base_branch") != snapshot.get("base_branch") or not isinstance(protection.get("release_branch"), str) or not protection.get("release_branch") or not _is_digest(protection.get("readback_digest")):
        pstatus, preason = "UNVERIFIABLE", "protection_readback_unauthenticated_incomplete_or_branch_mismatched"
    else:
        pstatus, preason = "PASS", "authenticated_effective_protection_readback_matches_expected_base_and_release_branches"
    gates.append(_gate("G3_EFFECTIVE_PROTECTION", "authorized repository administrator", pstatus,
        "authenticated readback of effective protections for PR base and release branches, including required checks/reviews and bypass actors",
        "authorized readback digest validates and required controls demonstrably apply to both target branches",
        preason, blockers))

    review = snapshot.get("review")
    rstatus, rreason = "BLOCK", "qualified_independent_review_missing"
    if not isinstance(review, Mapping):
        rstatus, rreason = "UNVERIFIABLE", "review_evidence_missing"
    elif review.get("authenticated") is not True or review.get("qualified_independent") is not True or review.get("reviewed_sha") != candidate or review.get("findings_closed_with_retest") is not True or review.get("review_threads_verified") is not True or not isinstance(review.get("review_id"), str) or not review.get("review_id"):
        rstatus, rreason = "BLOCK", "review_unauthenticated_nonindependent_stale_or_findings_not_retested"
    else:
        rstatus, rreason = "PASS", "independent_review_and_retest_bound_to_candidate"
    gates.append(_gate("G4_INDEPENDENT_REVIEW", "authorized repository administrator + independent reviewer", rstatus,
        "authorized reviewer assignment, qualification/conflict/independence evidence, review ID, exact SHA, findings and independent retest receipts",
        "qualified independent reviewer reviewed exact candidate and every finding has evidence-backed closure/retest",
        rreason, blockers))

    provenance = snapshot.get("provenance")
    prstatus, prreason = "BLOCK", "trusted_provenance_missing"
    if not isinstance(provenance, Mapping):
        prstatus, prreason = "UNVERIFIABLE", "provenance_receipt_missing"
    elif provenance.get("verified") is not True or provenance.get("authenticated") is not True or provenance.get("repository") != repository or provenance.get("source_sha") != candidate or not _is_digest(provenance.get("subject_digest")) or not isinstance(provenance.get("workflow_identity"), str) or not provenance.get("workflow_identity") or not isinstance(provenance.get("issuer"), str) or not provenance.get("issuer") or not isinstance(artifact, Mapping) or provenance.get("subject_digest") not in {artifact.get("sha256"), "sha256:" + str(artifact.get("sha256", "")).removeprefix("sha256:")}:
        prstatus, prreason = "BLOCK", "provenance_signature_or_repository_workflow_source_subject_claims_invalid"
    else:
        prstatus, prreason = "PASS", "trusted_provenance_claims_verified"
    gates.append(_gate("G5_TRUSTED_PROVENANCE", "engineering/security owner", prstatus,
        "authenticated signature/issuer verification receipt with repository, workflow identity, source SHA and subject digest",
        "trusted verifier confirms expected repository, workflow, issuer, source SHA, predicate and artifact subject digest",
        prreason, blockers))

    acceptance = snapshot.get("acceptance")
    evidence_digest = snapshot.get("evidence_digest")
    policy_version = snapshot.get("policy_version")
    astatus, areason = "BLOCK", "authenticated_human_acceptance_missing"
    if not _is_digest(evidence_digest) or not isinstance(policy_version, str) or not policy_version.strip():
        astatus, areason = "UNVERIFIABLE", "canonical_evidence_digest_or_policy_version_missing_or_invalid"
    elif not isinstance(acceptance, Mapping):
        astatus, areason = "UNVERIFIABLE", "acceptance_receipt_missing"
    elif acceptance.get("authenticated") is not True or acceptance.get("approver_role") != "authorized_human_approver" or acceptance.get("candidate_sha") != candidate or acceptance.get("evidence_digest") != evidence_digest or acceptance.get("policy_version") != policy_version or not isinstance(acceptance.get("receipt_id"), str) or not acceptance.get("receipt_id"):
        astatus, areason = "BLOCK", "acceptance_unauthenticated_or_sha_digest_role_mismatch"
    else:
        astatus, areason = "PASS", "authenticated_human_acceptance_matches_candidate_and_packet"
    gates.append(_gate("G6_HUMAN_ACCEPTANCE", "authorized human approver", astatus,
        "authenticated approval receipt, authorized role, candidate SHA, policy version and canonical evidence digest",
        "approval identity/authority validates and receipt binds exact candidate and evidence digest",
        areason, blockers))

    handoff = snapshot.get("rx19_handoff")
    hstatus, hreason = "BLOCK", "HANDOFF_INTERFACE_MISSING"
    if not isinstance(handoff, Mapping):
        hstatus, hreason = "UNVERIFIABLE", "HANDOFF_INTERFACE_MISSING"
    elif handoff.get("authenticated") is not True or handoff.get("recipient") != "RX-19" or handoff.get("candidate_sha") != candidate or handoff.get("evidence_digest") != evidence_digest or not isinstance(handoff.get("receipt_id"), str) or not handoff.get("receipt_id"):
        hstatus, hreason = "BLOCK", "rx19_handoff_receipt_missing_unauthenticated_or_payload_mismatch"
    else:
        hstatus, hreason = "PASS", "authenticated_rx19_receipt_matches_exact_packet"
    gates.append(_gate("G7_RX19_HANDOFF", "release engineering / RX-144 coordinator", hstatus,
        "verified RX-19 interface contract and authenticated receipt for exact candidate SHA and packet digest",
        "receipt proves intended RX-19 recipient and exact payload binding; no inferred endpoint",
        hreason, blockers))

    decision = snapshot.get("rx19_decision")
    dstatus, dreason = "BLOCK", "RX-19 sole release decision missing"
    if not isinstance(decision, Mapping):
        dstatus, dreason = "UNVERIFIABLE", "authenticated_RX-19_decision_missing"
    elif decision.get("authenticated") is not True or decision.get("authority") != "RX-19" or decision.get("decision") != "APPROVE" or decision.get("candidate_sha") != candidate or decision.get("evidence_digest") != evidence_digest or not isinstance(decision.get("receipt_id"), str) or not decision.get("receipt_id"):
        dstatus, dreason = "BLOCK", "RX19_decision_unauthenticated_or_candidate_packet_authority_mismatch"
    else:
        dstatus, dreason = "PASS", "authenticated_RX19_decision_matches_candidate_and_packet"
    gates.append(_gate("G8_RX19_DECISION", "RX-19 sole release decision authority", dstatus,
        "authenticated RX-19 decision receipt bound to candidate SHA and evidence digest",
        "only RX-19 issued an authenticated APPROVE decision for this exact candidate and packet",
        dreason, blockers))

    dependencies = {
        "G0_LIVE_RECONCILIATION": [],
        "G1_EXACT_HEAD_CI": ["G0_LIVE_RECONCILIATION"],
        "G2_ARTIFACT_INTEGRITY": ["G0_LIVE_RECONCILIATION", "G1_EXACT_HEAD_CI"],
        "G3_EFFECTIVE_PROTECTION": [],
        "G4_INDEPENDENT_REVIEW": ["G0_LIVE_RECONCILIATION"],
        "G5_TRUSTED_PROVENANCE": ["G1_EXACT_HEAD_CI", "G2_ARTIFACT_INTEGRITY"],
        "G6_HUMAN_ACCEPTANCE": ["G0_LIVE_RECONCILIATION", "G2_ARTIFACT_INTEGRITY", "G4_INDEPENDENT_REVIEW", "G5_TRUSTED_PROVENANCE"],
        "G7_RX19_HANDOFF": ["G6_HUMAN_ACCEPTANCE"],
        "G8_RX19_DECISION": ["G7_RX19_HANDOFF"],
    }
    by_gate = {g["gate_id"]: g for g in gates}
    for gate in gates:
        gate["depends_on"] = dependencies[gate["gate_id"]]
        blocked_dependencies = [dep for dep in dependencies[gate["gate_id"]] if by_gate[dep]["status"] != "PASS"]
        gate["dependency_blocked"] = bool(blocked_dependencies)
        if blocked_dependencies and gate["status"] == "PASS":
            gate["status"] = "STALE"
            gate["reason"] = "dependency_not_passed:" + ",".join(blocked_dependencies)
    blockers = [{
        "gate_id": g["gate_id"], "status": g["status"], "accountable_role": g["accountable_role"],
        "required_action": g["reason"], "evidence_contract": g["evidence_contract"],
        "acceptance_test": g["acceptance_test"],
    } for g in gates if g["status"] != "PASS"]
    gates.sort(key=lambda g: g["gate_id"])
    blockers.sort(key=lambda b: (b["gate_id"], b["required_action"]))
    body = {
        "schema_version": "rx148.closure.v1",
        "repository": repository,
        "pr_number": pr_number,
        "candidate_sha": candidate,
        "observed_head_sha": observed,
        "base_branch": snapshot.get("base_branch"),
        "base_sha": snapshot.get("base_sha"),
        "gate_results": gates,
        "blockers": blockers,
        "release_authority": "RX-19",
        "coordinator_authority": "RX-144_COORDINATION_ONLY",
        "merge_authorization": False,
        "deployment_authorization": False,
        "release_authorization": False,
    }
    body["disposition"] = "RX19_APPROVED_EVIDENCE_ONLY_NO_ACTION" if all(g["status"] == "PASS" for g in gates) else "BLOCK"
    body["manifest_digest"] = _digest(body)
    return body
