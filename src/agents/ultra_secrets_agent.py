from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from src.security.redaction_scanner import RedactionFinding, RedactionScanner
from src.security.redactor import Redactor
from src.security.secret_broker import SecretBroker
from src.security.secret_policy_gate import SecretAccessRequest


@dataclass
class ManifestValidationResult:
    valid: bool
    issues: List[str]
    secret_count: int


class UltraSecretsAgent:
    """
    Ultra-layer credential guardian.

    This agent validates manifests, routes access through Secret Broker, scans for
    secret-like content, and refuses policies that would log or store raw values.
    """

    RAW_VALUE_FIELDS = {
        "value",
        "raw_value",
        "secret_value",
        "api_key",
        "password",
        "token",
        "private_key",
    }

    def __init__(self, manifest_path: Path, audit_log_path: Path, enable_live_retrieval: bool = False):
        self.manifest_path = manifest_path
        self.audit_log_path = audit_log_path
        self.redactor = Redactor()
        self.scanner = RedactionScanner(self.redactor)
        self.enable_live_retrieval = enable_live_retrieval

    def load_manifest(self) -> Dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def validate_manifest(self) -> ManifestValidationResult:
        issues: List[str] = []
        manifest = self.load_manifest()
        if manifest.get("store_raw_values", False):
            issues.append("Manifest attempts to allow raw secret storage.")
        rules = manifest.get("rules", {}) or {}
        required_false_rules = [
            "store_raw_secret_values_on_external_drive",
            "store_raw_secret_values_in_repo",
            "log_secret_values",
            "print_secret_values",
            "include_secret_values_in_prompts",
            "include_secret_values_in_employer_packets",
        ]
        for rule_name in required_false_rules:
            if rules.get(rule_name, False):
                issues.append(f"Manifest rule must be false: {rule_name}")
        if rules and not rules.get("secret_values_runtime_only", False):
            issues.append("Manifest must require runtime-only secret values.")
        kms_policy = manifest.get("kms_policy", {}) or {}
        if kms_policy and not kms_policy.get("not_for_general_password_or_api_secret_storage", False):
            issues.append("KMS policy must state that KMS is not the general secret-value store.")
        service_account_policy = manifest.get("service_account_key_policy", {}) or {}
        forbidden_service_account_storage = [
            "store_service_account_key_json_in_repo",
            "store_service_account_key_json_on_external_drive",
            "store_service_account_key_json_in_secret_manager",
        ]
        for rule_name in forbidden_service_account_storage:
            if service_account_policy.get(rule_name, False):
                issues.append(f"Service account key policy must be false: {rule_name}")
        secrets = manifest.get("secrets", {})
        if not isinstance(secrets, dict) or not secrets:
            issues.append("Manifest contains no secrets map.")
            return ManifestValidationResult(valid=False, issues=issues, secret_count=0)
        for name, record in secrets.items():
            if not isinstance(record, dict):
                issues.append(f"{name}: record must be an object.")
                continue
            for field in self.RAW_VALUE_FIELDS:
                if field in record:
                    issues.append(f"{name}: raw-value field is forbidden: {field}")
            if record.get("log_value", False):
                issues.append(f"{name}: log_value must be false.")
            if record.get("store_raw_value_on_external_drive", False):
                issues.append(f"{name}: external drive raw value storage must be false.")
            resource = str(record.get("resource", ""))
            if not resource.startswith("projects/"):
                issues.append(f"{name}: resource must be a Google Secret Manager resource reference.")
            if not record.get("allowed_phases"):
                issues.append(f"{name}: allowed_phases is required.")
            if not record.get("allowed_agents"):
                issues.append(f"{name}: allowed_agents is required.")
        return ManifestValidationResult(valid=not issues, issues=issues, secret_count=len(secrets))

    def request_secret(self, request: SecretAccessRequest, google_client: Any | None = None) -> str:
        broker = SecretBroker(
            manifest_path=self.manifest_path,
            audit_log_path=self.audit_log_path,
            enable_live_retrieval=self.enable_live_retrieval,
            google_client=google_client,
        )
        return broker.get_secret(request)

    def redact_text(self, text: str) -> str:
        return self.redactor.redact_text(text)

    def scan_text(self, text: str, path: str = "<memory>") -> List[RedactionFinding]:
        return self.scanner.scan_text(text, path=path)

    def signature_update(self, validation: ManifestValidationResult, fake_test_passed: bool | None = None) -> str:
        lines = [
            "AIGC SIGNATURE UPDATE",
            "Operator:",
            "Justice Gray Maciocha",
            "Phase:",
            "Phase 11 - Security, Privacy, and Secrets Vault",
            "Agent:",
            "Ultra-Secrets Agent",
            "Manifest:",
            str(self.manifest_path),
            f"Manifest Valid: {validation.valid}",
            f"Secrets Mapped: {validation.secret_count}",
            "Issues:",
            json.dumps(validation.issues, indent=2),
            "Safety Review:",
            "Raw secret values are forbidden in manifests.",
            "Secret values are forbidden in logs.",
            "Live retrieval is disabled unless explicitly configured.",
            "Audit ledger records access events without values.",
        ]
        if fake_test_passed is not None:
            lines.append(f"Fake Secret Test Passed: {fake_test_passed}")
        return "\n".join(lines).strip() + "\n"
