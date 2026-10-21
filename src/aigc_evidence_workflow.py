"""Evidence-driven, fail-closed orchestration for AIGC specialist agents.

This runner invokes the real deterministic AER/Red/Blue/Green evaluators, binds
each task/report to an exact repository/commit/tree/policy/invocation, and writes
a hash-chained JSONL evidence ledger. Authentication is deliberately pluggable:
a signer must be an external trusted signing service and the verifier must use
an independently pinned public key/identity. Without both, reports remain
unauthenticated and no downstream stage may consume them as trusted evidence.
No network, shell, repository mutation, deployment, merge, or release action.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from aigc_team_agents import AERAgent, RedTeamAgent, BlueTeamAgent, GreenTeamAgent
from aigc_team_agents import canonical_json, sha256_hex

SIGNER = Callable[[bytes], dict[str, Any]]
VERIFIER = Callable[[bytes, dict[str, Any]], dict[str, Any]]
REQUIRED_BINDINGS = ("repository", "commit_sha", "tree_sha", "policy_digest", "invocation_id")


def signed_payload(report: dict[str, Any]) -> bytes:
    """Canonical bytes that the external signer must sign and verifier must verify."""
    return canonical_json({k: v for k, v in report.items()
                           if k not in {"authentication", "report_sha256"}})


def _seal_digest(report: dict[str, Any]) -> dict[str, Any]:
    report.pop("report_sha256", None)
    report["report_sha256"] = sha256_hex(canonical_json(
        {k: v for k, v in report.items() if k != "report_sha256"}))
    return report


def authenticate_report(report: dict[str, Any], signer: SIGNER | None,
                        verifier: VERIFIER | None) -> dict[str, Any]:
    """Attach externally generated signature metadata and verify it immediately."""
    report = json.loads(json.dumps(report))
    report["authentication"] = {"status": "UNAUTHENTICATED", "method": None}
    payload = signed_payload(report)
    if signer is not None:
        try:
            signature = signer(payload)
            if not isinstance(signature, dict) or not signature.get("signature_b64") or not signature.get("signer_identity"):
                raise ValueError("signer returned incomplete signature metadata")
            report["authentication"] = {
                "status": "SIGNED", "method": "Ed25519", **signature,
                "signed_payload_sha256": sha256_hex(payload),
            }
            if verifier is not None:
                verification = verifier(payload, report["authentication"])
                if isinstance(verification, dict) and verification.get("verified") is True:
                    report["authentication"]["status"] = "AUTHENTICATED"
                    report["authentication"]["verification"] = {
                        "verified": True,
                        "signer_identity": verification.get("signer_identity"),
                        "trust_root_id": verification.get("trust_root_id"),
                    }
                else:
                    report["authentication"]["status"] = "REJECTED"
                    report["authentication"]["verification"] = {"verified": False}
        except Exception as exc:
            report["authentication"] = {
                "status": "REJECTED", "method": "Ed25519",
                "failure_class": type(exc).__name__,
            }
    _seal_digest(report)
    return report


def make_ed25519_verifier(public_key_pem: str, trusted_signer_identity: str,
                          trust_root_id: str) -> VERIFIER:
    """Build a verifier from an independently pinned PEM public key and identity.

    The private key must never be stored in this repository or runner. Supply a
    signer callback backed by a separately controlled KMS/HSM/signing service.
    """
    if not public_key_pem.strip() or not trusted_signer_identity.strip() or not trust_root_id.strip():
        raise ValueError("pinned public key, signer identity, and trust-root ID are required")
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        public_key = load_pem_public_key(public_key_pem.encode("utf-8"))
    except Exception as exc:
        raise ValueError("unable to load trusted public key") from exc

    def verify(payload: bytes, authentication: dict[str, Any]) -> dict[str, Any]:
        if authentication.get("signer_identity") != trusted_signer_identity:
            return {"verified": False, "reason": "signer_identity_mismatch"}
        if authentication.get("signed_payload_sha256") != sha256_hex(payload):
            return {"verified": False, "reason": "signed_payload_digest_mismatch"}
        try:
            signature = base64.b64decode(authentication.get("signature_b64", ""), validate=True)
            public_key.verify(signature, payload)
        except Exception:
            return {"verified": False, "reason": "signature_invalid"}
        return {"verified": True, "signer_identity": trusted_signer_identity,
                "trust_root_id": trust_root_id}
    return verify


def validate_binding(report: dict[str, Any], envelope: dict[str, Any],
                     expected_agent: str) -> bool:
    return (
        report.get("agent_id") == expected_agent
        and all(report.get(k) == envelope.get(k) for k in REQUIRED_BINDINGS)
        and report.get("tree_sha") == envelope.get("tree_sha")
        and report.get("policy_id") == envelope.get("policy_id")
        and report.get("invocation_id") == envelope.get("invocation_id")
        and report.get("authentication", {}).get("status") == "AUTHENTICATED"
    )


class HashChainLedger:
    """Append-only local JSONL ledger; detects accidental edits/reordering/truncation.

    A hash chain is tamper-evident only relative to a separately preserved final
    digest. It is not a digital signature or proof of remote storage.
    """
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sequence = 0
        self.previous_hash = "0" * 64
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                body = {k: v for k, v in record.items() if k != "record_hash"}
                expected = sha256_hex(canonical_json(body))
                if record.get("record_hash") != expected:
                    raise ValueError("existing evidence ledger hash mismatch")
                if record.get("sequence") != self.sequence + 1 or record.get("previous_hash") != self.previous_hash:
                    raise ValueError("existing evidence ledger chain discontinuity")
                self.sequence = record["sequence"]
                self.previous_hash = expected

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        body = {"sequence": self.sequence + 1, "previous_hash": self.previous_hash, "event": event}
        record = {**body, "record_hash": sha256_hex(canonical_json(body))}
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.sequence = record["sequence"]
        self.previous_hash = record["record_hash"]
        return record


def verify_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("evidence ledger is missing or empty")
    ledger = HashChainLedger(path)
    if ledger.sequence == 0:
        raise ValueError("evidence ledger contains no records")
    return {"valid": True, "records": ledger.sequence, "final_digest": ledger.previous_hash}


def _task(stage_id: str, agent_id: str, envelope: dict[str, Any],
          inputs: dict[str, Any], allowed_actions: list[str]) -> dict[str, Any]:
    task = {
        "task_id": f"{envelope['invocation_id']}:{stage_id}",
        "stage_id": stage_id, "agent_id": agent_id,
        "repository": envelope["repository"], "commit_sha": envelope["commit_sha"],
        "tree_sha": envelope["tree_sha"], "policy_digest": envelope["policy_digest"],
        "invocation_id": envelope["invocation_id"],
        "input_digest_sha256": sha256_hex(canonical_json(inputs)),
        "required_output": ["decision", "checks", "findings", "required_actions", "authentication"],
        "allowed_actions": allowed_actions,
        "prohibited_actions": ["network_access", "shell_execution", "repository_write",
                               "permission_escalation", "merge", "deployment", "release"],
    }
    task["task_digest_sha256"] = sha256_hex(canonical_json(task))
    return task


def run_workflow(envelope: dict[str, Any], inputs: dict[str, Any], output_dir: Path,
                 signer: SIGNER | None = None, verifier: VERIFIER | None = None) -> dict[str, Any]:
    """Execute local specialist evaluators; gate every trusted handoff on signature."""
    missing = [k for k in REQUIRED_BINDINGS if not envelope.get(k)]
    if missing:
        raise ValueError("missing version bindings: " + ", ".join(missing))
    if len(envelope["commit_sha"]) != 40 or len(envelope["tree_sha"]) != 40:
        raise ValueError("commit_sha and tree_sha must be full 40-character Git object IDs")
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be a JSON object")

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = HashChainLedger(output_dir / "evidence.jsonl")
    reports: dict[str, dict[str, Any]] = {}
    stages: list[dict[str, Any]] = []

    def execute(stage_id: str, agent_id: str, input_data: dict[str, Any],
                invoke: Callable[[], dict[str, Any]], allowed: list[str]) -> dict[str, Any]:
        task = _task(stage_id, agent_id, envelope, input_data, allowed)
        ledger.append({"type": "task_issued", "task": task})
        raw = invoke()
        raw["task"] = task
        report = authenticate_report(raw, signer, verifier)
        bound = (
            all(report.get(k) == envelope.get(k) for k in REQUIRED_BINDINGS)
            and report.get("tree_sha") == envelope.get("tree_sha")
            and report.get("policy_id") == envelope.get("policy_id")
            and report.get("agent_id") == agent_id
        )
        authenticated = report.get("authentication", {}).get("status") == "AUTHENTICATED"
        status = report.get("decision", "BLOCK")
        if not bound:
            status = "BLOCK"
        if not authenticated and status == "PASS":
            status = "BLOCK"
        report["workflow_status"] = status
        report["binding_valid"] = bound
        report["trusted_for_handoff"] = bool(bound and authenticated)
        _seal_digest(report)
        reports[stage_id] = report
        path = output_dir / f"{stage_id}.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        ledger.append({"type": "specialist_result", "stage_id": stage_id,
                       "agent_id": agent_id, "workflow_status": status,
                       "binding_valid": bound, "trusted_for_handoff": report["trusted_for_handoff"],
                       "report_sha256": report["report_sha256"], "report_path": path.name})
        stages.append({"stage_id": stage_id, "agent_id": agent_id, "status": status,
                       "trusted_for_handoff": report["trusted_for_handoff"],
                       "report_sha256": report["report_sha256"]})
        return report

    aer_input = inputs.get("aer", {}) if isinstance(inputs.get("aer", {}), dict) else {}
    red_input = inputs.get("red_team", {}) if isinstance(inputs.get("red_team", {}), dict) else {}
    blue_input = inputs.get("blue_team", {}) if isinstance(inputs.get("blue_team", {}), dict) else {}
    green_input = inputs.get("green_team", {}) if isinstance(inputs.get("green_team", {}), dict) else {}

    aer = execute("aer-review", "aer", aer_input,
        lambda: AERAgent().assess(envelope, aer_input),
        ["evaluate supplied architecture/reliability evidence"])
    red = execute("red-review", "red-team", red_input,
        lambda: RedTeamAgent().assess(envelope, red_input.get("authorization"),
                                      red_input.get("test_results", []), red_input.get("requested_targets")),
        ["evaluate synthetic-only authorized test results"])
    blue = execute("blue-review", "blue-team", blue_input,
        lambda: BlueTeamAgent().assess(envelope, blue_input.get("telemetry"), blue_input.get("scenarios")),
        ["evaluate supplied telemetry and scenario outcomes"])

    upstream = [aer, red, blue]
    upstream_trusted = all(r.get("trusted_for_handoff") for r in upstream)
    # Remediation is only eligible when all upstream reports have authenticated,
    # exact-version bindings. It remains proposal-only and cannot apply a patch.
    if upstream_trusted:
        green = execute("green-remediation", "green-team", green_input,
            lambda: GreenTeamAgent().assess(envelope, green_input.get("remediation")),
            ["draft/evaluate remediation proposal; no patch application"])
    else:
        reason = "Blocked: one or more AER/Red/Blue reports lacks trusted authentication or exact-version binding."
        ledger.append({"type": "stage_blocked", "stage_id": "green-remediation", "reason": reason})
        stages.append({"stage_id": "green-remediation", "agent_id": "green-team",
                       "status": "BLOCKED_DEPENDENCY", "trusted_for_handoff": False, "reason": reason})

    all_trusted = upstream_trusted and ("green-remediation" in reports and reports["green-remediation"].get("trusted_for_handoff"))
    if all_trusted:
        verifier_status = "PASS" if all(r.get("workflow_status") == "PASS" for r in reports.values()) else "BLOCK"
        verifier_reason = "All specialist reports authenticated and bound; decisions still require PASS."
    else:
        verifier_status = "BLOCK"
        verifier_reason = "Independent verification cannot accept missing, unauthenticated, or version-mismatched specialist evidence."
    ledger.append({"type": "independent_verification", "status": verifier_status, "reason": verifier_reason})
    stages.append({"stage_id": "independent-verification", "status": verifier_status, "reason": verifier_reason})

    # Human acceptance and release authority are never inferred from automation.
    ledger.append({"type": "human_acceptance", "status": "REQUIRED", "accepted": False})
    stages.append({"stage_id": "human-acceptance", "status": "BLOCKED", "reason": "Explicit authorized human acceptance not supplied."})
    ledger.append({"type": "release_assurance", "status": "BLOCK", "decision": "BLOCK",
                   "reason": "Canonical Release Assurance has not received authenticated complete evidence and human acceptance."})
    stages.append({"stage_id": "release-assurance", "status": "BLOCK", "decision": "BLOCK"})

    summary = {
        "schema_version": "1.0", "policy_id": envelope["policy_id"],
        "repository": envelope["repository"], "commit_sha": envelope["commit_sha"],
        "tree_sha": envelope["tree_sha"], "policy_digest": envelope["policy_digest"],
        "invocation_id": envelope["invocation_id"],
        "status": "PASS" if all(s.get("status") == "PASS" for s in stages) else "BLOCK",
        "release_decision": "BLOCK", "stages": stages,
        "reports": {k: v["report_sha256"] for k, v in reports.items()},
        "ledger_final_digest": ledger.previous_hash,
        "authentication_configured": bool(signer and verifier),
        "disclaimer": "Local specialist evaluators executed. Release remains BLOCK unless all required authenticated evidence, independent verification, and explicit human acceptance pass. The JSONL hash chain is not a remote immutable store or signature.",
    }
    summary["summary_sha256"] = sha256_hex(canonical_json(
        {k: v for k, v in summary.items() if k not in {"summary_sha256", "ledger_final_digest"}}))
    (output_dir / "workflow_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ledger.append({"type": "workflow_summary", "summary_sha256": summary["summary_sha256"],
                   "status": summary["status"], "release_decision": summary["release_decision"]})
    summary["ledger_final_digest"] = ledger.previous_hash
    (output_dir / "workflow_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AIGC's fail-closed specialist workflow.")
    parser.add_argument("--envelope", required=True, help="JSON with repository, commit_sha, tree_sha, policy_digest, invocation_id, policy_id")
    parser.add_argument("--inputs", required=True, help="JSON object containing specialist evidence inputs")
    parser.add_argument("--output-dir", required=True, help="Directory for reports and hash-chained JSONL evidence")
    args = parser.parse_args(argv)
    try:
        envelope = json.loads(Path(args.envelope).read_text(encoding="utf-8"))
        inputs = json.loads(Path(args.inputs).read_text(encoding="utf-8"))
        # CLI intentionally does not construct a signer from local private-key files.
        # Production wiring must inject an approved external signer/verifier adapter.
        summary = run_workflow(envelope, inputs, Path(args.output_dir))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": summary["status"], "release_decision": summary["release_decision"],
                      "stages": len(summary["stages"]), "reports": len(summary["reports"]),
                      "authentication_configured": summary["authentication_configured"],
                      "ledger_final_digest": summary["ledger_final_digest"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
