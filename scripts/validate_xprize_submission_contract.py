from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


FINAL_FIELD_STATES = {"EVIDENCED", "NOT_APPLICABLE"}
ALLOWED_FIELD_STATES = FINAL_FIELD_STATES | {
    "UNRESOLVED",
    "PARTIAL",
    "UNVERIFIED",
    "MISSING",
    "BLOCKED_RUNTIME_EVIDENCE",
}
FINAL_DELIVERABLE_STATES = {"EVIDENCED", "NOT_APPLICABLE"}
ALLOWED_DELIVERABLE_STATES = FINAL_DELIVERABLE_STATES | {
    "PARTIAL",
    "UNVERIFIED",
    "MISSING",
}
FINAL_ELIGIBILITY_STATES = {"EVIDENCED", "NOT_APPLICABLE"}
ALLOWED_ELIGIBILITY_STATES = FINAL_ELIGIBILITY_STATES | {
    "UNRESOLVED",
    "PARTIAL",
    "UNVERIFIED",
    "MISSING",
}


@dataclass(frozen=True)
class SubmissionContractEvaluation:
    ready_for_final_submission: bool
    unresolved_field_ids: tuple[int, ...]
    unresolved_deliverables: tuple[str, ...]
    unresolved_eligibility: tuple[str, ...]
    stale_public_project_copy: bool
    authority_granted: bool


def evaluate(payload: Mapping[str, Any]) -> SubmissionContractEvaluation:
    required_top = {
        "schema_version",
        "challenge",
        "challenge_slug",
        "submission_deadline_utc",
        "project",
        "judging_criteria",
        "eligibility",
        "deliverables",
        "required_fields",
        "authority",
    }
    missing = sorted(required_top - set(payload))
    if missing:
        raise ValueError("missing submission-contract keys: " + ", ".join(missing))
    if payload["schema_version"] != "aigc.xprize-submission-contract.v1":
        raise ValueError("unsupported submission contract schema_version")

    eligibility = payload["eligibility"]
    if not isinstance(eligibility, Mapping):
        raise ValueError("eligibility must be an object")
    unresolved_eligibility: list[str] = []
    for name, value in eligibility.items():
        if isinstance(value, Mapping):
            state = str(value.get("status", ""))
        else:
            state = str(value)
        if state not in ALLOWED_ELIGIBILITY_STATES:
            raise ValueError(f"unsupported eligibility state for {name}: {state}")
        if state not in FINAL_ELIGIBILITY_STATES:
            unresolved_eligibility.append(str(name))

    fields = payload["required_fields"]
    if not isinstance(fields, list):
        raise ValueError("required_fields must be a list")
    seen: set[int] = set()
    unresolved_field_ids: list[int] = []
    for field in fields:
        if not isinstance(field, Mapping):
            raise ValueError("required field entries must be objects")
        field_id = int(field["id"])
        if field_id in seen:
            raise ValueError(f"duplicate submission field id: {field_id}")
        seen.add(field_id)
        state = str(field["status"])
        if state not in ALLOWED_FIELD_STATES:
            raise ValueError(f"unsupported field state for {field_id}: {state}")
        if state not in FINAL_FIELD_STATES:
            unresolved_field_ids.append(field_id)

    deliverables = payload["deliverables"]
    if not isinstance(deliverables, Mapping):
        raise ValueError("deliverables must be an object")
    unresolved_deliverables: list[str] = []
    for name, value in deliverables.items():
        state = str(value)
        if state not in ALLOWED_DELIVERABLE_STATES:
            raise ValueError(f"unsupported deliverable state for {name}: {state}")
        if state not in FINAL_DELIVERABLE_STATES:
            unresolved_deliverables.append(str(name))

    project = payload["project"]
    if not isinstance(project, Mapping):
        raise ValueError("project must be an object")
    stale = str(project.get("public_copy_alignment")) != "CURRENT"

    authority = payload["authority"]
    if not isinstance(authority, Mapping):
        raise ValueError("authority must be an object")
    authority_granted = all(
        authority.get(name) is True
        for name in ("public_project_update", "final_submission_update", "devpost_submission")
    )

    ready = (
        not unresolved_eligibility
        and not unresolved_field_ids
        and not unresolved_deliverables
        and not stale
        and authority_granted
    )
    return SubmissionContractEvaluation(
        ready_for_final_submission=ready,
        unresolved_field_ids=tuple(sorted(unresolved_field_ids)),
        unresolved_deliverables=tuple(sorted(unresolved_deliverables)),
        unresolved_eligibility=tuple(sorted(unresolved_eligibility)),
        stale_public_project_copy=stale,
        authority_granted=authority_granted,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AIGC XPRIZE submission readiness without submitting anything.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    result = evaluate(payload)
    print(json.dumps({
        "ready_for_final_submission": result.ready_for_final_submission,
        "unresolved_field_ids": result.unresolved_field_ids,
        "unresolved_deliverables": result.unresolved_deliverables,
        "unresolved_eligibility": result.unresolved_eligibility,
        "stale_public_project_copy": result.stale_public_project_copy,
        "authority_granted": result.authority_granted,
        "external_action_performed": False,
    }, indent=2))
    return 0 if result.ready_for_final_submission else 2


if __name__ == "__main__":
    raise SystemExit(main())
