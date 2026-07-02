from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from src.security.approval_tokens import ApprovalTokenError, ApprovalTokenStore


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
    def __init__(self, approval_token_store_path: Path | None = None):
        self.approval_token_store_path = approval_token_store_path

    def validate(self, request: SecretAccessRequest, record: Dict[str, Any]) -> None:
        allowed_phases = set(record.get("allowed_phases", []))
        allowed_agents = set(record.get("allowed_agents", []))
        if request.phase not in allowed_phases:
            raise SecretAccessDenied(f"Phase not allowed to access secret: {request.phase}")
        if request.agent not in allowed_agents:
            raise SecretAccessDenied(f"Agent not allowed to access secret: {request.agent}")
        if record.get("approval_required", False) and not request.approval_token:
            raise SecretAccessDenied(f"Approval token required for secret: {request.secret_key}")
        if record.get("approval_required", False) and self.approval_token_store_path:
            scope = record.get("approval_token_scope") or f"secret:{request.secret_key}"
            try:
                ApprovalTokenStore(self.approval_token_store_path).validate_token(
                    token=request.approval_token or "",
                    required_scope=scope,
                    phase=request.phase,
                    mark_used=True,
                )
            except ApprovalTokenError as exc:
                raise SecretAccessDenied(str(exc)) from exc
        if record.get("log_value", False):
            raise SecretAccessDenied("Secret manifest attempts to allow value logging.")
