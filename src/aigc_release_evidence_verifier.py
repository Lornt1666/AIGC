"""Fail-closed AIGC release-evidence verifier policy engine.

This module validates evidence receipts from independently trusted adapters. It does
not itself fetch GitHub data, verify JWTs/signatures, operate a controller, authenticate
reviewers, or write to the evidence store. Those integrations must provide cryptographically
verified receipts and are separately acceptance-tested. This agent can never authorize a
release; its maximum disposition is READY_FOR_CANONICAL_REVIEW.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import time
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "aigc-evidence-verifier-receipt/1.0"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
TREE_SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST_SHA256 = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
READY = "READY_FOR_CANONICAL_REVIEW"
BLOCK = "BLOCK"
RELEASE_DECISION = "BLOCK"
REQUIRED_GATES = (
    "subject",
    "ci",
    "artifact",
    "oidc",
    "attestation",
    "controller",
    "audit",
    "adversarial",
    "independent_review",
    "human_acceptance",
)


@dataclass(frozen=True)
class VerifierPolicy:
    policy_id: str
    policy_version: str
    policy_digest: str
    repository: str
    repository_id: str
    owner_id: str
    workflow_path: str
    allowed_events: frozenset[str]
    allowed_refs: frozenset[str]
    required_checks: frozenset[str]
    required_adversarial_cases: frozenset[str]
    attestation_predicate: str
    attestation_verifier: str
    attestation_verifier_version: str
    max_evidence_age_seconds: int = 3600

    def validate(self) -> list[str]:
        errors = []
        if not self.policy_id.strip() or not self.policy_version.strip():
            errors.append("policy_identity_missing")
        if not DIGEST_SHA256.fullmatch(self.policy_digest):
            errors.append("policy_digest_invalid")
        if not self.repository or "/" not in self.repository:
            errors.append("canonical_repository_invalid")
        if not self.repository_id.isdigit() or not self.owner_id.isdigit():
            errors.append("immutable_repository_or_owner_id_invalid")
        if not self.workflow_path.startswith(".github/workflows/"):
            errors.append("workflow_path_invalid")
        if not self.allowed_events or not self.allowed_refs:
            errors.append("event_or_ref_allowlist_empty")
        if not self.required_checks:
            errors.append("required_check_allowlist_empty")
        if not self.required_adversarial_cases:
            errors.append("adversarial_case_allowlist_empty")
        if not self.attestation_predicate.strip():
            errors.append("attestation_predicate_missing")
        if not self.attestation_verifier.strip() or not self.attestation_verifier_version.strip():
            errors.append("attestation_verifier_not_pinned")
        if self.max_evidence_age_seconds <= 0:
            errors.append("max_evidence_age_invalid")
        return errors


def _sha(value: Any, *, tree: bool = False) -> bool:
    return isinstance(value, str) and bool((TREE_SHA if tree else FULL_SHA).fullmatch(value))


def _digest(value: Any) -> bool:
    return isinstance(value, str) and bool(DIGEST_SHA256.fullmatch(value))


def _safe_text(value: Any, max_length: int = 256) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"(?i)(authorization\s*[:=]\s*|bearer\s+)[^\s,;]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(token|password|secret|api[_-]?key)(\s*[:=]\s*)[^\s,;]+", r"\1\2[REDACTED]", text)
    return text[:max_length]


def _same(record: Mapping[str, Any], key: str, expected: Any, reason: str, reasons: list[str]) -> None:
    if record.get(key) != expected:
        reasons.append(reason)


def _receipt_ok(record: Any, *, evidence_type: str, sha: str, tree_sha: str,
                policy: VerifierPolicy, reasons: list[str], prefix: str,
                evaluation_time: int, run_id: str | None = None, run_attempt: str | None = None) -> bool:
    if not isinstance(record, Mapping):
        reasons.append(prefix + "_missing")
        return False
    required = {
        "evidence_type": evidence_type,
        "repository": policy.repository,
        "repository_id": policy.repository_id,
        "subject_sha": sha,
        "subject_tree_sha": tree_sha,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.policy_digest,
    }
    ok = True
    for key, expected in required.items():
        if record.get(key) != expected:
            reasons.append(prefix + "_binding_mismatch:" + key)
            ok = False
    if run_id is not None and str(record.get("run_id", "")) != run_id:
        reasons.append(prefix + "_binding_mismatch:run_id")
        ok = False
    if run_attempt is not None and str(record.get("run_attempt", "")) != run_attempt:
        reasons.append(prefix + "_binding_mismatch:run_attempt")
        ok = False
    if record.get("authenticated") is not True:
        reasons.append(prefix + "_not_authenticated")
        ok = False
    if record.get("revoked") is not False:
        reasons.append(prefix + "_revocation_unknown_or_revoked")
        ok = False
    if not _digest(record.get("content_sha256")):
        reasons.append(prefix + "_content_digest_invalid")
        ok = False
    if not isinstance(record.get("evidence_uri"), str) or not record.get("evidence_uri", "").strip():
        reasons.append(prefix + "_evidence_locator_missing")
        ok = False
    if not isinstance(record.get("producer_identity"), str) or not record.get("producer_identity", "").strip():
        reasons.append(prefix + "_producer_identity_missing")
        ok = False
    if not isinstance(record.get("verification_method"), str) or not record.get("verification_method", "").strip():
        reasons.append(prefix + "_verification_method_missing")
        ok = False
    verified_at = record.get("verified_at")
    if not isinstance(verified_at, int) or verified_at <= 0:
        reasons.append(prefix + "_verification_time_missing")
        ok = False
    elif verified_at > evaluation_time + 30 or evaluation_time - verified_at > policy.max_evidence_age_seconds:
        reasons.append(prefix + "_evidence_stale_or_future_dated")
        ok = False
    return ok


def evaluate_evidence(policy: VerifierPolicy, bundle: Mapping[str, Any], *, evaluation_time: int | None = None) -> dict[str, Any]:
    """Evaluate one immutable evidence bundle; inject evaluation_time for reproducible tests."""
    evaluation_time = int(time.time()) if evaluation_time is None else evaluation_time
    reasons = policy.validate()
    if not isinstance(evaluation_time, int) or evaluation_time <= 0:
        reasons.append("evaluation_time_invalid")
        evaluation_time = 1
    subject = bundle.get("subject") if isinstance(bundle, Mapping) else None
    if not isinstance(subject, Mapping):
        subject = {}
        reasons.append("subject_missing")

    sha = subject.get("commit_sha")
    tree_sha = subject.get("tree_sha")
    if not _sha(sha):
        reasons.append("subject_commit_sha_invalid")
    if not _sha(tree_sha, tree=True):
        reasons.append("subject_tree_sha_invalid")
    if subject.get("repository") != policy.repository:
        reasons.append("subject_repository_mismatch")
    if str(subject.get("repository_id", "")) != policy.repository_id:
        reasons.append("subject_repository_id_mismatch")
    if str(subject.get("owner_id", "")) != policy.owner_id:
        reasons.append("subject_owner_id_mismatch")
    if subject.get("ref") not in policy.allowed_refs:
        reasons.append("subject_ref_not_allowlisted")
    if subject.get("event") not in policy.allowed_events:
        reasons.append("subject_event_not_allowlisted")
    if subject.get("source_tree_verified") is not True:
        reasons.append("subject_tree_not_independently_verified")

    ci = bundle.get("ci") if isinstance(bundle.get("ci"), Mapping) else {}
    run_id = str(ci.get("run_id", ""))
    run_attempt = str(ci.get("run_attempt", ""))
    if not run_id.isdigit() or not run_attempt.isdigit():
        reasons.append("ci_run_identity_missing")
    for key, expected, reason in (
        ("repository", policy.repository, "ci_repository_mismatch"),
        ("repository_id", policy.repository_id, "ci_repository_id_mismatch"),
        ("owner_id", policy.owner_id, "ci_owner_id_mismatch"),
        ("head_sha", sha, "ci_head_sha_mismatch"),
        ("tree_sha", tree_sha, "ci_tree_sha_mismatch"),
        ("workflow_path", policy.workflow_path, "ci_workflow_path_mismatch"),
    ):
        if ci.get(key) != expected:
            reasons.append(reason)
    if ci.get("event") not in policy.allowed_events:
        reasons.append("ci_event_not_allowlisted")
    if ci.get("ref") not in policy.allowed_refs:
        reasons.append("ci_ref_not_allowlisted")
    if ci.get("status") != "completed" or ci.get("conclusion") != "success":
        reasons.append("ci_not_complete_success")
    if ci.get("required_checks_complete") is not True:
        reasons.append("ci_required_checks_not_complete")
    checks = ci.get("checks") if isinstance(ci.get("checks"), list) else []
    observed = {}
    for check in checks:
        if not isinstance(check, Mapping) or not isinstance(check.get("name"), str):
            reasons.append("ci_check_record_malformed")
            continue
        name = check["name"]
        if name in observed:
            reasons.append("ci_duplicate_check:" + _safe_text(name))
        observed[name] = check.get("conclusion")
        if check.get("conclusion") != "success":
            reasons.append("ci_check_not_success:" + _safe_text(name))
        if check.get("required") is not True:
            reasons.append("ci_required_check_not_policy_marked:" + _safe_text(name))
        if check.get("skipped") is True:
            reasons.append("ci_required_check_skipped:" + _safe_text(name))
    for required in sorted(policy.required_checks):
        if observed.get(required) != "success":
            reasons.append("ci_required_check_missing_or_failed:" + _safe_text(required))

    artifact = bundle.get("artifact") if isinstance(bundle.get("artifact"), Mapping) else {}
    for key, expected, reason in (
        ("repository", policy.repository, "artifact_repository_mismatch"),
        ("subject_sha", sha, "artifact_subject_sha_mismatch"),
        ("subject_tree_sha", tree_sha, "artifact_subject_tree_mismatch"),
        ("run_id", run_id, "artifact_run_id_mismatch"),
        ("run_attempt", run_attempt, "artifact_run_attempt_mismatch"),
    ):
        if artifact.get(key) != expected:
            reasons.append(reason)
    if artifact.get("bytes_rehashed_locally") is not True:
        reasons.append("artifact_not_locally_rehashed")
    if not _digest(artifact.get("sha256")):
        reasons.append("artifact_digest_invalid")
    if artifact.get("digest_matches_attestation") is not True:
        reasons.append("artifact_digest_not_bound_to_attestation")
    if artifact.get("safe_archive_inspection") is not True:
        reasons.append("artifact_archive_not_safely_inspected")
    if artifact.get("manifest_sha256") is None or not _digest(artifact.get("manifest_sha256")):
        reasons.append("artifact_manifest_digest_invalid")

    oidc = bundle.get("oidc")
    oidc_ok = _receipt_ok(oidc, evidence_type="oidc-verification", sha=sha, tree_sha=tree_sha,
                          policy=policy, reasons=reasons, prefix="oidc", evaluation_time=evaluation_time,
                          run_id=run_id, run_attempt=run_attempt)
    if isinstance(oidc, Mapping):
        if oidc.get("issuer") != "https://token.actions.githubusercontent.com":
            reasons.append("oidc_issuer_mismatch")
            oidc_ok = False
        if str(oidc.get("owner_id", "")) != policy.owner_id:
            reasons.append("oidc_owner_id_mismatch")
            oidc_ok = False
        if oidc.get("signature_verified") is not True:
            reasons.append("oidc_signature_not_verified")
            oidc_ok = False
        if oidc.get("audience_matches_policy") is not True:
            reasons.append("oidc_audience_mismatch")
            oidc_ok = False
        if oidc.get("subject_matches_policy") is not True:
            reasons.append("oidc_subject_mismatch")
            oidc_ok = False
        if oidc.get("claims_match_exact_run") is not True:
            reasons.append("oidc_claims_not_bound_to_exact_run")
            oidc_ok = False
        if oidc.get("raw_token_retained") is not False:
            reasons.append("oidc_raw_token_retained_or_unknown")
            oidc_ok = False
        if oidc.get("replay_protection_verified") is not True:
            reasons.append("oidc_replay_protection_unverified")
            oidc_ok = False

    att = bundle.get("attestation")
    att_ok = _receipt_ok(att, evidence_type="attestation-verification", sha=sha, tree_sha=tree_sha,
                          policy=policy, reasons=reasons, prefix="attestation", evaluation_time=evaluation_time,
                          run_id=run_id, run_attempt=run_attempt)
    if isinstance(att, Mapping):
        for key, expected, reason in (
            ("verifier", policy.attestation_verifier, "attestation_verifier_mismatch"),
            ("verifier_version", policy.attestation_verifier_version, "attestation_verifier_version_mismatch"),
            ("predicate_type", policy.attestation_predicate, "attestation_predicate_mismatch"),
            ("source_repository", policy.repository, "attestation_source_repository_mismatch"),
            ("source_sha", sha, "attestation_source_sha_mismatch"),
            ("source_tree_sha", tree_sha, "attestation_source_tree_mismatch"),
            ("subject_sha256", artifact.get("sha256"), "attestation_subject_digest_mismatch"),
        ):
            if att.get(key) != expected:
                reasons.append(reason)
                att_ok = False
        if att.get("signature_verified") is not True or att.get("transparency_verified") is not True:
            reasons.append("attestation_crypto_or_transparency_not_verified")
            att_ok = False
        if att.get("verifier_exit_code") != 0 or att.get("structured_output_valid") is not True:
            reasons.append("attestation_verifier_execution_invalid")
            att_ok = False
        if att.get("eligibility_checked") is not True or att.get("eligibility_supported") is not True:
            reasons.append("attestation_eligibility_missing_or_unsupported")
            att_ok = False
        if att.get("hash_only_fallback") is not False:
            reasons.append("attestation_hash_only_fallback_detected_or_unknown")
            att_ok = False

    controller = bundle.get("controller")
    controller_ok = _receipt_ok(controller, evidence_type="controller-assurance", sha=sha, tree_sha=tree_sha,
                                policy=policy, reasons=reasons, prefix="controller", evaluation_time=evaluation_time)
    if isinstance(controller, Mapping):
        for key in ("real_interface_verified", "server_side_authorization", "durable_intent_before_dispatch",
                    "idempotency_verified", "restart_recovery_verified", "ambiguous_outcome_is_unknown",
                    "worker_bypass_denied"):
            if controller.get(key) is not True:
                reasons.append("controller_gate_failed:" + key)
                controller_ok = False

    audit = bundle.get("audit")
    audit_ok = _receipt_ok(audit, evidence_type="audit-service-assurance", sha=sha, tree_sha=tree_sha,
                            policy=policy, reasons=reasons, prefix="audit", evaluation_time=evaluation_time)
    if isinstance(audit, Mapping):
        for key in ("real_interface_verified", "independent_admin_boundary", "append_only_verified",
                    "tamper_detection_verified", "retention_verified", "restore_test_passed",
                    "authenticated_receipts_verified"):
            if audit.get(key) is not True:
                reasons.append("audit_gate_failed:" + key)
                audit_ok = False
        if controller and audit.get("admin_boundary_id") == controller.get("admin_boundary_id"):
            reasons.append("audit_not_independently_administered")
            audit_ok = False
        if not audit.get("admin_boundary_id"):
            reasons.append("audit_admin_boundary_missing")
            audit_ok = False

    adv = bundle.get("adversarial")
    adversarial_ok = True
    if not isinstance(adv, Mapping):
        reasons.append("adversarial_evidence_missing")
        adversarial_ok = False
    else:
        if adv.get("real_interfaces") is not True or adv.get("subject_sha") != sha or adv.get("subject_tree_sha") != tree_sha:
            reasons.append("adversarial_suite_not_bound_to_real_exact_subject")
            adversarial_ok = False
        cases = adv.get("cases") if isinstance(adv.get("cases"), list) else []
        results = {}
        for case in cases:
            if not isinstance(case, Mapping) or not isinstance(case.get("case_id"), str):
                reasons.append("adversarial_case_malformed")
                adversarial_ok = False
                continue
            cid = case["case_id"]
            if cid in results:
                reasons.append("adversarial_case_duplicate:" + _safe_text(cid))
                adversarial_ok = False
            results[cid] = case
            if case.get("executed") is not True or case.get("actual_outcome") != case.get("expected_outcome") or case.get("evidence_digest") is None or not _digest(case.get("evidence_digest")):
                reasons.append("adversarial_case_failed_or_unproven:" + _safe_text(cid))
                adversarial_ok = False
        for required in sorted(policy.required_adversarial_cases):
            if required not in results:
                reasons.append("adversarial_case_missing:" + _safe_text(required))
                adversarial_ok = False

    review = bundle.get("independent_review")
    review_ok = _receipt_ok(review, evidence_type="independent-security-review", sha=sha, tree_sha=tree_sha,
                            policy=policy, reasons=reasons, prefix="review", evaluation_time=evaluation_time)
    if isinstance(review, Mapping):
        for key in ("reviewer_authenticated", "reviewer_independent", "reviewer_signature_verified",
                    "findings_closed", "remediation_retested", "review_bound_to_manifest"):
            if review.get(key) is not True:
                reasons.append("review_gate_failed:" + key)
                review_ok = False
        if review.get("reviewer_identity") in {subject.get("author_identity"), subject.get("implementer_identity")}:
            reasons.append("reviewer_not_independent_of_author_or_implementer")
            review_ok = False
        if review.get("evidence_manifest_sha256") != artifact.get("manifest_sha256") or not _digest(review.get("evidence_manifest_sha256")):
            reasons.append("review_manifest_binding_missing_or_mismatched")
            review_ok = False

    acceptance = bundle.get("human_acceptance")
    acceptance_ok = _receipt_ok(acceptance, evidence_type="human-acceptance", sha=sha, tree_sha=tree_sha,
                                policy=policy, reasons=reasons, prefix="acceptance", evaluation_time=evaluation_time)
    if isinstance(acceptance, Mapping):
        for key in ("approver_authenticated", "approver_authorized", "acceptance_signature_verified",
                    "approval_current", "bound_to_manifest", "bound_to_review"):
            if acceptance.get(key) is not True:
                reasons.append("acceptance_gate_failed:" + key)
                acceptance_ok = False
        if acceptance.get("approver_identity") in {subject.get("author_identity"), subject.get("implementer_identity")}:
            reasons.append("approver_not_independent_of_author_or_implementer")
            acceptance_ok = False
        if acceptance.get("evidence_manifest_sha256") != artifact.get("manifest_sha256") or not _digest(acceptance.get("evidence_manifest_sha256")):
            reasons.append("acceptance_manifest_binding_missing_or_mismatched")
            acceptance_ok = False
        if isinstance(review, Mapping) and acceptance.get("review_content_sha256") != review.get("content_sha256"):
            reasons.append("acceptance_review_binding_mismatch")
            acceptance_ok = False

    gate_values = {
        "subject": not any(r.startswith("subject_") for r in reasons),
        "ci": not any(r.startswith("ci_") for r in reasons),
        "artifact": not any(r.startswith("artifact_") for r in reasons),
        "oidc": oidc_ok,
        "attestation": att_ok,
        "controller": controller_ok,
        "audit": audit_ok,
        "adversarial": adversarial_ok,
        "independent_review": review_ok,
        "human_acceptance": acceptance_ok,
    }
    # Any reason, including an unclassified or cross-gate conflict, blocks.
    reasons = sorted(set(_safe_text(r, 320) for r in reasons))
    ready = not reasons and all(gate_values.values())
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "policy": {"id": policy.policy_id, "version": policy.policy_version,
                   "digest": policy.policy_digest},
        "subject": {"repository": policy.repository, "repository_id": policy.repository_id,
                    "commit_sha": sha, "tree_sha": tree_sha,
                    "run_id": run_id, "run_attempt": run_attempt},
        "gates": {k: bool(v) for k, v in sorted(gate_values.items())},
        "reasons": reasons,
        "disposition": READY if ready else BLOCK,
        "release_decision": RELEASE_DECISION,
        "release_authority": "canonical Release Assurance Agent only",
        "automatic_mutations_performed": False,
        "raw_tokens_emitted": False,
    }
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    return receipt


def handoff_payload(receipt: Mapping[str, Any], *, evidence_manifest_uri: str,
                    evidence_manifest_sha256: str) -> dict[str, Any]:
    """Prepare (but do not transmit) the canonical Release Assurance handoff."""
    if receipt.get("disposition") != READY or receipt.get("release_decision") != BLOCK:
        raise ValueError("handoff_blocked: verifier evidence is incomplete")
    if not evidence_manifest_uri.strip() or not _digest(evidence_manifest_sha256):
        raise ValueError("handoff_manifest_binding_invalid")
    subject = receipt.get("subject")
    if not isinstance(subject, Mapping) or not _sha(subject.get("commit_sha")) or not _sha(subject.get("tree_sha"), tree=True):
        raise ValueError("handoff_subject_invalid")
    return {
        "schema_version": "aigc-release-assurance-handoff/1.0",
        "subject": dict(subject),
        "evidence_manifest_uri": evidence_manifest_uri,
        "evidence_manifest_sha256": evidence_manifest_sha256,
        "verifier_receipt_sha256": receipt.get("receipt_sha256"),
        "requested_action": "EVALUATE_RELEASE_ELIGIBILITY",
        "release_authorization": "NOT_GRANTED",
        "destination": "canonical Release Assurance Agent",
    }
