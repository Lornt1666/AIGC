"""Deterministic AIGC release assurance decision agent.

This component evaluates release evidence; it does not deploy, merge, provision secrets,
or manufacture evidence. An APPROVE result is scoped to the requested release tier and
must be enforced by a separate least-privilege release controller.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_STAGES = (
    "pip_check",
    "python_compilation",
    "contracts",
    "orchestration_schema_validation",
    "orchestration_round_trip_validation",
    "redaction",
    "release_secret_scan",
    "procurement_smoke",
    "provider_discovery",
    "terraform_inert",
    "tests",
    "false_authority",
    "readiness",
)
REQUIRED_RELEASE_CHECKS = frozenset({
    "platform_policy",
    "ai_disclosure",
    "privacy",
    "end_to_end",
    "postgres_s3",
    "recovery",
    "canary_health",
    "rollback_drill",
    "independent_review",
})
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


class ReleaseAssuranceAgent:
    """Fail-closed release decision over exact-head CI and trusted checker evidence.

    Runtime configuration:
      AIGC_RELEASE_EVIDENCE_HMAC_KEYS_JSON: issuer_id -> >=32-byte secret
      AIGC_RELEASE_POLICY_VERSION: exact approved policy version
      AIGC_RELEASE_ISSUER_BY_CHECK_JSON: required check_id -> issuer_id

    Keys are injected from a secret manager; never commit them. This HMAC adapter is
    a reference implementation. Prefer KMS-backed asymmetric signatures for production.
    """

    VERSION = "aigc-release-assurance-agent/1.0"

    def __init__(self, keys: dict[str, str], policy_version: str,
                 issuer_by_check: dict[str, str], now=None):
        self.keys = {
            issuer: key.encode("utf-8")
            for issuer, key in keys.items()
            if isinstance(issuer, str) and issuer
            and isinstance(key, str) and len(key.encode("utf-8")) >= 32
        }
        self.policy_version = policy_version
        self.issuer_by_check = dict(issuer_by_check)
        self.now = now or (lambda: datetime.now(timezone.utc))

    @classmethod
    def from_environment(cls) -> "ReleaseAssuranceAgent":
        def parse(name: str) -> dict:
            try:
                value = json.loads(os.environ.get(name, "{}"))
            except json.JSONDecodeError:
                return {}
            return value if isinstance(value, dict) else {}
        return cls(
            parse("AIGC_RELEASE_EVIDENCE_HMAC_KEYS_JSON"),
            os.environ.get("AIGC_RELEASE_POLICY_VERSION", ""),
            parse("AIGC_RELEASE_ISSUER_BY_CHECK_JSON"),
        )

    @staticmethod
    def sign_for_trusted_issuer(payload: dict, secret: str) -> str:
        """Test/approved-checker helper; never expose production signing keys to an agent."""
        if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
            raise ValueError("signing key must be at least 32 bytes")
        return hmac.new(secret.encode("utf-8"), canonical(payload), hashlib.sha256).hexdigest()

    def evaluate(self, packet: dict) -> dict:
        reasons: list[str] = []
        try:
            subject = packet["subject"]
            ci = packet["canonical_ci"]
            attestations = packet["release_attestations"]
            tier = packet["release_tier"]
        except (KeyError, TypeError):
            return self._decision("BLOCK", ["release packet is malformed"], packet)

        if tier not in {"staging_canary", "production"}:
            reasons.append("release tier is unsupported")
        target_sha = subject.get("commit_sha")
        tree_sha = subject.get("tree_sha")
        if not isinstance(target_sha, str) or not HEX40.fullmatch(target_sha):
            reasons.append("subject commit SHA is not a full lowercase SHA")
        if not isinstance(tree_sha, str) or not HEX40.fullmatch(tree_sha):
            reasons.append("subject tree SHA is not a full lowercase SHA")

        # Require a successful exact-head canonical run, not a branch-level green badge.
        if ci.get("conclusion") != "success":
            reasons.append("canonical workflow conclusion is not success")
        if ci.get("repository") != "Lornt1666/AIGC":
            reasons.append("canonical workflow repository mismatch")
        if ci.get("target_sha") != target_sha or ci.get("tested_tree_sha") != tree_sha:
            reasons.append("canonical run is not bound to the exact release commit and tree")
        if not isinstance(ci.get("run_id"), int) or ci.get("run_id", 0) <= 0:
            reasons.append("canonical workflow run ID is missing")
        if ci.get("contract_id") != "AIGC-CI-EXACT-SHA-V1":
            reasons.append("canonical validation contract identity mismatch")
        if not isinstance(ci.get("contract_sha256"), str) or not HEX64.fullmatch(ci["contract_sha256"]):
            reasons.append("canonical validation contract digest is invalid")
        if ci.get("workflow_revision") != ci.get("expected_workflow_revision"):
            reasons.append("workflow revision is not the explicitly expected revision")

        stage_receipts = ci.get("stage_receipts")
        if not isinstance(stage_receipts, list):
            stage_receipts = []
        by_stage: dict[str, dict] = {}
        for record in stage_receipts:
            if not isinstance(record, dict):
                reasons.append("canonical stage receipt is malformed")
                continue
            record_hash = record.get("record_sha256")
            unsigned = dict(record)
            unsigned.pop("record_sha256", None)
            if not isinstance(record_hash, str) or not hmac.compare_digest(record_hash, sha256(canonical(unsigned))):
                reasons.append("canonical stage receipt digest is invalid")
                continue
            stage = record.get("stage_id")
            if stage in by_stage:
                reasons.append("duplicate canonical stage receipt")
                continue
            by_stage[stage] = record
            if record.get("target_sha") != target_sha or record.get("tested_tree_sha") != tree_sha:
                reasons.append(f"stage {stage} is bound to a different commit/tree")
            if record.get("run_id") != ci.get("run_id"):
                reasons.append(f"stage {stage} is bound to a different workflow run")
            if record.get("status") != "success":
                reasons.append(f"canonical stage did not pass: {stage}")
            if record.get("external_action_performed") is not False:
                reasons.append(f"canonical stage reports external side effects: {stage}")
            for flag in (
                "production_activation_authorized",
                "merge_authority_granted",
                "deployment_authority_granted",
                "live_model_call_authority_granted",
                "financial_authority_granted",
            ):
                if record.get(flag) is not False:
                    reasons.append(f"canonical stage grants prohibited authority: {stage}/{flag}")
        if set(by_stage) != set(EXPECTED_STAGES):
            missing = sorted(set(EXPECTED_STAGES) - set(by_stage))
            extra = sorted(set(by_stage) - set(EXPECTED_STAGES))
            reasons.append(f"canonical stage set mismatch; missing={missing}, extra={extra}")

        # Trusted, scoped attestations: a signed statement is not proof unless its issuer
        # is authorized for that check, and its subject/policy/freshness match this release.
        if not self.keys or not self.policy_version:
            reasons.append("trusted release-evidence keys or policy version are not configured")
        if set(self.issuer_by_check) != set(REQUIRED_RELEASE_CHECKS):
            reasons.append("release issuer-to-check authority map is incomplete")
        if not isinstance(attestations, list):
            attestations = []
        seen: set[str] = set()
        checks: set[str] = set()
        issuers: set[str] = set()
        now = self.now().astimezone(timezone.utc)
        for item in attestations:
            if not isinstance(item, dict):
                reasons.append("release attestation is malformed")
                continue
            payload, signature = item.get("payload"), item.get("signature")
            if not isinstance(payload, dict) or not isinstance(signature, str):
                reasons.append("release attestation payload/signature missing")
                continue
            issuer = payload.get("issuer_id")
            secret = self.keys.get(issuer) if isinstance(issuer, str) else None
            if secret is None:
                reasons.append("release attestation issuer is untrusted")
                continue
            expected_sig = hmac.new(secret, canonical(payload), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected_sig):
                reasons.append("release attestation signature invalid")
                continue
            evidence_id, check = payload.get("evidence_id"), payload.get("check_id")
            if not isinstance(evidence_id, str) or not evidence_id or evidence_id in seen:
                reasons.append("release attestation ID missing or duplicated")
                continue
            seen.add(evidence_id)
            if check not in REQUIRED_RELEASE_CHECKS:
                reasons.append("unknown release attestation check")
                continue
            if check in checks:
                reasons.append(f"duplicate release check attestation: {check}")
                continue
            if self.issuer_by_check.get(check) != issuer:
                reasons.append(f"issuer not authorized for release check: {check}")
                continue
            if issuer in issuers:
                reasons.append("release checks must use distinct trusted issuers")
                continue
            issuers.add(issuer)
            if payload.get("result") is not True:
                reasons.append(f"release check did not pass: {check}")
            if payload.get("policy_version") != self.policy_version:
                reasons.append(f"release check policy version mismatch: {check}")
            if payload.get("commit_sha") != target_sha or payload.get("tree_sha") != tree_sha:
                reasons.append(f"release check is not bound to exact source: {check}")
            if payload.get("artifact_sha256") != subject.get("artifact_sha256"):
                reasons.append(f"release check is not bound to exact artifact: {check}")
            if payload.get("release_tier") != tier:
                reasons.append(f"release check tier mismatch: {check}")
            if not isinstance(payload.get("checker_version"), str) or not payload["checker_version"]:
                reasons.append(f"release check version missing: {check}")
            issued, expires = _parse_time(payload.get("issued_at")), _parse_time(payload.get("expires_at"))
            if issued is None or expires is None or issued > now or expires <= now or expires <= issued:
                reasons.append(f"release check timestamp invalid or expired: {check}")
            elif (expires - issued).total_seconds() > 24 * 60 * 60:
                reasons.append(f"release check validity window too long: {check}")
            checks.add(check)
        missing_checks = sorted(REQUIRED_RELEASE_CHECKS - checks)
        if missing_checks:
            reasons.append(f"required release evidence missing: {missing_checks}")

        # Canary and rollback are explicit evidence checks; production cannot be approved
        # by merely passing CI. A separate execution controller must still enforce this.
        if tier == "production" and not {"canary_health", "rollback_drill"}.issubset(checks):
            reasons.append("production requires successful canary and rollback evidence")

        verdict = "APPROVE" if not reasons else "BLOCK"
        return self._decision(verdict, reasons or ["all deterministic release gates passed"], packet)

    def _decision(self, verdict: str, reasons: list[str], packet: Any) -> dict:
        subject = packet.get("subject", {}) if isinstance(packet, dict) else {}
        body = {
            "schema_version": "1.0.0",
            "agent_version": self.VERSION,
            "verdict": verdict,
            "reasons": reasons,
            "commit_sha": subject.get("commit_sha"),
            "tree_sha": subject.get("tree_sha"),
            "release_tier": packet.get("release_tier") if isinstance(packet, dict) else None,
            "evaluated_at": self.now().astimezone(timezone.utc).isoformat(),
            "deployment_performed": False,
            "merge_performed": False,
        }
        body["decision_sha256"] = sha256(canonical(body))
        return body


def evaluate_file(packet_path: Path, output_path: Path) -> dict:
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    decision = ReleaseAssuranceAgent.from_environment().evaluate(packet)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(decision, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return decision
