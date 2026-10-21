"""Autonomous safety evidence verification agent with durable receipts.

The agent verifies claims; it does not create safety evidence or execute external actions.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.safety_evidence_verifier import SafetyEvidenceVerifier, canonical_json


@dataclass(frozen=True)
class SafetyVerificationReceipt:
    receipt_id: str
    verdict: str
    reason: str
    verified_at: str
    verifier_version: str
    source_revision: str
    source_tree_sha: str
    packet_sha256: str
    evidence_manifest_sha256: str
    authorization_id: str
    action_id: str
    artifact_sha256: str
    recipient: str
    platform: str
    scope: str
    receipt_sha256: str


class SafetyEvidenceVerifierAgent:
    """Run verification autonomously and append a hash-addressed audit receipt."""

    VERSION = "aigc-safety-evidence-verifier-agent/1.0"

    def __init__(self, verifier: SafetyEvidenceVerifier, project_root: Path, ledger_path: Path | None = None):
        self.verifier = verifier
        self.project_root = project_root.resolve()
        self.ledger_path = ledger_path or (self.project_root / "data" / "audit" / "safety_verifier_receipts.jsonl")

    def run(self, packet: Any) -> SafetyVerificationReceipt:
        evidence = packet.safety.evidence_records
        error = self.verifier.verify(packet, evidence)
        evidence_items = evidence if isinstance(evidence, (list, tuple)) else [evidence]
        verdict = "PASS" if error is None else "BLOCK"
        auth = packet.authorization
        packet_payload = {
            "authorization": asdict(auth),
            "artifact": asdict(packet.artifact),
            "action_type": packet.action_type,
            "execution_mode": packet.execution_mode,
        }
        evidence_manifest = [
            {
                "evidence_id": (
                    record.get("payload", {}).get("evidence_id", "")
                    if isinstance(record, dict) and isinstance(record.get("payload"), dict)
                    else ""
                ),
                "record_sha256": hashlib.sha256(canonical_json(record)).hexdigest(),
            }
            for record in evidence_items
        ]
        revision, tree_sha, clean_tree = self._git_provenance()
        if revision == "unavailable" or tree_sha == "unavailable":
            verdict = "BLOCK"
            error = error or "Source revision/tree provenance is unavailable."
        elif not clean_tree:
            verdict = "BLOCK"
            error = error or "Source checkout has uncommitted or untracked files outside the runtime audit ledger."
        fields = {
            "receipt_id": str(uuid.uuid4()),
            "verdict": verdict,
            "reason": error or "All required signed safety evidence validated.",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "verifier_version": self.VERSION,
            "source_revision": revision,
            "source_tree_sha": tree_sha,
            "packet_sha256": hashlib.sha256(canonical_json(packet_payload)).hexdigest(),
            "evidence_manifest_sha256": hashlib.sha256(canonical_json(evidence_manifest)).hexdigest(),
            "authorization_id": auth.authorization_id,
            "action_id": auth.action_id,
            "artifact_sha256": packet.artifact.hash,
            "recipient": auth.recipient,
            "platform": auth.platform,
            "scope": auth.execution_scope,
        }
        receipt_digest = hashlib.sha256(canonical_json(fields)).hexdigest()
        receipt = SafetyVerificationReceipt(**fields, receipt_sha256=receipt_digest)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(receipt), ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
        return receipt

    def _git_provenance(self) -> tuple[str, str, bool]:
        def resolve(expression: str) -> str:
            try:
                return subprocess.run(
                    ["git", "-C", str(self.project_root), "rev-parse", expression],
                    check=True, capture_output=True, text=True, timeout=3,
                ).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                return "unavailable"

        revision = resolve("HEAD")
        tree = resolve("HEAD^{tree}")
        try:
            status = subprocess.run(
                ["git", "-C", str(self.project_root), "status", "--porcelain", "--untracked-files=all"],
                check=True, capture_output=True, text=True, timeout=3,
            ).stdout.splitlines()
            # Runtime receipts are intentionally append-only generated state, not source.
            source_changes = [
                line for line in status
                if not line[3:].replace("\\\\", "/").startswith("data/audit/")
            ]
            clean = not source_changes
        except (OSError, subprocess.SubprocessError):
            clean = False
        return revision, tree, clean
