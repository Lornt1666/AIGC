"""Autonomous next-steps coordinator for AIGC release readiness.

Safe-by-default policy engine. It may autonomously gather/validate evidence and
prepare review packets through explicitly registered adapters. It never merges,
deploys, releases, approves itself, changes release authority, or grants access.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

AGENT_ID = "release_readiness_next_steps_coordinator"
CONTRACT_VERSION = "aigc-next-steps/1.0"
CANONICAL_RELEASE_AUTHORITY = "Release Assurance Agent"

AUTO_ACTIONS = frozenset({
    "inspect_exact_head_ci",
    "verify_artifact_binding",
    "run_reference_tests",
    "analyze_gate_evidence",
    "prepare_independent_review_packet",
})
PROHIBITED_ACTIONS = frozenset({
    "merge", "deploy", "release", "approve_release", "self_approve",
    "change_release_authority", "grant_privileges", "change_branch_protection",
    "sign_with_private_key", "spend_funds", "external_contact",
})


@dataclass(frozen=True)
class GateEvidence:
    """A normalized evidence claim; unknown/missing evidence is never a pass."""
    exact_commit: str
    ci: str = "UNKNOWN"
    artifact_binding: str = "UNKNOWN"
    specification: str = "UNKNOWN"
    security_review: str = "UNKNOWN"
    isolated_deployment: str = "UNKNOWN"
    operational_acceptance: str = "UNKNOWN"
    human_acceptance: str = "UNKNOWN"
    release_assurance: str = "UNKNOWN"
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if len(self.exact_commit) != 40 or any(c not in "0123456789abcdef" for c in self.exact_commit.lower()):
            raise ValueError("exact_commit must be a full 40-character Git SHA")
        allowed = {"PASS", "FAIL", "UNKNOWN", "PENDING", "NOT_APPLICABLE"}
        for name in ("ci", "artifact_binding", "specification", "security_review",
                     "isolated_deployment", "operational_acceptance", "human_acceptance",
                     "release_assurance"):
            if getattr(self, name) not in allowed:
                raise ValueError(f"invalid status for {name}")
        if any(not isinstance(ref, str) or not ref.strip() for ref in self.evidence_refs):
            raise ValueError("evidence references must be non-empty strings")


@dataclass(frozen=True)
class PlannedAction:
    action: str
    reason: str
    requires_human: bool = False


@dataclass
class Coordinator:
    """Deterministic planner plus allowlisted action runner; no implicit tools."""
    handlers: Mapping[str, Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]] = field(default_factory=dict)
    event_log: list[dict[str, Any]] = field(default_factory=list)
    _last_hash: str = "0" * 64

    def plan(self, evidence: GateEvidence) -> list[PlannedAction]:
        evidence.validate()
        actions: list[PlannedAction] = []
        if evidence.ci != "PASS":
            actions.append(PlannedAction("inspect_exact_head_ci", "CI is not proven PASS for this exact commit."))
        if evidence.artifact_binding != "PASS":
            actions.append(PlannedAction("verify_artifact_binding", "Artifact-to-commit/tree binding is unverified."))
        if evidence.specification != "PASS":
            actions.append(PlannedAction("analyze_gate_evidence", "Specification, contracts, topology, or FMEA needs verification."))
        if evidence.security_review != "PASS":
            actions.append(PlannedAction("analyze_gate_evidence", "Independent security review is not accepted."))
        if evidence.isolated_deployment != "PASS":
            actions.append(PlannedAction("analyze_gate_evidence", "Isolated deployment has not been evidenced and accepted."))
        if evidence.operational_acceptance != "PASS":
            actions.append(PlannedAction("run_reference_tests", "Operational acceptance evidence is incomplete."))
        if evidence.human_acceptance != "PASS":
            actions.append(PlannedAction("prepare_independent_review_packet", "Human acceptance is outstanding.", True))
        if evidence.release_assurance != "PASS":
            actions.append(PlannedAction("prepare_independent_review_packet", "Canonical Release Assurance decision is outstanding.", True))
        # Preserve order while removing duplicate actions; combine reasons deterministically.
        combined: dict[str, list[PlannedAction]] = {}
        for action in actions:
            combined.setdefault(action.action, []).append(action)
        return [
            PlannedAction(name, " ".join(item.reason for item in items),
                          any(item.requires_human for item in items))
            for name, items in combined.items()
        ]

    def _record(self, event: Mapping[str, Any]) -> None:
        base = {"sequence": len(self.event_log) + 1, "time_unix": int(time.time()),
                "previous_hash": self._last_hash, **dict(event)}
        canonical = json.dumps(base, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        base["event_hash"] = digest
        self.event_log.append(base)
        self._last_hash = digest

    async def execute(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Execute only registered auto-actions; all unknown/privileged actions fail closed."""
        if action in PROHIBITED_ACTIONS or action not in AUTO_ACTIONS:
            self._record({"event": "ACTION_BLOCKED", "action": action, "reason": "not in autonomous allowlist"})
            raise PermissionError(f"autonomous action blocked: {action}")
        handler = self.handlers.get(action)
        if handler is None:
            self._record({"event": "ACTION_BLOCKED", "action": action, "reason": "no registered handler"})
            raise PermissionError(f"no registered handler for: {action}")
        # A payload is data, not authority. Do not accept an action override from it.
        started = time.monotonic()
        self._record({"event": "ACTION_STARTED", "action": action})
        try:
            result = await asyncio.wait_for(handler(dict(payload)), timeout=30.0)
            if not isinstance(result, Mapping):
                raise TypeError("action handler must return a mapping")
            safe = dict(result)
            for forbidden in ("approved", "release_decision", "deployment_authority",
                              "grant_privileges", "merge_authority", "canonical_release_authority"):
                safe.pop(forbidden, None)
            self._record({"event": "ACTION_COMPLETED", "action": action,
                          "elapsed_ms": int((time.monotonic() - started) * 1000)})
            return {"status": "COMPLETED", "action": action, "result": safe}
        except asyncio.TimeoutError:
            self._record({"event": "ACTION_TIMEOUT", "action": action})
            raise
        except Exception as exc:
            self._record({"event": "ACTION_FAILED", "action": action,
                          "error_type": type(exc).__name__})
            raise

    def readiness(self, evidence: GateEvidence) -> dict[str, Any]:
        evidence.validate()
        plan = self.plan(evidence)
        gates = {
            "ci": evidence.ci, "artifact_binding": evidence.artifact_binding,
            "specification": evidence.specification, "security_review": evidence.security_review,
            "isolated_deployment": evidence.isolated_deployment,
            "operational_acceptance": evidence.operational_acceptance,
            "human_acceptance": evidence.human_acceptance, "release_assurance": evidence.release_assurance,
        }
        release_eligible = all(v == "PASS" for v in gates.values())
        return {
            "agent_id": AGENT_ID, "contract_version": CONTRACT_VERSION,
            "exact_commit": evidence.exact_commit, "gates": gates,
            "release_eligible": release_eligible,
            "decision": "ELIGIBLE_FOR_CANONICAL_REVIEW" if release_eligible else "BLOCK",
            "canonical_release_authority": CANONICAL_RELEASE_AUTHORITY,
            "planned_actions": [a.__dict__ for a in plan],
            "event_count": len(self.event_log),
            "limits": ["planner output is advisory", "release decision belongs only to canonical Release Assurance Agent",
                       "production requires independent review and explicit human acceptance"],
        }
