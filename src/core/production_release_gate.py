from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.contract_validator import validate_artifact  # noqa: E402
from src.core.production_readiness_ledger import (  # noqa: E402
    build_report,
    load_ledger,
    repository_revision,
)


_HEX40 = re.compile(r"^[a-f0-9]{40}$")
_POLICY_SCHEMA = "production_release_gate_policy"
_MANIFEST_SCHEMA = "production_release_manifest"
_APPROVAL_SCHEMA = "production_release_operator_approval"
_RECEIPT_SCHEMA = "production_release_gate_receipt"


class ProductionReleaseGateError(ValueError):
    """Raised when release-gate inputs violate their contracts."""


@dataclass(frozen=True)
class ProductionReleaseEvaluation:
    receipt: dict[str, Any]
    readiness_report: dict[str, Any]
    manifest: dict[str, Any]
    policy: dict[str, Any]

    @property
    def permitted(self) -> bool:
        return self.receipt["result"] == "PERMIT"

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt": self.receipt,
            "readiness_report": self.readiness_report,
            "manifest": self.manifest,
            "policy": self.policy,
        }


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return _utc(parsed)


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionReleaseGateError(
            f"Unable to load {label}: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ProductionReleaseGateError(f"{label} must be a JSON object")
    return payload


def readiness_truth_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    capabilities = []
    for item in report.get("capability_results") or []:
        capability = dict(item)
        capabilities.append(
            {
                "capability_id": str(capability.get("capability_id") or ""),
                "effective_status": str(capability.get("effective_status") or ""),
                "evidence_complete": bool(capability.get("evidence_complete")),
                "blocking_for_production": bool(
                    capability.get("blocking_for_production")
                ),
                "missing_evidence": sorted(
                    str(value)
                    for value in capability.get("missing_evidence") or []
                ),
            }
        )
    capabilities.sort(key=lambda item: item["capability_id"])
    return {
        "ledger_id": str(report.get("ledger_id") or ""),
        "source_revision": str(report.get("source_revision") or ""),
        "overall_score": float(report.get("overall_score") or 0),
        "production_readiness_threshold": float(
            report.get("production_readiness_threshold") or 0
        ),
        "production_ready": bool(report.get("production_ready")),
        "blocking_gaps": sorted(
            str(value) for value in report.get("blocking_gaps") or []
        ),
        "capabilities": capabilities,
    }


def readiness_truth_digest(report: Mapping[str, Any]) -> str:
    return _digest(readiness_truth_projection(report))


def release_candidate_projection(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return the release candidate material excluding its later approval."""

    return {
        key: value
        for key, value in dict(manifest).items()
        if key != "operator_approval"
    }


def release_candidate_digest(manifest: Mapping[str, Any]) -> str:
    return _digest(release_candidate_projection(manifest))


def evaluate_release_manifest(
    *,
    project_root: Path,
    manifest: Mapping[str, Any],
    policy: Mapping[str, Any],
    readiness_report: Mapping[str, Any] | None = None,
    actual_revision: str | None = None,
    evaluated_at: datetime | None = None,
) -> ProductionReleaseEvaluation:
    manifest_value = dict(manifest)
    policy_value = dict(policy)
    validate_artifact(_MANIFEST_SCHEMA, manifest_value)
    validate_artifact(_POLICY_SCHEMA, policy_value)
    approval = dict(manifest_value["operator_approval"])
    validate_artifact(_APPROVAL_SCHEMA, approval)

    if readiness_report is None:
        ledger_path = project_root / str(policy_value["readiness_ledger_path"])
        readiness_report = build_report(project_root, load_ledger(ledger_path))
    report = dict(readiness_report)

    current = _utc(evaluated_at or datetime.now(timezone.utc))
    revision = str(actual_revision or repository_revision(project_root))
    truth_digest = readiness_truth_digest(report)
    candidate_digest = release_candidate_digest(manifest_value)
    manifest_digest = _digest(manifest_value)
    threshold = max(
        float(policy_value["minimum_readiness_score"]),
        float(report.get("production_readiness_threshold") or 0),
    )
    score = float(report.get("overall_score") or 0)
    blocking_gaps = sorted(
        str(value) for value in report.get("blocking_gaps") or []
    )
    reasons: list[str] = []

    if policy_value.get("require_exact_revision") is True:
        if not _HEX40.fullmatch(revision):
            reasons.append("REVISION_UNBOUND")
        elif manifest_value.get("exact_revision") != revision:
            reasons.append("REVISION_MISMATCH")
        if report.get("source_revision") != revision:
            reasons.append("READINESS_REVISION_MISMATCH")

    if manifest_value.get("readiness_truth_digest") != truth_digest:
        reasons.append("READINESS_DIGEST_MISMATCH")
    if score < threshold:
        reasons.append("READINESS_SCORE_BELOW_THRESHOLD")
    if policy_value.get("require_no_blocking_gaps") is True and blocking_gaps:
        reasons.append("BLOCKING_GAPS_PRESENT")
    if report.get("production_ready") is not True:
        reasons.append("READINESS_NOT_PRODUCTION_READY")
    if manifest_value.get("expected_blocking_gaps") != []:
        reasons.append("MANIFEST_EXPECTED_GAPS_NOT_EMPTY")
    if (
        policy_value.get("require_production_environment") is True
        and manifest_value.get("environment") != "production"
    ):
        reasons.append("ENVIRONMENT_NOT_PRODUCTION")

    artifact = dict(manifest_value.get("release_artifact") or {})
    if artifact.get("immutable") is not True:
        reasons.append("RELEASE_ARTIFACT_NOT_IMMUTABLE")

    required_groups = set(policy_value.get("required_receipt_groups") or [])
    evidence_groups = dict(manifest_value.get("evidence_receipts") or {})
    for group in sorted(required_groups):
        values = evidence_groups.get(group)
        if not isinstance(values, list) or not values:
            reasons.append("RELEASE_EVIDENCE_INCOMPLETE")
            break

    created_at = _parse_time(manifest_value["created_at"])
    expires_at = _parse_time(manifest_value["expires_at"])
    if expires_at <= created_at:
        reasons.append("MANIFEST_LIFETIME_INVALID")
    if current >= expires_at:
        reasons.append("MANIFEST_EXPIRED")
    ttl_hours = (expires_at - created_at).total_seconds() / 3600
    if ttl_hours > int(policy_value["manifest_ttl_hours"]):
        reasons.append("MANIFEST_TTL_EXCEEDED")

    approval_receipt = approval.get("receipt_id")
    if policy_value.get("require_operator_approval") is True:
        if approval.get("release_id") != manifest_value.get("release_id"):
            reasons.append("OPERATOR_APPROVAL_RELEASE_MISMATCH")
        if approval.get("exact_revision") != manifest_value.get("exact_revision"):
            reasons.append("OPERATOR_APPROVAL_REVISION_MISMATCH")
        if approval.get("release_candidate_digest") != candidate_digest:
            reasons.append("OPERATOR_APPROVAL_CANDIDATE_MISMATCH")
        if approval.get("decision") == "DENIED":
            reasons.append("OPERATOR_DENIED_RELEASE")
        elif (
            approval.get("decision") != "APPROVED"
            or approval.get("production_deployment_authorized") is not True
        ):
            reasons.append("OPERATOR_APPROVAL_MISSING")

        approval_issued = _parse_time(approval["issued_at"])
        approval_expires = _parse_time(approval["expires_at"])
        if approval_expires <= approval_issued:
            reasons.append("OPERATOR_APPROVAL_LIFETIME_INVALID")
        if approval_issued < created_at:
            reasons.append("OPERATOR_APPROVAL_PREDATES_MANIFEST")
        if approval_expires > expires_at:
            reasons.append("OPERATOR_APPROVAL_OUTLIVES_MANIFEST")
        if current >= approval_expires:
            reasons.append("OPERATOR_APPROVAL_EXPIRED")

    reason_codes = tuple(dict.fromkeys(reasons))
    permitted = not reason_codes
    gate_receipt_id = "PRG-" + sha256(
        (
            str(manifest_value["release_id"])
            + "|"
            + revision
            + "|"
            + manifest_digest
            + "|"
            + candidate_digest
            + "|"
            + truth_digest
            + "|"
            + ",".join(reason_codes)
        ).encode("utf-8")
    ).hexdigest()[:24].upper()

    receipt = {
        "contract_id": "AIGC-PRODUCTION-RELEASE-GATE-RECEIPT-001",
        "contract_version": "1.0.0",
        "gate_receipt_id": gate_receipt_id,
        "release_id": manifest_value["release_id"],
        "exact_revision": revision or "unbound",
        "result": "PERMIT" if permitted else "DENY",
        "reason_codes": list(reason_codes),
        "actual_readiness_score": score,
        "required_readiness_score": threshold,
        "actual_blocking_gaps": blocking_gaps,
        "manifest_digest": manifest_digest,
        "release_candidate_digest": candidate_digest,
        "readiness_truth_digest": truth_digest,
        "release_artifact_digest": artifact.get(
            "digest",
            "sha256:" + "0" * 64,
        ),
        "operator_approval_receipt_id": approval_receipt,
        "deployment_authorized": permitted,
        "evaluated_at": current.isoformat(),
        "external_action_performed": False,
    }
    validate_artifact(_RECEIPT_SCHEMA, receipt)
    return ProductionReleaseEvaluation(
        receipt=receipt,
        readiness_report=report,
        manifest=manifest_value,
        policy=policy_value,
    )


def evaluate_release_manifest_file(
    *,
    project_root: Path,
    manifest_path: Path,
    policy_path: Path | None = None,
    evaluated_at: datetime | None = None,
) -> ProductionReleaseEvaluation:
    resolved_policy = policy_path or (
        project_root / "config" / "production_release_gate.json"
    )
    manifest = _load_json(manifest_path, label="production release manifest")
    policy = _load_json(resolved_policy, label="production release gate policy")
    return evaluate_release_manifest(
        project_root=project_root,
        manifest=manifest,
        policy=policy,
        evaluated_at=evaluated_at,
    )


def write_gate_receipt(
    project_root: Path,
    evaluation: ProductionReleaseEvaluation,
    *,
    artifact_root: Path | None = None,
) -> Path:
    root = artifact_root or (
        project_root / "reports" / "artifacts" / "production_release_gate"
    )
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{evaluation.receipt['gate_receipt_id']}.json"
    path.write_text(
        json.dumps(evaluation.receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a production release manifest without deploying."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--require-permit", action="store_true")
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    evaluation = evaluate_release_manifest_file(
        project_root=project_root,
        manifest_path=args.manifest.resolve(),
        policy_path=args.policy.resolve() if args.policy else None,
    )
    payload = evaluation.to_dict()
    if args.write:
        payload["written_receipt_path"] = str(
            write_gate_receipt(
                project_root,
                evaluation,
                artifact_root=(
                    args.artifact_root.resolve()
                    if args.artifact_root
                    else None
                ),
            )
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_permit and not evaluation.permitted:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
