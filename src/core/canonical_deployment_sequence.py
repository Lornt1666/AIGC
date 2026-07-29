from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from src.core.contract_validator import validate_artifact


SCHEMA_NAME = "canonical_deployment_and_autonomy_sequence"
CONTRACT_ID = "AIGC-CANONICAL-DEPLOYMENT-AUTONOMY-SEQUENCE-001"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEQUENCE_PATH = (
    PROJECT_ROOT / "config" / "canonical_deployment_and_autonomy_sequence.json"
)


class CanonicalSequenceError(ValueError):
    """Raised when the canonical deployment sequence violates semantic invariants."""


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CanonicalSequenceError(message)


def load_sequence(path: str | Path = DEFAULT_SEQUENCE_PATH) -> dict[str, Any]:
    sequence_path = Path(path)
    payload = json.loads(sequence_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CanonicalSequenceError("Canonical deployment sequence must be a JSON object")
    return validate_sequence(payload)


def validate_sequence(payload: Mapping[str, Any]) -> dict[str, Any]:
    document = json.loads(_canonical_json(payload))
    validate_artifact(SCHEMA_NAME, document)

    _require(document["contract_id"] == CONTRACT_ID, "Unexpected contract_id")
    _require(
        document["repository"]["full_name"] == "Lornt1666/AIGC",
        "Sequence must remain bound to Lornt1666/AIGC",
    )
    _require(
        document["repository"]["default_branch"] == "main",
        "Canonical default branch must be main",
    )

    bindings = document["bindings"]
    _require(bindings["ci_incident_issue"] == 124, "CI incident must remain issue #124")
    _require(bindings["employer_duty_issue"] == 128, "Employer-duty feature must remain issue #128")
    _require(bindings["ci_hardening_pr"]["number"] == 123, "CI hardening must remain PR #123")
    _require(bindings["staging_authorization_pr"]["number"] == 121, "Staging authorization must remain PR #121")
    _require(bindings["cockpit_pr"]["number"] == 122, "Cockpit reconstruction must remain PR #122")
    _require(bindings["rebind_required_on_revision_change"] is True, "Revision changes must require rebinding")

    stages = list(document["critical_path"])
    stage_ids = [str(stage["stage_id"]) for stage in stages]
    _require(len(stage_ids) == len(set(stage_ids)), "Critical-path stage IDs must be unique")

    orders = [int(stage["order"]) for stage in stages]
    _require(sorted(orders) == list(range(1, len(stages) + 1)), "Stage order must be contiguous and start at 1")

    by_id = {str(stage["stage_id"]): stage for stage in stages}
    order_by_id = {stage_id: int(by_id[stage_id]["order"]) for stage_id in by_id}
    for stage in stages:
        stage_id = str(stage["stage_id"])
        _require(stage["operator_review_required"] is True, f"{stage_id} must require operator review")
        _require(stage["external_action_performed"] is False, f"{stage_id} cannot claim external action")
        for dependency in stage["depends_on"]:
            dependency_id = str(dependency)
            _require(dependency_id in by_id, f"{stage_id} references unknown dependency {dependency_id}")
            _require(
                order_by_id[dependency_id] < order_by_id[stage_id],
                f"{stage_id} dependency {dependency_id} must appear earlier",
            )

    expected_stage_ids = [
        "S1_HOSTED_CI_RECOVERY",
        "S2_PR123_MAINLINE_ADMISSION",
        "S3_STAGING_AUTHORIZATION_RECONSTRUCTION",
        "S4_CLOUD_RUN_STAGING_RUNTIME",
        "S5_ISOLATED_STAGING_ACTIVATION",
        "S6_CANARY_A_PLATFORM_PROOF",
        "S7_PR122_RECONSTRUCTION",
        "S8_CANARY_B_EMPLOYER_DUTY_AUTONOMY",
        "S9_READ_ONLY_CONNECTOR_CANARY",
    ]
    ordered_stage_ids = [
        str(stage["stage_id"])
        for stage in sorted(stages, key=lambda item: int(item["order"]))
    ]
    _require(ordered_stage_ids == expected_stage_ids, "Critical path does not match the canonical sequence")

    canaries = document["canaries"]
    _require(
        canaries["canary_a"]["stage_id"] == "S6_CANARY_A_PLATFORM_PROOF",
        "Canary A must remain the platform proof",
    )
    _require(
        canaries["canary_b"]["stage_id"] == "S8_CANARY_B_EMPLOYER_DUTY_AUTONOMY",
        "Canary B must remain the employer-duty autonomy proof",
    )
    _require(
        order_by_id[canaries["canary_a"]["stage_id"]]
        < order_by_id[canaries["canary_b"]["stage_id"]],
        "Canary A must complete before Canary B",
    )

    authority = document["authority"]
    required_true = (
        "autonomous_internal_planning",
        "autonomous_internal_work_order_creation",
        "autonomous_progress_analysis",
        "autonomous_internal_reconciliation",
    )
    for key in required_true:
        _require(authority[key] is True, f"{key} must remain enabled")

    required_false = (
        "automatic_external_commitment_allowed",
        "self_approval_allowed",
        "automatic_merge_allowed",
        "external_action_performed",
    )
    for key in required_false:
        _require(authority[key] is False, f"{key} must remain false")

    for entry in authority["matrix"]:
        if entry["automatic"] is True and entry["separate_approval_required"] is False:
            _require(
                entry["action"]
                in {
                    "read_approved_employer_evidence",
                    "extract_duties_and_requirements",
                    "generate_internal_work_order_after_accepted_trigger",
                    "assign_approved_internal_agents",
                    "measure_progress_and_quality",
                },
                f"Unreviewed automatic authority is not allowlisted: {entry['action']}",
            )

    current_truth = document["current_truth"]
    _require(current_truth["external_action_performed"] is False, "Current truth cannot claim external action")

    first_incomplete = next(
        (stage for stage in sorted(stages, key=lambda item: int(item["order"])) if stage["status"] != "complete"),
        None,
    )
    _require(first_incomplete is not None, "At least one incomplete stage is expected before production admission")
    _require(
        document["next_admissible_action"]["stage_id"] == first_incomplete["stage_id"],
        "next_admissible_action must point to the first incomplete stage",
    )

    return document


def build_sequence_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    document = validate_sequence(payload)
    digest = hashlib.sha256(_canonical_json(document).encode("utf-8")).hexdigest()
    stages = sorted(document["critical_path"], key=lambda item: int(item["order"]))
    current_stage = next(stage for stage in stages if stage["status"] != "complete")
    return {
        "receipt_id": f"AIGC-CDAS-{digest[:20].upper()}",
        "contract_id": document["contract_id"],
        "contract_version": document["contract_version"],
        "sequence_sha256": digest,
        "current_stage_id": current_stage["stage_id"],
        "current_stage_status": current_stage["status"],
        "next_instruction": document["next_admissible_action"]["instruction"],
        "operator_review_required": True,
        "automatic_merge_allowed": False,
        "automatic_external_commitment_allowed": False,
        "external_action_performed": False,
    }


def main() -> int:
    sequence = load_sequence()
    print(json.dumps(build_sequence_receipt(sequence), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
