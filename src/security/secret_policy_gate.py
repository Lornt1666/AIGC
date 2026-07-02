from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SecretAccessRequest:
    secret_key: str
    phase: str
    agent: str
    reason: str
    approval_token: Optional[str] = None


class SecretAccessDenied(Exception):
    pass


class SecretPolicyGate:
    def validate(self, request: SecretAccessRequest, record: Dict[str, Any]) -> None:
        allowed_phases = set(record.get("allowed_phases", []))
        allowed_agents = set(record.get("allowed_agents", []))
        if request.phase not in allowed_phases:
            raise SecretAccessDenied(f"Phase not allowed to access secret: {request.phase}")
        if request.agent not in allowed_agents:
            raise SecretAccessDenied(f"Agent not allowed to access secret: {request.agent}")
        if record.get("approval_required", False) and not request.approval_token:
            raise SecretAccessDenied(f"Approval token required for secret: {request.secret_key}")
        if record.get("log_value", False):
            raise SecretAccessDenied("Secret manifest attempts to allow value logging.")
