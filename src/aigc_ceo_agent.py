"""AIGC CEO Agent: deterministic action approval policy, not an execution engine.

The CEO Agent may approve only low-risk, reversible, internal, zero-cost actions
with exact-version bindings and independently authenticated evidence. It cannot
approve merge, release, deployment, secret access, permission changes, financial
commitments, or other consequential external effects. Those require explicit
human authorization and the separate canonical Release Assurance decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

POLICY_ID = "aigc-ceo-action-approval-v1"
REQUIRED_BINDINGS = ("repository", "commit_sha", "tree_sha", "policy_digest", "invocation_id")
FORBIDDEN_ACTIONS = {
    "merge", "release", "deploy", "deployment", "secret_access", "permission_change",
    "credential_rotation", "production_write", "financial_commitment", "external_purchase",
    "delete_production_data", "disable_security_control",
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def evaluate_action(request: dict[str, Any], envelope: dict[str, Any],
                    evidence_verifier: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None) -> dict[str, Any]:
    """Return a policy decision receipt. This function never executes the action."""
    if not isinstance(request, dict) or not isinstance(envelope, dict):
        raise ValueError("request and envelope must be JSON objects")
    missing = [key for key in REQUIRED_BINDINGS if not envelope.get(key)]
    if missing:
        return _receipt("HOLD", "missing_version_binding", request, envelope)
    if not HEX40.fullmatch(str(envelope.get("commit_sha", ""))) or not HEX40.fullmatch(str(envelope.get("tree_sha", ""))):
        return _receipt("HOLD", "invalid_commit_or_tree_identity", request, envelope)
    if any(request.get(key) != envelope.get(key) for key in REQUIRED_BINDINGS):
        return _receipt("HOLD", "request_envelope_binding_mismatch", request, envelope)

    action = str(request.get("action_type", "")).strip().lower()
    risk = str(request.get("risk_level", "")).strip().lower()
    evidence = request.get("evidence", [])
    if not action:
        return _receipt("HOLD", "missing_action_type", request, envelope)
    if not isinstance(evidence, list) or not evidence:
        return _receipt("HOLD", "missing_evidence", request, envelope)

    # Never trust a caller-supplied authentication_status field by itself.
    # A separate verifier/store integration must cryptographically authenticate
    # each evidence record and its signer/version binding.
    if evidence_verifier is None:
        return _receipt("HOLD", "trusted_evidence_verifier_unavailable", request, envelope)
    for item in evidence:
        if not isinstance(item, dict) or item.get("authentication_status") != "AUTHENTICATED":
            return _receipt("HOLD", "evidence_not_authenticated", request, envelope)
        if any(item.get(key) != envelope.get(key) for key in REQUIRED_BINDINGS):
            return _receipt("HOLD", "evidence_version_binding_mismatch", request, envelope)
        if not item.get("evidence_ref"):
            return _receipt("HOLD", "evidence_reference_missing", request, envelope)
        try:
            verified = evidence_verifier(item, envelope) is True
        except Exception:
            verified = False
        if not verified:
            return _receipt("HOLD", "trusted_evidence_verification_failed", request, envelope)

    if action in FORBIDDEN_ACTIONS or request.get("external_effect") is True:
        return _receipt("REQUIRES_HUMAN", "consequential_action_requires_human_authorization", request, envelope)
    if request.get("reversible") is not True:
        return _receipt("REQUIRES_HUMAN", "action_not_proven_reversible", request, envelope)
    if request.get("estimated_cost") not in (0, 0.0, None):
        return _receipt("REQUIRES_HUMAN", "financial_cost_requires_human_authorization", request, envelope)
    if request.get("permission_change") is True or request.get("secret_access") is True:
        return _receipt("REQUIRES_HUMAN", "privilege_or_secret_boundary_requires_human_authorization", request, envelope)
    if risk != "low":
        return _receipt("REQUIRES_HUMAN", "only_low_risk_actions_are_within_ceo_autoapproval", request, envelope)
    if request.get("independent_review") is not True:
        return _receipt("HOLD", "independent_review_missing", request, envelope)
    if request.get("execution_scope") != "internal-only":
        return _receipt("REQUIRES_HUMAN", "execution_scope_not_internal_only", request, envelope)
    return _receipt("APPROVE", "bounded_low_risk_action_meets_policy", request, envelope)


def _receipt(decision: str, reason: str, request: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema_version": "1.0",
        "policy_id": POLICY_ID,
        "decision_authority": "AIGC CEO Agent bounded action policy",
        "decision": decision,
        "reason_code": reason,
        "action_id": request.get("action_id"),
        "action_type": request.get("action_type"),
        "repository": envelope.get("repository"),
        "commit_sha": envelope.get("commit_sha"),
        "tree_sha": envelope.get("tree_sha"),
        "policy_digest": envelope.get("policy_digest"),
        "invocation_id": envelope.get("invocation_id"),
        "request_digest_sha256": digest(request),
        "execution_performed": False,
        "release_decision": "NOT_MADE",
        "requires_human_authorization": decision == "REQUIRES_HUMAN",
        "note": "This digest provides integrity comparison, not cryptographic authentication or identity proof.",
    }
    body["receipt_digest_sha256"] = hashlib.sha256(canonical_json(body)).hexdigest()
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate an AIGC action request without executing it.")
    parser.add_argument("--request", required=True, help="Action request JSON")
    parser.add_argument("--envelope", required=True, help="Exact repository/commit/tree/policy/invocation JSON")
    parser.add_argument("--output", required=True, help="Decision receipt output path")
    args = parser.parse_args(argv)
    try:
        request = json.loads(Path(args.request).read_text(encoding="utf-8"))
        envelope = json.loads(Path(args.envelope).read_text(encoding="utf-8"))
        result = evaluate_action(request, envelope)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"decision": result["decision"], "reason_code": result["reason_code"],
                      "execution_performed": False, "release_decision": "NOT_MADE"}, indent=2))
    return 0 if result["decision"] == "APPROVE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
