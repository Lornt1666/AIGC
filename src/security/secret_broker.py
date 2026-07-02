from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .google_secret_manager import GoogleSecretManagerClient
    from .secret_audit_ledger import SecretAuditLedger
    from .secret_policy_gate import SecretAccessDenied, SecretAccessRequest, SecretPolicyGate
except ImportError:  # pragma: no cover - direct script fallback
    from google_secret_manager import GoogleSecretManagerClient
    from secret_audit_ledger import SecretAuditLedger
    from secret_policy_gate import SecretAccessDenied, SecretAccessRequest, SecretPolicyGate


class SecretBroker:
    """
    Policy-controlled secret retrieval.

    The broker reads secret references from a manifest, validates phase/agent/approval
    policy, and can retrieve from Google Cloud Secret Manager only when live retrieval
    is explicitly enabled. Secret values are never logged.
    """

    def __init__(
        self,
        manifest_path: Path,
        audit_log_path: Path,
        enable_live_retrieval: bool = False,
        google_client: Optional[GoogleSecretManagerClient] = None,
        approval_token_store_path: Optional[Path] = None,
    ):
        self.manifest_path = manifest_path
        self.audit = SecretAuditLedger(audit_log_path)
        self.policy = SecretPolicyGate(approval_token_store_path=approval_token_store_path)
        self.enable_live_retrieval = enable_live_retrieval
        self.google_client = google_client
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self._validate_manifest_rules()

    def get_secret(self, request: SecretAccessRequest) -> str:
        secrets = self.manifest.get("secrets", {})
        if request.secret_key not in secrets:
            self._audit("denied_unknown_secret", request, {})
            raise SecretAccessDenied(f"Unknown secret key: {request.secret_key}")
        record = secrets[request.secret_key]
        try:
            self.policy.validate(request, record)
        except SecretAccessDenied as exc:
            self._audit("denied_policy_check", request, {"reason": str(exc)})
            raise
        if not self.enable_live_retrieval:
            self._audit("denied_live_retrieval_disabled", request, {
                "resource": record.get("resource", ""),
                "purpose": record.get("purpose", ""),
                "risk_level": record.get("risk_level", ""),
            })
            raise SecretAccessDenied("Live secret retrieval is disabled for this runtime.")
        client = self.google_client or GoogleSecretManagerClient()
        secret_value = client.access_secret(record["resource"])
        self._audit("secret_access_granted", request, {
            "resource": record.get("resource", ""),
            "purpose": record.get("purpose", ""),
            "risk_level": record.get("risk_level", ""),
            "secret_value_logged": False,
        })
        return secret_value

    def _audit(self, event_type: str, request: SecretAccessRequest, metadata: Dict[str, Any]) -> None:
        self.audit.record(event_type, {
            "secret_key": request.secret_key,
            "phase": request.phase,
            "agent": request.agent,
            "reason": request.reason,
            "metadata": metadata,
        })

    def _validate_manifest_rules(self) -> None:
        if self.manifest.get("store_raw_values", False):
            raise SecretAccessDenied("Manifest attempts to allow raw secret storage.")
        rules = self.manifest.get("rules", {}) or {}
        forbidden_true_rules = [
            "store_raw_secret_values_on_external_drive",
            "store_raw_secret_values_in_repo",
            "log_secret_values",
            "print_secret_values",
            "include_secret_values_in_prompts",
            "include_secret_values_in_employer_packets",
        ]
        for rule_name in forbidden_true_rules:
            if rules.get(rule_name, False):
                raise SecretAccessDenied(f"Unsafe manifest rule enabled: {rule_name}")
        service_account_policy = self.manifest.get("service_account_key_policy", {}) or {}
        for rule_name in [
            "store_service_account_key_json_in_repo",
            "store_service_account_key_json_on_external_drive",
            "store_service_account_key_json_in_secret_manager",
        ]:
            if service_account_policy.get(rule_name, False):
                raise SecretAccessDenied(f"Unsafe service account key policy enabled: {rule_name}")
