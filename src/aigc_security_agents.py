"""Executable, independently testable AIGC security assurance agents.

These agents are deterministic policy evaluators. They do not authenticate to GitHub,
run scanners, verify signatures, or perform privileged actions themselves. Production
adapters must supply authoritative observations and real verifier outputs.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

SCHEMA_VERSION = "1.0"
AGENT_VERSION = "0.1.0"
POLICY_VERSION = "aigc-security-baseline-1"
PASS = "PASS"
BLOCK = "BLOCK"
UNKNOWN = "UNKNOWN"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _report(agent_id: str, repository: str, commit_sha: str, checks: list[dict[str, Any]],
            findings: list[dict[str, Any]] | None = None,
            required_actions: list[str] | None = None) -> dict[str, Any]:
    decision = PASS if checks and all(c.get("status") == PASS for c in checks) else BLOCK
    report = {
        "schema_version": SCHEMA_VERSION,
        "agent_id": agent_id,
        "agent_version": AGENT_VERSION,
        "policy_version": POLICY_VERSION,
        "repository": repository,
        "commit_sha": commit_sha,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "checks": checks,
        "findings": findings or [],
        "required_actions": required_actions or [],
    }
    report["evidence_digest"] = _digest({k: v for k, v in report.items() if k != "evidence_digest"})
    return report


class GitHubProtectorAgent:
    """Evaluate a caller-supplied authoritative repository-settings snapshot."""

    agent_id = "github-protector"

    def assess(self, snapshot: dict[str, Any] | None, repository: str, commit_sha: str) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        actions: list[str] = []
        if not isinstance(snapshot, dict) or snapshot.get("read_status") != "OK":
            checks.append({"id": "settings_readback", "status": UNKNOWN,
                           "detail": "Authoritative settings snapshot absent or unreadable."})
            actions.append("Have an authorized administrator read back effective repository settings.")
            return _report(self.agent_id, repository, commit_sha, checks, required_actions=actions)

        rulesets = snapshot.get("rulesets")
        if not isinstance(rulesets, list):
            checks.append({"id": "rulesets_schema", "status": UNKNOWN, "detail": "Rulesets missing or malformed."})
        else:
            active = [r for r in rulesets if isinstance(r, dict) and r.get("enforcement") == "active"]
            branch_ok = any(
                r.get("target") == "branch"
                and r.get("enforcement") == "active"
                and "refs/heads/main" in ((r.get("conditions") or {}).get("ref_name") or {}).get("include", [])
                and self._required_branch_rules(r)
                and not r.get("bypass_actors")
                for r in active
            )
            tag_pattern = snapshot.get("release_tag_pattern")
            tag_ok = bool(tag_pattern) and any(
                r.get("target") == "tag"
                and r.get("enforcement") == "active"
                and f"refs/tags/{tag_pattern}" in ((r.get("conditions") or {}).get("ref_name") or {}).get("include", [])
                and self._required_tag_rules(r)
                and not r.get("bypass_actors")
                for r in active
            )
            checks.append({"id": "main_ruleset", "status": PASS if branch_ok else BLOCK,
                           "detail": "Active main ruleset has required rules and no bypass actors." if branch_ok else "Required main ruleset or zero-bypass policy not verified."})
            checks.append({"id": "release_tag_ruleset", "status": PASS if tag_ok else BLOCK,
                           "detail": "Active tag ruleset matches declared pattern and blocks mutation/deletion." if tag_ok else "Release tag pattern/rules/bypass are not verified."})
            if not branch_ok:
                actions.append("Configure and verify a main ruleset requiring PR reviews, required checks, and no unapproved bypass.")
            if not tag_ok:
                actions.append("Confirm the actual release-tag pattern and configure/read back tag mutation/deletion protection.")
        protection = snapshot.get("branch_protection")
        protection_ok = (
            isinstance(protection, dict)
            and protection.get("read_status") == "OK"
            and protection.get("required_approving_review_count", 0) >= 1
            and bool(protection.get("required_status_checks"))
            and protection.get("allow_force_pushes") is False
            and protection.get("allow_deletions") is False
            and protection.get("enforce_admins") is True
        )
        checks.append({"id": "branch_protection_readback", "status": PASS if protection_ok else BLOCK,
                       "detail": "Legacy branch protection read-back meets baseline." if protection_ok else "Branch protection read-back incomplete or below baseline."})
        if not protection_ok:
            actions.append("Read back and test review/check requirements, admin enforcement, force-push and deletion restrictions.")
        return _report(self.agent_id, repository, commit_sha, checks, required_actions=actions)

    @staticmethod
    def _required_branch_rules(rule: dict[str, Any]) -> bool:
        types = {r.get("type") for r in rule.get("rules", []) if isinstance(r, dict)}
        return {"pull_request", "required_status_checks", "required_signatures"}.issubset(types) or {
            "pull_request", "required_status_checks"
        }.issubset(types)

    @staticmethod
    def _required_tag_rules(rule: dict[str, Any]) -> bool:
        types = {r.get("type") for r in rule.get("rules", []) if isinstance(r, dict)}
        return "deletion" in types and "update" in types


class CybersecurityAgent:
    """Evaluate real security-check records bound to a single exact revision."""

    agent_id = "cybersecurity"

    def assess(self, check_results: list[dict[str, Any]] | None, repository: str,
               commit_sha: str) -> dict[str, Any]:
        required = {"workflow_permissions", "action_pinning", "secret_scan", "dependency_scan",
                    "static_analysis", "adversarial_tests"}
        by_id = {c.get("id"): c for c in check_results or [] if isinstance(c, dict) and c.get("id")}
        checks = []
        findings = []
        actions = []
        for check_id in sorted(required):
            result = by_id.get(check_id)
            status = UNKNOWN
            detail = "No result supplied."
            if isinstance(result, dict):
                if result.get("commit_sha") != commit_sha:
                    status, detail = BLOCK, "Result is not bound to the exact requested commit SHA."
                elif result.get("executed") is not True or not result.get("run_id") or not result.get("evidence_sha256"):
                    status, detail = UNKNOWN, "Actual execution metadata or evidence digest is missing."
                elif result.get("conclusion") == "success":
                    status, detail = PASS, "Executed result is bound to the exact requested commit."
                else:
                    status, detail = BLOCK, f"Check conclusion is {result.get('conclusion')!r}."
            checks.append({"id": check_id, "status": status, "detail": detail,
                           "run_id": result.get("run_id") if isinstance(result, dict) else None})
            if status != PASS:
                findings.append({"severity": "high" if status == BLOCK else "unknown",
                                 "check_id": check_id, "detail": detail})
                actions.append(f"Run and preserve a real {check_id} result for exact commit {commit_sha}.")
        return _report(self.agent_id, repository, commit_sha, checks, findings, actions)


class TrustworthinessAssessmentAgent:
    """Call an injected real verifier; absence of a verifier is never a pass."""

    agent_id = "trustworthiness-assessment"

    def __init__(self, verifier: Callable[[dict[str, Any]], dict[str, Any]] | None = None):
        self.verifier = verifier

    def assess(self, evidence_items: list[dict[str, Any]] | None, repository: str,
               commit_sha: str) -> dict[str, Any]:
        if not self.verifier:
            return _report(self.agent_id, repository, commit_sha, [
                {"id": "trusted_verifier_available", "status": UNKNOWN,
                 "detail": "No cryptographic verifier adapter configured."}
            ], required_actions=["Configure an approved signature/provenance verifier; do not accept self-reported validity."])
        checks = []
        actions = []
        required_kinds = {"canonical_receipt_bundle", "release_artifact"}
        items = [x for x in evidence_items or [] if isinstance(x, dict)]
        for kind in sorted(required_kinds):
            item = next((x for x in items if x.get("kind") == kind), None)
            if not item:
                checks.append({"id": f"attestation_{kind}", "status": UNKNOWN, "detail": "Required attested subject absent."})
                actions.append(f"Produce and verify a separate attestation for {kind}.")
                continue
            try:
                result = self.verifier(item)
            except Exception as exc:
                result = {"verified": False, "error": type(exc).__name__}
            exact_binding = (
                item.get("repository") == repository
                and item.get("commit_sha") == commit_sha
                and isinstance(item.get("subject_sha256"), str)
                and len(item["subject_sha256"]) == 64
                and all(ch in "0123456789abcdef" for ch in item["subject_sha256"])
            )
            verified = result.get("verified") is True and exact_binding
            checks.append({
                "id": f"attestation_{kind}",
                "status": PASS if verified else BLOCK,
                "detail": "Verifier accepted evidence and exact subject binding." if verified else "Signature/provenance verification or exact subject binding failed.",
                "verifier_result": {k: result.get(k) for k in ("verified", "reason", "workflow_identity", "predicate_type") if k in result},
                "subject_sha256": item.get("subject_sha256"),
            })
            if not verified:
                actions.append(f"Resolve signature, identity, revision, or digest verification for {kind}.")
        return _report(self.agent_id, repository, commit_sha, checks, required_actions=actions)


class ReleaseAssuranceAgent:
    """Sole policy aggregator; never creates evidence or performs release actions."""

    agent_id = "release-assurance"

    def decide(self, reports: list[dict[str, Any]], repository: str, commit_sha: str) -> dict[str, Any]:
        required_agents = {"github-protector", "cybersecurity", "trustworthiness-assessment"}
        seen = {r.get("agent_id"): r for r in reports if isinstance(r, dict)}
        checks = []
        for agent_id in sorted(required_agents):
            report = seen.get(agent_id)
            valid = (
                isinstance(report, dict)
                and report.get("repository") == repository
                and report.get("commit_sha") == commit_sha
                and report.get("decision") == PASS
                and bool(report.get("evidence_digest"))
                and isinstance(report.get("checks"), list)
                and bool(report["checks"])
                and all(c.get("status") == PASS for c in report["checks"] if isinstance(c, dict))
                and all(isinstance(c, dict) for c in report["checks"])
            )
            checks.append({"id": f"agent_report_{agent_id}", "status": PASS if valid else BLOCK,
                           "detail": "Valid PASS report bound to exact repository/revision." if valid else "Missing, failed, malformed, or mismatched agent report."})
        return _report(self.agent_id, repository, commit_sha, checks,
                       required_actions=[] if all(c["status"] == PASS for c in checks) else
                       ["Keep release BLOCK until all three agents provide valid PASS reports for the exact revision."])
