"""Bounded control-plane agents for AIGC.

These components are deliberately adapters, not self-authenticating authorities.
Production integrations must supply trusted identity, cryptographic verification,
durable append-only storage, and an isolated execution backend.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import subprocess
from typing import Any, Callable, Mapping, Protocol, Sequence


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
ACTION_RE = re.compile(r"^[a-z][a-z0-9_.:-]{1,127}$")


class ControlError(ValueError):
    """Raised when a control-plane contract is malformed or unsafe."""


@dataclass(frozen=True)
class ExtensionSpec:
    extension_id: str
    version: str
    entrypoint: str
    action_ids: tuple[str, ...]
    input_schema_id: str
    output_schema_id: str
    risk_tier: str
    enabled: bool = False


class AllowlistedExtensionRegistry:
    """Only explicitly registered, enabled extensions with declared actions resolve."""

    def __init__(self, extensions: Sequence[ExtensionSpec] = ()):
        self._extensions: dict[str, ExtensionSpec] = {}
        for spec in extensions:
            self.register(spec)

    def register(self, spec: ExtensionSpec) -> None:
        if not spec.extension_id or not spec.version or not spec.entrypoint:
            raise ControlError("extension_identity_required")
        if spec.extension_id in self._extensions:
            raise ControlError("duplicate_extension_id")
        if not spec.action_ids or any(not ACTION_RE.fullmatch(a) or "*" in a for a in spec.action_ids):
            raise ControlError("explicit_action_allowlist_required")
        if spec.risk_tier not in {"low", "moderate", "high", "critical"}:
            raise ControlError("invalid_risk_tier")
        self._extensions[spec.extension_id] = spec

    def resolve(self, extension_id: str, version: str, action_id: str) -> ExtensionSpec:
        spec = self._extensions.get(extension_id)
        if spec is None or not spec.enabled:
            raise ControlError("extension_not_allowlisted_or_disabled")
        if spec.version != version:
            raise ControlError("extension_version_mismatch")
        if action_id not in spec.action_ids:
            raise ControlError("action_not_allowlisted")
        return spec

    def manifest(self) -> list[dict[str, Any]]:
        return [asdict(self._extensions[k]) for k in sorted(self._extensions)]


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    condition: str
    effect: str
    rationale: str
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class PolicyDraft:
    schema_version: str
    policy_id: str
    policy_version: str
    owner: str
    rules: tuple[PolicyRule, ...]
    created_at: str
    status: str = "DRAFT"


class MVPPolicyCreatorAgent:
    """Creates reviewable policy drafts; cannot activate, sign, or approve them."""

    def create_draft(self, *, policy_id: str, policy_version: str, owner: str,
                     rules: Sequence[Mapping[str, Any]]) -> PolicyDraft:
        if not policy_id or not policy_version or not owner or not rules:
            raise ControlError("policy_identity_owner_and_rules_required")
        compiled: list[PolicyRule] = []
        seen: set[str] = set()
        for item in rules:
            required = {"rule_id", "condition", "effect", "rationale", "source_refs"}
            if not isinstance(item, Mapping) or set(item) != required:
                raise ControlError("policy_rule_schema_mismatch")
            rid, condition, effect = item["rule_id"], item["condition"], item["effect"]
            if not all(isinstance(v, str) and v.strip() for v in (rid, condition, effect, item["rationale"])):
                raise ControlError("policy_rule_fields_must_be_nonempty_strings")
            if rid in seen:
                raise ControlError("duplicate_policy_rule")
            if effect not in {"ALLOW_SCOPED", "BLOCK", "REVIEW_REQUIRED"}:
                raise ControlError("invalid_policy_effect")
            refs = item["source_refs"]
            if not isinstance(refs, (list, tuple)) or not refs or any(not isinstance(x, str) or not x.strip() for x in refs):
                raise ControlError("policy_source_refs_required")
            seen.add(rid)
            compiled.append(PolicyRule(rid, condition, effect, item["rationale"], tuple(refs)))
        return PolicyDraft("aigc-policy-draft/1.0", policy_id, policy_version, owner,
                           tuple(compiled), datetime.now(timezone.utc).isoformat())


class IdentityVerifier(Protocol):
    def verify(self, token: str, *, issuer: str, audience: str, subject: str) -> Mapping[str, Any]: ...


class AuthenticatedPolicyInputAgent:
    """Delegates token cryptography to a configured identity verifier and checks scope."""

    def __init__(self, verifier: IdentityVerifier, allowed_issuers: set[str],
                 allowed_audiences: set[str], allowed_subjects: set[str]):
        self.verifier = verifier
        self.allowed_issuers = set(allowed_issuers)
        self.allowed_audiences = set(allowed_audiences)
        self.allowed_subjects = set(allowed_subjects)

    def authenticate(self, token: str, *, issuer: str, audience: str, subject: str) -> dict[str, Any]:
        if not token or issuer not in self.allowed_issuers or audience not in self.allowed_audiences or subject not in self.allowed_subjects:
            raise ControlError("policy_input_identity_not_allowlisted")
        claims = self.verifier.verify(token, issuer=issuer, audience=audience, subject=subject)
        if not isinstance(claims, Mapping):
            raise ControlError("identity_verifier_invalid_response")
        if claims.get("iss") != issuer or claims.get("aud") != audience or claims.get("sub") != subject:
            raise ControlError("identity_claim_mismatch")
        if claims.get("authenticated") is not True:
            raise ControlError("identity_not_authenticated")
        return {"issuer": issuer, "audience": audience, "subject": subject,
                "claims_digest": sha256(json.dumps(dict(claims), sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


class CosignEvidenceVerifier:
    """Runs cosign against a pinned local executable and validates exact subject bindings.

    The caller must provision/pin cosign and configure the expected certificate identity
    and OIDC issuer. A successful subprocess alone is not enough: subject, commit and
    workflow identity must also match the request. No private signing keys are accepted.
    """

    def __init__(self, cosign_path: str, expected_identity: str, expected_oidc_issuer: str,
                 runner: Callable[..., Any] = subprocess.run):
        if not cosign_path or not expected_identity or not expected_oidc_issuer:
            raise ControlError("cosign_path_and_expected_identity_required")
        self.cosign_path = cosign_path
        self.expected_identity = expected_identity
        self.expected_oidc_issuer = expected_oidc_issuer
        self.runner = runner

    def verify_bundle(self, *, bundle_path: str, artifact_sha256: str, source_sha: str,
                      workflow_identity: str, timeout_seconds: int = 30) -> dict[str, Any]:
        if not DIGEST_RE.fullmatch(artifact_sha256) or not SHA_RE.fullmatch(source_sha):
            raise ControlError("invalid_subject_digest_or_source_sha")
        if workflow_identity != self.expected_identity:
            raise ControlError("unexpected_workflow_identity")
        if not bundle_path or timeout_seconds < 1 or timeout_seconds > 120:
            raise ControlError("invalid_verification_parameters")
        command = [self.cosign_path, "verify-blob-attestation", "--bundle", bundle_path,
                   "--certificate-identity", self.expected_identity,
                   "--certificate-oidc-issuer", self.expected_oidc_issuer]
        result = self.runner(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
        if getattr(result, "returncode", 1) != 0:
            raise ControlError("cosign_signature_or_attestation_verification_failed")
        output = (getattr(result, "stdout", "") or "") + "\n" + (getattr(result, "stderr", "") or "")
        # The caller must provide a machine-readable verified statement from a trusted
        # wrapper. Raw cosign output is not assumed to establish subject/source binding.
        try:
            statement = json.loads(output)
        except (ValueError, TypeError):
            raise ControlError("verified_statement_json_required")
        if not isinstance(statement, Mapping):
            raise ControlError("verified_statement_object_required")
        if statement.get("subject_sha256") != artifact_sha256:
            raise ControlError("subject_digest_mismatch")
        if statement.get("source_sha") != source_sha:
            raise ControlError("source_revision_mismatch")
        if statement.get("workflow_identity") != self.expected_identity:
            raise ControlError("workflow_identity_mismatch")
        return {"verified": True, "artifact_sha256": artifact_sha256, "source_sha": source_sha,
                "workflow_identity": self.expected_identity, "oidc_issuer": self.expected_oidc_issuer,
                "verifier": "cosign", "statement": dict(statement)}


class AppendOnlyAuditSink(Protocol):
    def append(self, record: Mapping[str, Any]) -> str: ...


class ExecutionBackend(Protocol):
    def execute(self, action_id: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]: ...


class ExecutionControllerEnforcementAgent:
    """Fail-closed policy enforcement gate; requires independent decision revalidation."""

    def __init__(self, *, audit_sink: AppendOnlyAuditSink, backend: ExecutionBackend,
                 decision_verifier: Callable[[Mapping[str, Any]], bool],
                 allowlisted_actions: set[str]):
        self.audit_sink = audit_sink
        self.backend = backend
        self.decision_verifier = decision_verifier
        self.allowlisted_actions = set(allowlisted_actions)

    def execute(self, *, action_id: str, payload: Mapping[str, Any], decision: Mapping[str, Any],
                idempotency_key: str, now: datetime | None = None) -> Mapping[str, Any]:
        now = now or datetime.now(timezone.utc)
        if not action_id or action_id not in self.allowlisted_actions or "*" in action_id:
            raise ControlError("action_not_allowlisted")
        if not idempotency_key:
            raise ControlError("idempotency_key_required")
        if not isinstance(decision, Mapping) or decision.get("decision") != "ALLOW_SCOPED":
            raise ControlError("governance_decision_not_allow")
        if decision.get("action_id") != action_id:
            raise ControlError("decision_action_mismatch")
        expiry = decision.get("expires_at")
        try:
            expires = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            raise ControlError("decision_expiry_invalid")
        if expires.tzinfo is None or expires <= now:
            raise ControlError("decision_expired_or_timezone_missing")
        if self.decision_verifier is None or self.decision_verifier(decision) is not True:
            raise ControlError("decision_authentication_failed")
        record = {"event": "execution_requested", "action_id": action_id,
                  "idempotency_key": idempotency_key, "time": now.isoformat(),
                  "decision_digest": sha256(json.dumps(dict(decision), sort_keys=True, default=str).encode()).hexdigest()}
        receipt = self.audit_sink.append(record)
        if not isinstance(receipt, str) or not receipt:
            raise ControlError("audit_append_not_confirmed")
        result = self.backend.execute(action_id, payload, idempotency_key)
        if not isinstance(result, Mapping) or result.get("status") not in {"SUCCEEDED", "FAILED", "UNKNOWN"}:
            raise ControlError("execution_backend_invalid_result")
        self.audit_sink.append({"event": "execution_result", "action_id": action_id,
                                "idempotency_key": idempotency_key, "status": result["status"],
                                "prior_audit_receipt": receipt})
        if result["status"] != "SUCCEEDED":
            raise ControlError("execution_not_confirmed_success")
        return dict(result)


class AdversarialControlTestAgent:
    """Deterministic negative-test harness for controller gate behavior."""

    def run_cases(self, controller: ExecutionControllerEnforcementAgent,
                  base: Mapping[str, Any], cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        results = []
        for case in cases:
            kwargs = dict(base)
            kwargs.update(case.get("overrides", {}))
            try:
                controller.execute(**kwargs)
                observed = "ALLOWED"
            except (ControlError, PermissionError):
                observed = "BLOCKED"
            expected = case.get("expected")
            results.append({"case_id": case.get("case_id", "unnamed"), "expected": expected,
                            "observed": observed, "pass": observed == expected})
        return {"schema_version": "aigc-adversarial-results/1.0",
                "passed": all(item["pass"] for item in results), "cases": results}


class IndependentReviewAcceptanceAgent:
    """Records review evidence; cannot fabricate a reviewer or approve its own work."""

    def evaluate(self, *, subject_sha: str, reviewer_id: str, reviewer_independent: bool,
                 findings: Sequence[Mapping[str, Any]], signed_review_ref: str | None,
                 human_acceptance_ref: str | None) -> dict[str, Any]:
        if not SHA_RE.fullmatch(subject_sha):
            raise ControlError("exact_subject_sha_required")
        if not reviewer_id or not reviewer_independent or not signed_review_ref:
            return {"decision": "BLOCK", "reason": "independent_authenticated_review_missing", "subject_sha": subject_sha}
        if any(not isinstance(f, Mapping) or "finding_id" not in f or "status" not in f for f in findings):
            raise ControlError("review_finding_schema_invalid")
        unresolved = [f for f in findings if f["status"] not in {"RESOLVED", "ACCEPTED_RISK"}]
        if unresolved:
            return {"decision": "BLOCK", "reason": "unresolved_review_findings", "subject_sha": subject_sha,
                    "unresolved_finding_ids": [f["finding_id"] for f in unresolved]}
        if not human_acceptance_ref:
            return {"decision": "REVIEW_REQUIRED", "reason": "explicit_human_acceptance_missing", "subject_sha": subject_sha}
        return {"decision": "REVIEW_EVIDENCE_COMPLETE", "subject_sha": subject_sha,
                "reviewer_id": reviewer_id, "signed_review_ref": signed_review_ref,
                "human_acceptance_ref": human_acceptance_ref}
