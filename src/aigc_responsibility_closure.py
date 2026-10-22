"""Fail-closed, evidence-driven release closure workflow for AIGC.

This module evaluates supplied snapshots and receipts. It does not query GitHub,
authenticate signatures, assign humans, transmit packets, change repository settings,
merge, deploy, or authorize a release. Those actions require trusted adapters and
external authority. Missing or unverifiable evidence remains BLOCK.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
BLOCK = "BLOCK"
READY = "READY_FOR_RX19_REVIEW"
SCHEMA_VERSION = "aigc-responsibility-closure/1.0"

GATES = (
    ("live_pr_state", "Release coordinator", "Current PR metadata; open, draft, unmerged, current full head SHA."),
    ("exact_head_ci", "CI owner", "Completed successful required checks for the exact current head SHA."),
    ("effective_protection", "Authorized repository administrator", "Authenticated effective protection readback for target/base branches."),
    ("reviewer_assignment", "Authorized repository administrator", "Actual qualified, independent reviewer assignment bound to the candidate SHA."),
    ("independent_review", "Independent security reviewer", "Authenticated review and finding dispositions bound to the candidate SHA."),
    ("remediation_retest", "Independent security reviewer", "Every finding remediated and independently retested against the current candidate."),
    ("trusted_provenance", "Trusted CI/provenance owner", "Authenticated producer provenance binds repository, workflow, SHA, tree, run and artifact digest."),
    ("human_acceptance", "Authorized human approver", "Authenticated explicit acceptance binds exact SHA and evidence-manifest digest."),
    ("rx19_handoff", "RX-19 integration owner", "Actual authenticated submission and receipt for the complete candidate-bound packet."),
)

RECEIPT_GATES = {
    "effective_protection": "effective-repository-protection",
    "reviewer_assignment": "independent-reviewer-assignment",
    "independent_review": "independent-security-review",
    "remediation_retest": "independent-remediation-retest",
    "trusted_provenance": "trusted-build-provenance",
    "human_acceptance": "human-acceptance",
    "rx19_handoff": "rx19-handoff-receipt",
}


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256.fullmatch(value))


def canonical_digest(value: Mapping[str, Any]) -> str:
    """Return deterministic SHA-256 over JSON-compatible data."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _receipt_reasons(
    receipt: Any, *, expected_type: str, expected_sha: str, now: int, max_age: int
) -> list[str]:
    reasons: list[str] = []
    if not isinstance(receipt, Mapping):
        return ["receipt_missing"]
    if receipt.get("evidence_type") != expected_type:
        reasons.append("evidence_type_mismatch")
    if receipt.get("subject_sha") != expected_sha:
        reasons.append("subject_sha_mismatch")
    if receipt.get("authenticated") is not True:
        reasons.append("receipt_not_authenticated")
    if receipt.get("revoked") is not False:
        reasons.append("revocation_unknown_or_revoked")
    if not _is_digest(receipt.get("content_sha256")):
        reasons.append("content_digest_invalid")
    for field in ("evidence_uri", "producer_identity", "verification_method"):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            reasons.append(field + "_missing")
    verified_at = receipt.get("verified_at")
    if not isinstance(verified_at, int) or isinstance(verified_at, bool) or verified_at <= 0:
        reasons.append("verification_time_missing")
    elif verified_at > now + 30 or now - verified_at > max_age:
        reasons.append("evidence_stale_or_future_dated")
    return reasons


def evaluate_closure(
    snapshot: Mapping[str, Any], *, evaluation_time: int, max_evidence_age_seconds: int = 3600
) -> dict[str, Any]:
    """Evaluate one snapshot deterministically; never performs external actions.

    Required input:
      pr: {number, state, draft, merged, head_sha}
      ci: {status, conclusion, head_sha, required_checks_complete}
      evidence: mapping of receipt gate names to authenticated receipt objects
      evidence_manifest_sha256: digest of the complete packet manifest

    Receipt objects use evidence_type, subject_sha, authenticated, revoked,
    content_sha256, evidence_uri, producer_identity, verification_method,
    verified_at. Gate-specific booleans are checked below.
    """
    reasons: list[str] = []
    pr = snapshot.get("pr")
    ci = snapshot.get("ci")
    evidence = snapshot.get("evidence")
    expected_sha = pr.get("head_sha") if isinstance(pr, Mapping) else None
    if not isinstance(expected_sha, str) or not FULL_SHA.fullmatch(expected_sha):
        expected_sha = None
        reasons.append("live_pr_head_sha_missing_or_invalid")
    if not isinstance(evaluation_time, int) or isinstance(evaluation_time, bool) or evaluation_time <= 0:
        reasons.append("evaluation_time_invalid")
    if not isinstance(max_evidence_age_seconds, int) or max_evidence_age_seconds <= 0:
        reasons.append("max_evidence_age_invalid")
    now = evaluation_time if isinstance(evaluation_time, int) and not isinstance(evaluation_time, bool) and evaluation_time > 0 else 1
    max_age = max_evidence_age_seconds if isinstance(max_evidence_age_seconds, int) and max_evidence_age_seconds > 0 else 0

    gate_results: list[dict[str, Any]] = []

    def add_gate(gate_id: str, owner: str, contract: str, gate_reasons: list[str]) -> None:
        gate_results.append({
            "gate": gate_id,
            "owner_role": owner,
            "evidence_contract": contract,
            "status": "PASS" if not gate_reasons else "BLOCK",
            "reasons": sorted(set(gate_reasons)),
        })

    # A caller must supply freshly retrieved PR metadata; a cached candidate is not enough.
    pr_reasons: list[str] = []
    if not isinstance(pr, Mapping):
        pr_reasons.append("live_pr_snapshot_missing")
    else:
        if pr.get("state") != "open":
            pr_reasons.append("pr_not_open")
        if pr.get("draft") is not True:
            pr_reasons.append("pr_not_draft")
        if pr.get("merged") is not False:
            pr_reasons.append("pr_merged_or_merge_state_unknown")
        if expected_sha is None:
            pr_reasons.append("live_pr_head_sha_missing_or_invalid")
    add_gate(GATES[0][0], GATES[0][1], GATES[0][2], pr_reasons)

    ci_reasons: list[str] = []
    if expected_sha is None:
        ci_reasons.append("candidate_sha_unavailable")
    if not isinstance(ci, Mapping):
        ci_reasons.append("ci_snapshot_missing")
    else:
        if ci.get("status") != "completed" or ci.get("conclusion") != "success":
            ci_reasons.append("ci_not_completed_successfully")
        if ci.get("head_sha") != expected_sha:
            ci_reasons.append("ci_head_sha_mismatch_or_stale")
        if ci.get("required_checks_complete") is not True:
            ci_reasons.append("required_checks_incomplete_or_unknown")
    add_gate(GATES[1][0], GATES[1][1], GATES[1][2], ci_reasons)

    if not isinstance(evidence, Mapping):
        evidence = {}
        reasons.append("evidence_mapping_missing")
    for gate_id, owner, contract in GATES[2:]:
        gate_reasons = ["candidate_sha_unavailable"] if expected_sha is None else []
        receipt = evidence.get(gate_id)
        if expected_sha is not None:
            gate_reasons.extend(_receipt_reasons(
                receipt, expected_type=RECEIPT_GATES[gate_id], expected_sha=expected_sha,
                now=now, max_age=max_age
            ))
        if isinstance(receipt, Mapping):
            required_flags = {
                "effective_protection": ("effective_settings_readback", "administrator_authorized"),
                "reviewer_assignment": ("reviewer_qualified", "reviewer_independent", "administrator_authorized"),
                "independent_review": ("reviewer_independent", "review_bound_to_sha", "findings_dispositioned"),
                "remediation_retest": ("all_findings_retested", "retester_independent", "retest_bound_to_sha"),
                "trusted_provenance": ("signature_verified", "issuer_verified", "repository_verified", "workflow_verified", "artifact_digest_verified"),
                "human_acceptance": ("approver_authorized", "acceptance_signature_verified", "bound_to_manifest"),
                "rx19_handoff": ("receipt_authenticated", "packet_digest_matches", "recipient_is_rx19"),
            }[gate_id]
            for flag in required_flags:
                if receipt.get(flag) is not True:
                    gate_reasons.append(flag + "_missing_or_false")
            if gate_id == "human_acceptance":
                manifest = snapshot.get("evidence_manifest_sha256")
                if not _is_digest(manifest) or receipt.get("evidence_manifest_sha256") != manifest:
                    gate_reasons.append("acceptance_manifest_mismatch")
            if gate_id == "rx19_handoff":
                manifest = snapshot.get("evidence_manifest_sha256")
                if not _is_digest(manifest) or receipt.get("evidence_manifest_sha256") != manifest:
                    gate_reasons.append("handoff_manifest_mismatch")
        add_gate(gate_id, owner, contract, gate_reasons)

    # The RX-19 decision is intentionally not evaluated or synthesized here.
    # Even a complete packet only becomes eligible for canonical human/authority review.
    blocked = [g["gate"] for g in gate_results if g["status"] != "PASS"]
    disposition = BLOCK if blocked or reasons else READY
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_sha": expected_sha,
        "disposition": disposition,
        "release_decision": BLOCK,
        "rx19_decision_evaluated": False,
        "automatic_mutations_performed": False,
        "gates": gate_results,
        "blocked_gates": blocked,
        "global_reasons": sorted(set(reasons)),
        "report_sha256": canonical_digest({
            "schema_version": SCHEMA_VERSION,
            "candidate_sha": expected_sha,
            "disposition": disposition,
            "gates": gate_results,
            "blocked_gates": blocked,
            "global_reasons": sorted(set(reasons)),
        }),
    }
