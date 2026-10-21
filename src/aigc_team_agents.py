"""Fail-closed, read-only AER and Red/Blue/Green team report producers.

These are deterministic evaluators, not execution engines. Red Team never performs
network or exploit actions; active testing is denied by default. Reports are not
authenticated by a SHA-256 digest alone. Production consumers must verify signatures
and identity through an independently configured verifier before trusting these reports.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Callable

SCHEMA_VERSION = "1.0"
POLICY_ID = "aigc-team-assurance-v1"
PASS, FAIL, UNKNOWN, BLOCK = "PASS", "FAIL", "UNKNOWN", "BLOCK"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> bytes:
    """Canonical JSON for local integrity checks; this is not a signature."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None
    except (ValueError, TypeError):
        return False


def validate_envelope(envelope: Any) -> list[dict[str, str]]:
    """Validate a strict, revision-bound input envelope; no implicit defaults."""
    problems: list[dict[str, str]] = []
    if not isinstance(envelope, dict):
        return [{"id": "envelope", "status": UNKNOWN, "detail": "Envelope is absent or not an object."}]
    required = ("schema_version", "policy_id", "policy_digest", "repository", "commit_sha",
                "tree_sha", "invocation_id", "producer_identity", "issued_at_utc",
                "expires_at_utc", "evidence_refs")
    for field in required:
        if field not in envelope or envelope[field] is None or envelope[field] == "":
            problems.append({"id": f"envelope_{field}", "status": UNKNOWN, "detail": f"Missing/invalid {field}."})
    if envelope.get("schema_version") != SCHEMA_VERSION:
        problems.append({"id": "envelope_schema_version", "status": BLOCK, "detail": "Unsupported schema version."})
    if envelope.get("policy_id") != POLICY_ID:
        problems.append({"id": "envelope_policy_id", "status": BLOCK, "detail": "Unexpected policy identifier."})
    if isinstance(envelope.get("policy_digest"), str) and not _SHA64.fullmatch(envelope["policy_digest"]):
        problems.append({"id": "envelope_policy_digest", "status": BLOCK, "detail": "Policy digest must be lowercase SHA-256 hex."})
    for field in ("commit_sha", "tree_sha"):
        if isinstance(envelope.get(field), str) and not _SHA40.fullmatch(envelope[field]):
            problems.append({"id": f"envelope_{field}", "status": BLOCK, "detail": f"{field} must be a full lowercase Git SHA."})
    if isinstance(envelope.get("repository"), str) and envelope["repository"].count("/") != 1:
        problems.append({"id": "envelope_repository", "status": BLOCK, "detail": "Repository must be owner/name."})
    for field in ("issued_at_utc", "expires_at_utc"):
        if envelope.get(field) and not _valid_timestamp(envelope[field]):
            problems.append({"id": f"envelope_{field}", "status": BLOCK, "detail": f"{field} must be timezone-aware ISO-8601."})
    if _valid_timestamp(envelope.get("issued_at_utc")) and _valid_timestamp(envelope.get("expires_at_utc")):
        issued = datetime.fromisoformat(envelope["issued_at_utc"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(envelope["expires_at_utc"].replace("Z", "+00:00"))
        if expires <= issued:
            problems.append({"id": "envelope_expiry_order", "status": BLOCK, "detail": "Expiry must be later than issue time."})
    if "evidence_refs" in envelope and not isinstance(envelope["evidence_refs"], list):
        problems.append({"id": "envelope_evidence_refs", "status": BLOCK, "detail": "evidence_refs must be a list."})
    return problems


def make_report(agent_id: str, envelope: dict[str, Any], checks: list[dict[str, Any]],
                findings: list[dict[str, Any]] | None = None,
                required_actions: list[str] | None = None) -> dict[str, Any]:
    envelope_problems = validate_envelope(envelope)
    decision = PASS if not envelope_problems and checks and all(c.get("status") == PASS for c in checks) else BLOCK
    report = {
        "schema_version": SCHEMA_VERSION, "agent_id": agent_id, "policy_id": POLICY_ID,
        "repository": envelope.get("repository"), "commit_sha": envelope.get("commit_sha"),
        "tree_sha": envelope.get("tree_sha"), "policy_digest": envelope.get("policy_digest"),
        "invocation_id": envelope.get("invocation_id"), "producer_identity": envelope.get("producer_identity"),
        "issued_at_utc": envelope.get("issued_at_utc"), "expires_at_utc": envelope.get("expires_at_utc"),
        "authentication": {"status": "UNAUTHENTICATED", "method": None},
        "decision": decision, "checks": checks + envelope_problems,
        "findings": findings or [], "required_actions": required_actions or [],
    }
    report["report_sha256"] = sha256_hex(canonical_json(report))
    return report


class TeamAgent:
    agent_id = "team-base"

    def _report(self, envelope: Any, checks: list[dict[str, Any]],
                findings: list[dict[str, Any]] | None = None,
                actions: list[str] | None = None) -> dict[str, Any]:
        return make_report(self.agent_id, envelope if isinstance(envelope, dict) else {}, checks, findings, actions)


class AERAgent(TeamAgent):
    """Architecture, Engineering, and Reliability readiness evaluator."""
    agent_id = "aer"

    def assess(self, envelope: Any, inputs: Any) -> dict[str, Any]:
        if not isinstance(inputs, dict):
            return self._report(envelope, [{"id": "inputs", "status": UNKNOWN, "detail": "Assessment inputs missing."}])
        checks = []
        for key, label in (
            ("architecture_baseline_ref", "Versioned architecture baseline"),
            ("interface_contracts", "Interface contracts"),
            ("failure_mode_review", "Failure-mode and blast-radius review"),
            ("observability_baseline", "Observability baseline"),
            ("rollback_plan_ref", "Rollback or recovery plan"),
        ):
            ok = bool(inputs.get(key))
            checks.append({"id": key, "status": PASS if ok else BLOCK,
                           "detail": f"{label} supplied." if ok else f"{label} missing."})
        slos = inputs.get("slos")
        slo_ok = isinstance(slos, list) and bool(slos) and all(
            isinstance(x, dict) and x.get("service") and x.get("objective") and x.get("measurement_window") for x in slos)
        checks.append({"id": "slos", "status": PASS if slo_ok else BLOCK,
                       "detail": "Explicit measurable SLOs supplied." if slo_ok else "SLOs absent or missing service/objective/window."})
        risk_ok = inputs.get("unresolved_critical_risks") == []
        checks.append({"id": "critical_risks", "status": PASS if risk_ok else BLOCK,
                       "detail": "No unresolved critical risks reported." if risk_ok else "Critical-risk inventory missing or contains unresolved items."})
        return self._report(envelope, checks, actions=[] if all(c["status"] == PASS for c in checks) else
                            ["Resolve architecture/reliability gaps and reassess the exact revision."])


class RedTeamAgent(TeamAgent):
    """Scope-gated adversarial evidence evaluator; it never executes active tests."""
    agent_id = "red-team"

    def assess(self, envelope: Any, authorization_data: Any, test_results: Any,
               requested_targets: Any = None) -> dict[str, Any]:
        # Use a distinct parameter identifier so static redaction scanning does not
        # confuse a Python type annotation with an authorization header/secret.
        authorization = authorization_data
        auth_ok = isinstance(authorization, dict) and all(authorization.get(k) for k in (
            "authorization_id", "repository", "environment", "allowed_targets", "allowed_test_types",
            "start_at_utc", "end_at_utc", "approver_identity"))
        envelope_repo = envelope.get("repository") if isinstance(envelope, dict) else None
        auth_ok = bool(auth_ok and authorization.get("repository") == envelope_repo
                       and authorization.get("authenticated") is True
                       and _valid_timestamp(authorization.get("start_at_utc"))
                       and _valid_timestamp(authorization.get("end_at_utc")))
        allowed = authorization.get("allowed_targets") if isinstance(authorization, dict) else None
        allowed_ok = isinstance(allowed, list) and all(isinstance(t, str) and t for t in allowed)
        targets_ok = allowed_ok and isinstance(requested_targets, list) and bool(requested_targets) and all(
            isinstance(t, str) and t in allowed for t in requested_targets)
        checks = [
            {"id": "authorization", "status": PASS if auth_ok else BLOCK,
             "detail": "Authenticated, repository-bound authorization supplied." if auth_ok else "Authorization absent, unauthenticated, incomplete, or mismatched."},
            {"id": "target_allowlist", "status": PASS if auth_ok and targets_ok else BLOCK,
             "detail": "All requested targets are explicitly allowlisted." if auth_ok and targets_ok else "Target list absent or includes an out-of-scope target."},
            {"id": "active_execution", "status": UNKNOWN,
             "detail": "No active testing is executed by this report producer; offline/synthetic evidence only."},
        ]
        results_ok = isinstance(test_results, list) and bool(test_results) and all(
            isinstance(r, dict) and r.get("test_id") and r.get("result") in ("pass", "fail", "blocked")
            and isinstance(r.get("evidence_sha256"), str) and _SHA64.fullmatch(r["evidence_sha256"])
            for r in test_results)
        checks.append({"id": "synthetic_test_evidence", "status": PASS if results_ok else UNKNOWN,
                       "detail": "Well-formed synthetic test records supplied." if results_ok else "Synthetic test evidence absent or malformed."})
        findings = [{"severity": "high", "test_id": r["test_id"], "result": r["result"]}
                    for r in (test_results if isinstance(test_results, list) else [])
                    if isinstance(r, dict) and r.get("result") == "fail" and r.get("test_id")]
        return self._report(envelope, checks, findings,
                            ["Active tests require a separate approved isolated executor; this module never executes them."])


class BlueTeamAgent(TeamAgent):
    """Defensive telemetry and incident-response evidence evaluator."""
    agent_id = "blue-team"

    def assess(self, envelope: Any, telemetry: Any, scenarios: Any) -> dict[str, Any]:
        telemetry_ok = isinstance(telemetry, list) and bool(telemetry) and all(
            isinstance(t, dict) and t.get("source_id") and _valid_timestamp(t.get("observed_at_utc"))
            and isinstance(t.get("evidence_sha256"), str) and _SHA64.fullmatch(t["evidence_sha256"])
            for t in telemetry)
        checks = [{"id": "telemetry_evidence", "status": PASS if telemetry_ok else UNKNOWN,
                   "detail": "Timestamped, hashed telemetry records supplied." if telemetry_ok else "Telemetry missing or malformed."}]
        scenarios_ok = isinstance(scenarios, list) and bool(scenarios)
        if scenarios_ok:
            for s in scenarios:
                if not isinstance(s, dict) or not s.get("scenario_id"):
                    scenarios_ok = False
                    break
                if s.get("expected_detection") is True:
                    alert = s.get("alert")
                    if not isinstance(alert, dict) or not alert.get("alert_id") or not _valid_timestamp(alert.get("detected_at_utc")) or not isinstance(alert.get("evidence_sha256"), str) or not _SHA64.fullmatch(alert["evidence_sha256"]):
                        scenarios_ok = False
                        break
        checks.append({"id": "scenario_detection", "status": PASS if scenarios_ok else BLOCK,
                       "detail": "Required scenario outcomes include timestamped alert evidence." if scenarios_ok else "Scenario or required alert evidence missing/malformed."})
        return self._report(envelope, checks, actions=[] if all(c["status"] == PASS for c in checks) else
                            ["Collect source telemetry and recorded alert outcomes; do not infer detection from configuration alone."])


class GreenTeamAgent(TeamAgent):
    """Propose-only remediation evaluator; cannot approve or merge changes."""
    agent_id = "green-team"

    def assess(self, envelope: Any, remediation: Any) -> dict[str, Any]:
        required = ("finding_ids", "patch_ref", "regression_tests", "rollback_plan_ref",
                    "before_metrics", "after_metrics", "independent_reviewer")
        valid = isinstance(remediation, dict) and all(remediation.get(k) for k in required)
        author = remediation.get("author_identity") if isinstance(remediation, dict) else None
        reviewer = remediation.get("independent_reviewer") if isinstance(remediation, dict) else None
        self_approval = bool(author and reviewer and author == reviewer)
        auto_merge = isinstance(remediation, dict) and remediation.get("auto_merge") is True
        checks = [
            {"id": "remediation_package", "status": PASS if valid else BLOCK,
             "detail": "Patch, findings, tests, metrics, rollback, and reviewer are supplied." if valid else "Remediation package incomplete."},
            {"id": "no_self_approval", "status": BLOCK if self_approval else PASS,
             "detail": "Author cannot independently review their own change." if self_approval else "No self-approval detected in supplied identities."},
            {"id": "no_auto_merge", "status": BLOCK if auto_merge else PASS,
             "detail": "Automatic merge is prohibited." if auto_merge else "Auto-merge is not enabled by this evaluator."},
            {"id": "propose_only", "status": PASS, "detail": "This module only evaluates a proposal; it does not write or merge changes."},
        ]
        return self._report(envelope, checks, actions=[] if all(c["status"] == PASS for c in checks) else
                            ["Complete remediation evidence and obtain independent review; no agent may self-approve or auto-merge."])


class AuthenticatedTeamReportAdapter:
    """Read-only evidence adapter for canonical Release Assurance; never decides release."""
    def __init__(self, verifier: Callable[[dict[str, Any]], dict[str, Any]] | None = None):
        self.verifier = verifier

    def validate(self, reports: Any, repository: str, commit_sha: str, tree_sha: str,
                 policy_digest: str) -> dict[str, Any]:
        required = {"aer", "red-team", "blue-team", "green-team"}
        valid_reports = [r for r in reports if isinstance(r, dict)] if isinstance(reports, list) else []
        ids = [r.get("agent_id") for r in valid_reports]
        duplicate_ids = len(ids) != len(set(ids))
        by_id = {r.get("agent_id"): r for r in valid_reports}
        checks = []
        for agent_id in sorted(required):
            report = by_id.get(agent_id)
            binding_ok = isinstance(report, dict) and all(report.get(k) == v for k, v in (
                ("repository", repository), ("commit_sha", commit_sha), ("tree_sha", tree_sha),
                ("policy_digest", policy_digest), ("decision", PASS)))
            digest_ok = False
            if isinstance(report, dict) and isinstance(report.get("report_sha256"), str):
                body = {k: v for k, v in report.items() if k != "report_sha256"}
                digest_ok = bool(_SHA64.fullmatch(report["report_sha256"])) and sha256_hex(canonical_json(body)) == report["report_sha256"]
            authenticated = False
            if self.verifier and isinstance(report, dict):
                try:
                    result = self.verifier(report)
                    authenticated = isinstance(result, dict) and result.get("verified") is True and bool(result.get("signer_identity"))
                except Exception:
                    authenticated = False
            auth_status = report.get("authentication", {}).get("status") if isinstance(report, dict) and isinstance(report.get("authentication"), dict) else None
            ok = bool(binding_ok and digest_ok and authenticated and auth_status == "AUTHENTICATED" and not duplicate_ids)
            checks.append({"id": f"authenticated_{agent_id}", "status": PASS if ok else BLOCK,
                           "detail": "Report digest, exact binding, and trusted authentication verified." if ok else
                           "Missing, duplicate, unauthenticated, tampered, or mismatched team report."})
        return {"adapter_id": "authenticated-team-report-adapter", "repository": repository,
                "commit_sha": commit_sha, "tree_sha": tree_sha, "policy_digest": policy_digest,
                "checks": checks, "status": PASS if all(c["status"] == PASS for c in checks) else BLOCK,
                "release_decision": "NOT_MADE",
                "note": "Evidence only; canonical Release Assurance remains the sole release decision authority."}
