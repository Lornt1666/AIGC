"""Minimal, fail-closed AIGC runtime primitives; no external side effects are performed here.

This module is an executable policy boundary, not a production orchestration service.
Adapters must call authorize_tool immediately before the real tool invocation and must
retain the returned decision/event with the invocation's immutable evidence manifest.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Callable, Iterable, Mapping

CONTRACT_VERSION = "aigc.task/1.0"
RUNTIME_VERSION = "aigc.runtime/0.1.0"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ALLOWED_STATUSES = {"SUCCEEDED", "PARTIAL", "BLOCKED", "FAILED", "UNKNOWN"}


class GovernanceError(ValueError):
    """Raised when a contract, permit, or workflow transition is invalid."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise GovernanceError("timestamp_must_be_utc_z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise GovernanceError("timestamp_malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise GovernanceError("timestamp_must_be_utc")
    return parsed


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    project_id: str
    agent_id: str
    agent_version: str
    policy_version: str
    objective: str
    scope: tuple[str, ...]
    exclusions: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    risk_tier: str
    input_refs: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    permitted_side_effects: tuple[str, ...]
    contract_version: str = CONTRACT_VERSION

    def validate(self, known_agent_ids: Iterable[str] | None = None) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise GovernanceError("unsupported_task_contract_version")
        for name in ("task_id", "project_id", "agent_id", "agent_version", "policy_version", "objective", "risk_tier"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise GovernanceError("required_field_empty:" + name)
        if not ID_RE.fullmatch(self.task_id) or not ID_RE.fullmatch(self.agent_id):
            raise GovernanceError("identifier_malformed")
        if known_agent_ids is not None and self.agent_id not in set(known_agent_ids):
            raise GovernanceError("unknown_agent")
        for name in ("scope", "exclusions", "acceptance_criteria", "input_refs", "allowed_tools", "permitted_side_effects"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or any(not isinstance(x, str) or not x.strip() for x in values):
                raise GovernanceError("list_field_malformed:" + name)
        if not self.scope or not self.acceptance_criteria:
            raise GovernanceError("scope_and_acceptance_criteria_required")
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise GovernanceError("duplicate_allowed_tool")
        if self.risk_tier not in {"R0", "R1", "R2", "R3", "R4"}:
            raise GovernanceError("unknown_risk_tier")


@dataclass(frozen=True)
class ToolPermit:
    permit_id: str
    task_id: str
    agent_id: str
    tool_name: str
    action: str
    resource: str
    policy_version: str
    issued_at: str
    expires_at: str
    max_uses: int = 1
    human_approval_ref: str | None = None

    def validate(self, now: datetime) -> None:
        for name in ("permit_id", "task_id", "agent_id", "tool_name", "action", "resource", "policy_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise GovernanceError("permit_field_empty:" + name)
        issued, expires = parse_utc(self.issued_at), parse_utc(self.expires_at)
        if expires <= issued:
            raise GovernanceError("permit_expiry_must_follow_issue")
        if now.tzinfo is None or now.utcoffset() is None:
            raise GovernanceError("current_time_must_be_timezone_aware")
        if now.astimezone(timezone.utc) < issued:
            raise GovernanceError("permit_not_yet_valid")
        if now.astimezone(timezone.utc) >= expires:
            raise GovernanceError("permit_expired")
        if isinstance(self.max_uses, bool) or not isinstance(self.max_uses, int) or self.max_uses < 1:
            raise GovernanceError("permit_max_uses_invalid")
        if self.human_approval_ref is not None and not self.human_approval_ref.strip():
            raise GovernanceError("human_approval_reference_empty")


class AuditLedger:
    """In-memory append-only event list for tests/prototypes; not durable evidence storage."""
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def append(self, event_type: str, payload: Mapping[str, Any], at: str) -> str:
        event = {"sequence": len(self._events) + 1, "event_type": event_type, "at": at, "payload": dict(payload)}
        event["event_id"] = sha256_digest(event)
        self._events.append(event)
        return event["event_id"]

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(event) for event in self._events)


class PermitBroker:
    """Deny-by-default permit evaluator. It does not itself execute tools."""
    def __init__(self, ledger: AuditLedger, enabled_agent_ids: Iterable[str] = ()) -> None:
        self.ledger = ledger
        self.enabled_agent_ids = frozenset(enabled_agent_ids)
        self._uses: dict[str, int] = {}

    def authorize(
        self,
        *,
        contract: TaskContract,
        permit: ToolPermit | None,
        tool_name: str,
        action: str,
        resource: str,
        policy_version: str,
        now: datetime,
    ) -> dict[str, Any]:
        reason = "permit_missing"
        try:
            contract.validate()
            if contract.agent_id not in self.enabled_agent_ids:
                raise GovernanceError("agent_not_enabled")
            if tool_name not in contract.allowed_tools:
                raise GovernanceError("tool_not_in_task_contract")
            if permit is None:
                raise GovernanceError("permit_missing")
            permit.validate(now)
            if permit.task_id != contract.task_id or permit.agent_id != contract.agent_id:
                raise GovernanceError("permit_subject_mismatch")
            if (permit.tool_name, permit.action, permit.resource) != (tool_name, action, resource):
                raise GovernanceError("permit_scope_mismatch")
            if permit.policy_version != policy_version or contract.policy_version != policy_version:
                raise GovernanceError("policy_version_mismatch")
            if permit.permit_id in self._uses and self._uses[permit.permit_id] >= permit.max_uses:
                raise GovernanceError("permit_use_limit_exceeded")
            self._uses[permit.permit_id] = self._uses.get(permit.permit_id, 0) + 1
            reason = "authorized"
            allowed = True
        except GovernanceError as exc:
            reason = str(exc)
            allowed = False
        timestamp = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        event_id = self.ledger.append("tool_permit_decision", {
            "task_id": contract.task_id,
            "agent_id": contract.agent_id,
            "tool_name": tool_name,
            "action": action,
            "resource_digest": sha256_digest(resource),
            "policy_version": policy_version,
            "allowed": allowed,
            "reason": reason,
        }, timestamp)
        return {"allowed": allowed, "reason": reason, "audit_event_id": event_id}


class WorkflowState:
    """Small deterministic state machine; repeated event IDs are idempotently ignored."""
    TRANSITIONS = {
        "NEW": {"VALIDATED", "BLOCKED"},
        "VALIDATED": {"RUNNING", "BLOCKED"},
        "RUNNING": {"SUCCEEDED", "PARTIAL", "BLOCKED", "FAILED", "UNKNOWN"},
        "PARTIAL": {"RUNNING", "BLOCKED"},
        "UNKNOWN": {"BLOCKED", "RUNNING"},
        "SUCCEEDED": set(), "BLOCKED": set(), "FAILED": set(),
    }

    def __init__(self, task_id: str, ledger: AuditLedger) -> None:
        if not task_id or not ID_RE.fullmatch(task_id):
            raise GovernanceError("task_id_malformed")
        self.task_id = task_id
        self.status = "NEW"
        self._seen_event_ids: set[str] = set()
        self.ledger = ledger

    def transition(self, new_status: str, *, event_id: str, reason: str, at: str) -> dict[str, Any]:
        if not event_id or not reason:
            raise GovernanceError("transition_event_id_and_reason_required")
        if event_id in self._seen_event_ids:
            return {"status": self.status, "duplicate": True}
        if new_status not in self.TRANSITIONS.get(self.status, set()):
            raise GovernanceError("invalid_transition:" + self.status + "->" + str(new_status))
        previous = self.status
        self.status = new_status
        self._seen_event_ids.add(event_id)
        audit_id = self.ledger.append("workflow_transition", {
            "task_id": self.task_id, "from": previous, "to": new_status,
            "cause_event_id": event_id, "reason": reason,
        }, at)
        return {"status": self.status, "duplicate": False, "audit_event_id": audit_id}


def evaluate_cases(cases: Iterable[Mapping[str, Any]], evaluator) -> dict[str, Any]:
    """Run deterministic local cases; evaluator must be pure and must not invoke tools."""
    ordered = sorted((dict(case) for case in cases), key=lambda c: str(c.get("case_id", "")))
    ids = [c.get("case_id") for c in ordered]
    if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
        raise GovernanceError("evaluation_case_ids_missing_or_duplicate")
    results = []
    for case in ordered:
        observed = evaluator(dict(case))
        passed = observed == case.get("expected")
        results.append({"case_id": case["case_id"], "expected": case.get("expected"), "observed": observed, "passed": passed})
    summary = {
        "runtime_version": RUNTIME_VERSION,
        "case_count": len(results),
        "passed_count": sum(1 for r in results if r["passed"]),
        "failed_count": sum(1 for r in results if not r["passed"]),
        "results": results,
    }
    summary["evidence_digest"] = sha256_digest(summary)
    return summary
