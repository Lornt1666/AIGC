from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


DEFAULT_FORBIDDEN_WRITE_TERMS = {
    "apply",
    "submit",
    "message",
    "send",
    "bid",
    "post",
    "write",
    "upload",
    "delete",
    "patch",
    "contract",
    "invoice",
    "payment",
}


@dataclass(frozen=True)
class ConnectorPolicyResult:
    status: str
    maturity_level: str
    safety_status: str
    risk_flags: List[str] = field(default_factory=list)


class ConnectorPolicyGate:
    def __init__(
        self,
        forbidden_write_terms: List[str] | None = None,
        allowed_read_only_actions: List[str] | None = None,
        maturity_levels: Dict[str, str] | None = None,
    ):
        self.forbidden_write_terms = {
            term.lower() for term in (forbidden_write_terms or sorted(DEFAULT_FORBIDDEN_WRITE_TERMS))
        }
        self.allowed_read_only_actions = {
            action.lower() for action in (allowed_read_only_actions or [])
        }
        self.maturity_levels = maturity_levels or {
            "enabled_read_only": "read_only_validated",
            "disabled_reference": "configured_reference_only",
            "needs_review": "needs_connector_review",
            "blocked": "blocked_by_connector_policy",
        }

    def inspect(self, record: Dict[str, Any]) -> ConnectorPolicyResult:
        risk_flags: List[str] = []
        enabled = bool(record.get("enabled", False))
        allowed_actions = [str(action) for action in record.get("allowed_actions", [])]
        write_like = [
            action for action in allowed_actions
            if self._looks_like_write_action(action)
        ]
        if write_like:
            risk_flags.append("allowed_actions_contain_write_like_capability")
        if record.get("external_write_allowed"):
            risk_flags.append("external_write_allowed_must_remain_false")
        if record.get("live_execution_allowed"):
            risk_flags.append("live_execution_allowed_must_remain_false")
        if not record.get("read_only", False):
            risk_flags.append("connector_not_marked_read_only")
        if record.get("external_action_performed"):
            risk_flags.append("external_action_performed_must_remain_false")
        if bool(record.get("requires_secret", False)) and enabled and not record.get("secret_key"):
            risk_flags.append("enabled_secret_connector_missing_secret_key")

        blocking_flags = {
            "allowed_actions_contain_write_like_capability",
            "external_write_allowed_must_remain_false",
            "live_execution_allowed_must_remain_false",
            "connector_not_marked_read_only",
            "external_action_performed_must_remain_false",
            "enabled_secret_connector_missing_secret_key",
        }
        if any(flag in blocking_flags for flag in risk_flags):
            return ConnectorPolicyResult(
                status="blocked",
                maturity_level=self.maturity_levels["blocked"],
                safety_status="blocked",
                risk_flags=risk_flags,
            )
        if not enabled:
            if bool(record.get("requires_secret", False)):
                risk_flags.append("disabled_secret_connector_reference_only")
            return ConnectorPolicyResult(
                status="disabled_reference_only",
                maturity_level=self.maturity_levels["disabled_reference"],
                safety_status="caution" if risk_flags else "cleared",
                risk_flags=risk_flags,
            )
        return ConnectorPolicyResult(
            status="ready_read_only",
            maturity_level=self.maturity_levels["enabled_read_only"],
            safety_status="cleared",
            risk_flags=risk_flags,
        )

    def _looks_like_write_action(self, action: str) -> bool:
        clean = action.lower().replace("-", "_")
        if clean in self.allowed_read_only_actions:
            return False
        return any(term in clean.split("_") or term in clean for term in self.forbidden_write_terms)
