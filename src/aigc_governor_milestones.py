"""Fail-closed milestone gate for Governor integration work.

This is a workflow/readiness evaluator, not a cryptographic verifier or executor.
Evidence must be authenticated by independent verifier services before being supplied.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
STAGES = (
    "authenticated_policy_inputs",
    "cryptographic_evidence_validation",
    "execution_controller_enforcement",
    "independent_audit_retention",
    "adversarial_integration_tests",
    "independent_review_and_acceptance",
)


def evaluate_milestones(
    record: Mapping[str, Any], *, expected_sha: str, now: datetime | None = None
) -> dict[str, Any]:
    """Evaluate ordered implementation gates; never enable production on assertions alone.

    Each gate must be PASS and carry an exact-subject evidence reference plus the
    identity of an independent verifier. This function checks record shape only;
    it cannot establish that the evidence or verifier identity is genuine.
    """
    reasons: list[str] = []
    if not isinstance(expected_sha, str) or not FULL_SHA.fullmatch(expected_sha):
        return _result("BLOCK", ["invalid_expected_sha"], [], expected_sha)

    if not isinstance(record, Mapping):
        return _result("BLOCK", ["record_not_object"], [], expected_sha)

    if record.get("schema_version") != "aigc-governor-milestones/1.0":
        reasons.append("schema_version_mismatch")
    if record.get("subject_sha") != expected_sha:
        reasons.append("subject_sha_mismatch")

    stages = record.get("stages")
    if not isinstance(stages, Mapping):
        return _result("BLOCK", reasons + ["stages_not_object"], [], expected_sha)

    unknown = set(stages.keys()) - set(STAGES)
    if unknown:
        reasons.append("unknown_stages:" + ",".join(sorted(str(x) for x in unknown)))

    passed: list[str] = []
    first_incomplete: str | None = None
    for name in STAGES:
        stage = stages.get(name)
        if not isinstance(stage, Mapping):
            first_incomplete = first_incomplete or name
            reasons.append(f"{name}:missing_record")
            continue
        if stage.get("status") != "PASS":
            first_incomplete = first_incomplete or name
            reasons.append(f"{name}:not_pass")
            continue
        if stage.get("subject_sha") != expected_sha:
            first_incomplete = first_incomplete or name
            reasons.append(f"{name}:subject_sha_mismatch")
            continue
        if not isinstance(stage.get("evidence_ref"), str) or not stage["evidence_ref"].strip():
            first_incomplete = first_incomplete or name
            reasons.append(f"{name}:evidence_ref_missing")
            continue
        if not isinstance(stage.get("verifier_identity"), str) or not stage["verifier_identity"].strip():
            first_incomplete = first_incomplete or name
            reasons.append(f"{name}:independent_verifier_missing")
            continue
        if stage.get("verified") is not True:
            first_incomplete = first_incomplete or name
            reasons.append(f"{name}:verification_not_confirmed")
            continue
        passed.append(name)

    # Explicit human acceptance is mandatory and must bind to the same subject.
    acceptance = record.get("human_acceptance")
    if not isinstance(acceptance, Mapping):
        reasons.append("human_acceptance_missing")
    else:
        if acceptance.get("accepted") is not True:
            reasons.append("human_acceptance_not_granted")
        if acceptance.get("subject_sha") != expected_sha:
            reasons.append("human_acceptance_subject_mismatch")
        if not isinstance(acceptance.get("approver_identity"), str) or not acceptance.get("approver_identity", "").strip():
            reasons.append("human_approver_identity_missing")
        if acceptance.get("authenticated") is not True:
            reasons.append("human_acceptance_not_authenticated")

    if reasons or len(passed) != len(STAGES):
        return _result("BLOCK", sorted(set(reasons)), passed, expected_sha,
                       first_incomplete=first_incomplete)

    return _result("ELIGIBLE_FOR_EXTERNAL_PRODUCTION_REVIEW",
                   ["all_declared_gates_passed_external_verification_and_controller_checks_still_required"],
                   passed, expected_sha)


def _result(
    decision: str, reasons: list[str], passed: list[str], subject_sha: Any,
    *, first_incomplete: str | None = None
) -> dict[str, Any]:
    return {
        "schema_version": "aigc-governor-milestones-result/1.0",
        "decision": decision,
        "reasons": reasons,
        "passed_stages": passed,
        "first_incomplete_stage": first_incomplete,
        "subject_sha": subject_sha,
        "production_enabled": False,
        "authority": "readiness_advisory_only",
        "cryptographic_verification_performed": False,
        "execution_performed": False,
        "release_decision_authority": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
