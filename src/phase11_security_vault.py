from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.ultra_secrets_agent import UltraSecretsAgent
from src.security.secret_policy_gate import SecretAccessRequest, SecretAccessDenied


class FakeGoogleSecretClient:
    def __init__(self, secrets: Dict[str, str]):
        self.secrets = secrets

    def access_secret(self, resource_name: str) -> str:
        return self.secrets[resource_name]


def run_fake_secret_test(agent: UltraSecretsAgent) -> bool:
    manifest = agent.load_manifest()
    fake_record = manifest.get("secrets", {}).get("FAKE_TEST_SECRET", {})
    fake_resource = fake_record.get("resource", "")
    fake_value = "sk-" + "fake-" + "LOCAL-TEST-SECRET-" + "1234567890"
    fake_client = FakeGoogleSecretClient({fake_resource: fake_value})
    test_agent = UltraSecretsAgent(
        manifest_path=agent.manifest_path,
        audit_log_path=agent.audit_log_path,
        enable_live_retrieval=True,
    )
    returned = test_agent.request_secret(
        SecretAccessRequest(
            secret_key="FAKE_TEST_SECRET",
            phase="phase11_security_vault",
            agent="Secret Broker",
            reason="Phase 11 fake-secret broker verification.",
        ),
        google_client=fake_client,
    )
    redacted = test_agent.redact_text(returned)
    audit_text = agent.audit_log_path.read_text(encoding="utf-8") if agent.audit_log_path.exists() else ""
    return returned == fake_value and fake_value not in redacted and fake_value not in audit_text


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    external_manifest = default_root.parent / "AIGC_MEMORY_CORE" / "config" / "secret_manifest.json"
    parser = argparse.ArgumentParser(description="Run AIGC Phase 11 security vault checks.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--manifest", type=Path, default=external_manifest)
    parser.add_argument("--audit-log", type=Path, default=default_root / "data" / "audit" / "phase11_secret_access_log.jsonl")
    parser.add_argument("--fake-test", action="store_true", help="Run fake Google Secret Manager retrieval test.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    agent = UltraSecretsAgent(
        manifest_path=args.manifest,
        audit_log_path=args.audit_log,
        enable_live_retrieval=False,
    )
    validation = agent.validate_manifest()
    fake_test_passed = None
    if args.fake_test:
        try:
            fake_test_passed = run_fake_secret_test(agent)
        except (KeyError, SecretAccessDenied) as exc:
            fake_test_passed = False
            print(f"Fake secret test failed: {exc}")
    report = agent.signature_update(validation, fake_test_passed)
    report_path = args.project_root / "data" / "reports" / "phase11_signature_update.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Report exported: {report_path}")
    return 0 if validation.valid and (fake_test_passed is not False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
