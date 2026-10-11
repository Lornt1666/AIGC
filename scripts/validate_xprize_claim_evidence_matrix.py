from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "aigc.xprize-claim-evidence-matrix.v1"
ALLOWED_CLASSES = {
    "PROVEN",
    "DEMONSTRATED",
    "IMPLEMENTED_NOT_RUNTIME_PROVEN",
    "DESIGNED",
    "PLANNED",
    "EXPERIMENTAL",
}
ALLOWED_EVIDENCE_STATES = {"VERIFIED", "PARTIAL", "UNVERIFIED", "MISSING"}
STRONG_CLASSES = {"PROVEN", "DEMONSTRATED"}
IMPLEMENTED_CLASSES = STRONG_CLASSES | {"IMPLEMENTED_NOT_RUNTIME_PROVEN"}


@dataclass(frozen=True)
class ClaimMatrixEvaluation:
    valid: bool
    claim_count: int
    strong_claim_count: int
    unresolved_claim_ids: tuple[str, ...]
    runtime_receipt_blocked_ids: tuple[str, ...]
    business_receipt_blocked_ids: tuple[str, ...]


def _text(value: Any, *, field: str, claim_id: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{claim_id}: {field} is required")
    return result


def evaluate(payload: Mapping[str, Any]) -> ClaimMatrixEvaluation:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported claim-evidence matrix schema_version")
    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("claims must be a non-empty list")

    seen: set[str] = set()
    unresolved: list[str] = []
    runtime_blocked: list[str] = []
    business_blocked: list[str] = []
    strong_count = 0

    for raw in claims:
        if not isinstance(raw, Mapping):
            raise ValueError("claim entries must be objects")
        claim_id = _text(raw.get("claim_id"), field="claim_id", claim_id="<unknown>")
        if claim_id in seen:
            raise ValueError(f"duplicate claim_id: {claim_id}")
        seen.add(claim_id)
        _text(raw.get("topic"), field="topic", claim_id=claim_id)
        _text(raw.get("claim"), field="claim", claim_id=claim_id)
        claim_class = _text(raw.get("class"), field="class", claim_id=claim_id)
        evidence_state = _text(raw.get("evidence_state"), field="evidence_state", claim_id=claim_id)
        if claim_class not in ALLOWED_CLASSES:
            raise ValueError(f"{claim_id}: unsupported claim class {claim_class}")
        if evidence_state not in ALLOWED_EVIDENCE_STATES:
            raise ValueError(f"{claim_id}: unsupported evidence state {evidence_state}")

        refs = raw.get("evidence_refs")
        if not isinstance(refs, list):
            raise ValueError(f"{claim_id}: evidence_refs must be a list")
        refs = [str(item).strip() for item in refs if str(item).strip()]
        if claim_class in IMPLEMENTED_CLASSES and not refs:
            raise ValueError(f"{claim_id}: implemented/strong claim requires evidence refs")

        if claim_class in STRONG_CLASSES:
            strong_count += 1
            if evidence_state != "VERIFIED":
                raise ValueError(
                    f"{claim_id}: {claim_class} requires VERIFIED evidence, got {evidence_state}"
                )

        if evidence_state == "MISSING" and claim_class in IMPLEMENTED_CLASSES:
            raise ValueError(f"{claim_id}: implemented/strong claim cannot have MISSING evidence")

        runtime_required = raw.get("runtime_required") is True
        runtime_ref = raw.get("runtime_receipt_ref")
        if runtime_required and claim_class in STRONG_CLASSES and not runtime_ref:
            raise ValueError(f"{claim_id}: strong runtime claim requires runtime_receipt_ref")
        if runtime_required and not runtime_ref:
            runtime_blocked.append(claim_id)

        business_required = raw.get("business_evidence_required") is True
        business_ref = raw.get("business_receipt_ref")
        if business_required and claim_class in STRONG_CLASSES and not business_ref:
            raise ValueError(f"{claim_id}: strong business claim requires business_receipt_ref")
        if business_required and not business_ref:
            business_blocked.append(claim_id)

        _text(raw.get("allowed_wording"), field="allowed_wording", claim_id=claim_id)
        prohibited = raw.get("prohibited_wording")
        if not isinstance(prohibited, list) or not prohibited:
            raise ValueError(f"{claim_id}: prohibited_wording must be non-empty")
        if any(not str(item).strip() for item in prohibited):
            raise ValueError(f"{claim_id}: prohibited wording entries cannot be blank")

        if evidence_state != "VERIFIED":
            unresolved.append(claim_id)

    for flag in (
        "external_action_performed",
        "public_devpost_update_performed",
        "devpost_submission_performed",
    ):
        if payload.get(flag) is not False:
            raise ValueError(f"{flag} must remain false in the claim audit artifact")

    return ClaimMatrixEvaluation(
        valid=True,
        claim_count=len(claims),
        strong_claim_count=strong_count,
        unresolved_claim_ids=tuple(sorted(unresolved)),
        runtime_receipt_blocked_ids=tuple(sorted(runtime_blocked)),
        business_receipt_blocked_ids=tuple(sorted(business_blocked)),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the AIGC XPRIZE claim/evidence matrix.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    result = evaluate(payload)
    print(json.dumps({
        "valid": result.valid,
        "claim_count": result.claim_count,
        "strong_claim_count": result.strong_claim_count,
        "unresolved_claim_ids": result.unresolved_claim_ids,
        "runtime_receipt_blocked_ids": result.runtime_receipt_blocked_ids,
        "business_receipt_blocked_ids": result.business_receipt_blocked_ids,
        "external_action_performed": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
