"""Fail-closed readiness trigger assessment for AIGC release gates.

Pure reference evaluator. It does not dispatch workflows, authenticate identities,
read GitHub, or grant production/merge/release authority.
"""
from __future__ import annotations

from typing import Any, Mapping
import re

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


def assess_release_readiness(state: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate internal CI and external release dependencies without inference."""
    if not isinstance(state, Mapping):
        raise ValueError("readiness_state_must_be_object")
    candidate = state.get("candidate_sha")
    if not isinstance(candidate, str) or not _SHA.fullmatch(candidate):
        raise ValueError("candidate_sha_invalid")
    evidence_digest = state.get("evidence_digest")
    if not isinstance(evidence_digest, str) or not _DIGEST.fullmatch(evidence_digest):
        raise ValueError("evidence_digest_invalid")

    observed = state.get("observed_ci_sha")
    ci_pass = observed == candidate and state.get("ci_status") == "success"
    review_pass = (
        isinstance(state.get("independent_review_count"), int)
        and state["independent_review_count"] > 0
        and state.get("review_exact_sha") == candidate
        and state.get("review_findings_status") == "CLOSED_OR_NONE_WITH_EVIDENCE"
        and state.get("reviewer_qualified_independent") is True
    )
    protection_pass = state.get("protection_readback_status") == "VERIFIED"
    acceptance_pass = (
        state.get("acceptance_authenticated") is True
        and state.get("acceptance_sha") == candidate
        and state.get("acceptance_evidence_digest") == evidence_digest
    )
    merged = state.get("merged") is True
    provenance_pass = merged and state.get("post_merge_provenance_status") == "VERIFIED"
    retention_pass = merged and state.get("retention_retrieval_status") == "VERIFIED"

    gates = [
        {"gate_id": "exact_head_ci", "agent_id": "RX-136", "status": "PASS" if ci_pass else "BLOCK",
         "reason": "exact_sha_ci_success" if ci_pass else "missing_failed_or_sha_mismatched_ci"},
        {"gate_id": "independent_human_review", "agent_id": "RX-131", "status": "PASS" if review_pass else "BLOCK",
         "reason": "qualified_review_bound_to_sha" if review_pass else "independent_review_missing_or_unverified"},
        {"gate_id": "repository_protection", "agent_id": "RX-132", "status": "PASS" if protection_pass else "BLOCK",
         "reason": "authorized_protection_readback_verified" if protection_pass else "protection_readback_missing_or_unverified"},
        {"gate_id": "authenticated_acceptance", "agent_id": "RX-133", "status": "PASS" if acceptance_pass else "BLOCK",
         "reason": "authenticated_acceptance_matches_sha_and_digest" if acceptance_pass else "acceptance_missing_unauthenticated_or_mismatched"},
        {"gate_id": "post_merge_provenance", "agent_id": "RX-137", "status": "PASS" if provenance_pass else "BLOCK",
         "reason": "post_merge_provenance_verified" if provenance_pass else "merge_or_signed_provenance_not_verified"},
        {"gate_id": "independent_retention", "agent_id": "RX-137", "status": "PASS" if retention_pass else "BLOCK",
         "reason": "independent_retention_retrieval_verified" if retention_pass else "retention_receipt_missing_or_unverified"},
    ]
    blocked = [g["gate_id"] for g in gates if g["status"] != "PASS"]
    external_triggers = []
    if not review_pass:
        external_triggers.append({"owner_role": "authorized_repository_administrator", "action": "assign qualified independent human reviewer; obtain exact-SHA review and finding closure"})
    if not protection_pass:
        external_triggers.append({"owner_role": "authorized_repository_administrator", "action": "read back and provide authenticated branch/ruleset protection evidence"})
    if not acceptance_pass:
        external_triggers.append({"owner_role": "authorized_human_approver", "action": "provide authenticated acceptance receipt bound to candidate SHA and evidence digest"})
    if not provenance_pass:
        external_triggers.append({"owner_role": "authorized_maintainer_after_premerge_gates", "action": "after authorized merge, verify post-merge signed provenance"})
    if not retention_pass:
        external_triggers.append({"owner_role": "evidence_retention_operator", "action": "verify independently retained artifact retrieval after provenance generation"})
    return {
        "status": "READY_FOR_RX19_DECISION" if not blocked else "BLOCK",
        "candidate_sha": candidate,
        "evidence_digest": evidence_digest if evidence_digest.startswith("sha256:") else "sha256:" + evidence_digest,
        "gate_results": gates,
        "blocked_gates": blocked,
        "external_triggers": external_triggers,
        "canonical_release_authority": "RX-19",
        "production_authorization": False,
        "merge_authorization": False,
        "agent_activation_authorization": False,
    }
