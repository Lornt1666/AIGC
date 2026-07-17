from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.core.contract_validator import validate_artifact


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "current_repository_truth_procurement.json"
SCHEMA_NAME = "current_repository_truth_procurement"


class TruthProcurementError(ValueError):
    """Raised when the truth-procurement ledger is structurally or semantically unsafe."""


@dataclass(frozen=True)
class ProcurementReceipt:
    receipt_id: str
    generated_at: str
    contract_id: str
    contract_version: str
    source_digest: str
    transition_target_count: int
    completed_transition_count: int
    safety_invariant_count: int
    next_transition_id: str
    next_transition_label: str
    next_accountable_actor: str
    next_status: str
    external_mutation_required: bool
    operator_review_required: bool
    required_actions: list[str]
    required_evidence: list[str]
    stop_conditions: list[str]
    safety_invariants_preserved: bool
    automatic_merge_allowed: bool
    automatic_external_commitment_allowed: bool
    external_action_performed: bool


@dataclass(frozen=True)
class CompletionEvaluation:
    truth_id: str
    ready: bool
    reasons: list[str]
    missing_dependencies: list[str]
    evidence_count: int
    required_evidence_count: int
    operator_attested: bool
    external_action_performed: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def load_procurement(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config_path = Path(path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TruthProcurementError("Truth procurement configuration must be a JSON object")
    validate_artifact(SCHEMA_NAME, payload)
    validate_semantics(payload)
    return payload


def validate_semantics(payload: Mapping[str, Any]) -> None:
    transitions = [dict(item) for item in payload.get("transition_targets") or []]
    invariants = [dict(item) for item in payload.get("safety_invariants") or []]
    if not transitions:
        raise TruthProcurementError("At least one transition target is required")
    if not invariants:
        raise TruthProcurementError("At least one safety invariant is required")

    transition_ids = [str(item["truth_id"]) for item in transitions]
    invariant_ids = [str(item["truth_id"]) for item in invariants]
    if len(set(transition_ids)) != len(transition_ids):
        raise TruthProcurementError("Transition truth IDs must be unique")
    if len(set(invariant_ids)) != len(invariant_ids):
        raise TruthProcurementError("Safety-invariant truth IDs must be unique")
    overlap = set(transition_ids).intersection(invariant_ids)
    if overlap:
        raise TruthProcurementError(
            "A truth cannot be both a completion target and a safety invariant: "
            + ", ".join(sorted(overlap))
        )

    orders = [int(item["order"]) for item in transitions]
    expected_orders = list(range(1, len(transitions) + 1))
    if orders != expected_orders:
        raise TruthProcurementError(
            f"Transition order must be contiguous and canonical: {expected_orders}"
        )

    seen: set[str] = set()
    for item in transitions:
        truth_id = str(item["truth_id"])
        current = bool(item["current_value"])
        desired = bool(item["desired_value"])
        status = str(item["status"])
        if desired is not True:
            raise TruthProcurementError(
                f"Completion target {truth_id} must have desired_value=true"
            )
        if status == "completed" and current is not True:
            raise TruthProcurementError(
                f"Completed transition {truth_id} must have current_value=true"
            )
        if status != "completed" and current is True:
            raise TruthProcurementError(
                f"Incomplete transition {truth_id} cannot claim current_value=true"
            )
        if not item.get("operator_review_required"):
            raise TruthProcurementError(
                f"Transition {truth_id} must require accountable operator review"
            )
        for field in ("required_actions", "required_evidence", "stop_conditions"):
            values = [str(value).strip() for value in item.get(field) or []]
            if not values or any(not value for value in values):
                raise TruthProcurementError(
                    f"Transition {truth_id} requires non-empty {field}"
                )
        dependencies = [str(value) for value in item.get("dependencies") or []]
        unknown = [value for value in dependencies if value not in transition_ids]
        if unknown:
            raise TruthProcurementError(
                f"Transition {truth_id} has unknown dependencies: {unknown}"
            )
        forward = [value for value in dependencies if value not in seen]
        if forward:
            raise TruthProcurementError(
                f"Transition {truth_id} has forward or self dependencies: {forward}"
            )
        seen.add(truth_id)

    for item in invariants:
        truth_id = str(item["truth_id"])
        if item.get("current_value") is not False:
            raise TruthProcurementError(
                f"Safety invariant {truth_id} must currently remain false"
            )
        if item.get("required_value") is not False:
            raise TruthProcurementError(
                f"Safety invariant {truth_id} must require false"
            )
        tests = [str(value).strip() for value in item.get("enforcement_tests") or []]
        if not tests or any(not value for value in tests):
            raise TruthProcurementError(
                f"Safety invariant {truth_id} requires enforcement tests"
            )

    policy = dict(payload.get("procurement_policy") or {})
    required_policy_truths = (
        "false_is_not_automatically_a_defect",
        "completion_requires_evidence",
        "authority_does_not_substitute_for_evidence",
        "first_incomplete_transition_is_next",
        "no_direct_main_write",
        "no_new_product_train",
    )
    for key in required_policy_truths:
        if policy.get(key) is not True:
            raise TruthProcurementError(f"Procurement policy {key} must remain true")

    summary = dict(payload.get("current_summary") or {})
    completed_count = sum(1 for item in transitions if item["current_value"] is True)
    next_item = next((item for item in transitions if item["current_value"] is False), None)
    expected_next = str(next_item["truth_id"]) if next_item else "ALL_TRANSITIONS_COMPLETE"
    if int(summary.get("transition_target_count", -1)) != len(transitions):
        raise TruthProcurementError("current_summary transition target count is stale")
    if int(summary.get("completed_transition_count", -1)) != completed_count:
        raise TruthProcurementError("current_summary completed count is stale")
    if int(summary.get("safety_invariant_count", -1)) != len(invariants):
        raise TruthProcurementError("current_summary safety-invariant count is stale")
    if str(summary.get("next_transition_id")) != expected_next:
        raise TruthProcurementError(
            f"current_summary next transition must be {expected_next}"
        )
    if summary.get("external_action_performed") is not False:
        raise TruthProcurementError(
            "The procurement artifact itself cannot claim external action"
        )


def first_incomplete_transition(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    validate_semantics(payload)
    return next(
        (
            dict(item)
            for item in payload.get("transition_targets") or []
            if item.get("current_value") is False
        ),
        None,
    )


def build_receipt(payload: Mapping[str, Any]) -> ProcurementReceipt:
    validate_semantics(payload)
    transitions = [dict(item) for item in payload["transition_targets"]]
    invariants = [dict(item) for item in payload["safety_invariants"]]
    next_item = first_incomplete_transition(payload)
    if next_item is None:
        next_item = {
            "truth_id": "ALL_TRANSITIONS_COMPLETE",
            "label": "All evidence-backed transition targets are complete",
            "accountable_actor": "ACCOUNTABLE_OPERATOR",
            "status": "completed",
            "external_mutation_required": False,
            "operator_review_required": True,
            "required_actions": ["Perform final accountable production-readiness review"],
            "required_evidence": ["Final readiness receipt"],
            "stop_conditions": ["Any evidence or binding is stale"],
        }
    source_digest = _digest(payload)
    receipt_id = "AIGC-TRUTH-PROCUREMENT-" + source_digest[:24].upper()
    return ProcurementReceipt(
        receipt_id=receipt_id,
        generated_at=_now(),
        contract_id=str(payload["contract_id"]),
        contract_version=str(payload["contract_version"]),
        source_digest=source_digest,
        transition_target_count=len(transitions),
        completed_transition_count=sum(
            1 for item in transitions if item["current_value"] is True
        ),
        safety_invariant_count=len(invariants),
        next_transition_id=str(next_item["truth_id"]),
        next_transition_label=str(next_item["label"]),
        next_accountable_actor=str(next_item["accountable_actor"]),
        next_status=str(next_item["status"]),
        external_mutation_required=bool(next_item["external_mutation_required"]),
        operator_review_required=bool(next_item["operator_review_required"]),
        required_actions=[str(value) for value in next_item["required_actions"]],
        required_evidence=[str(value) for value in next_item["required_evidence"]],
        stop_conditions=[str(value) for value in next_item["stop_conditions"]],
        safety_invariants_preserved=all(
            item["current_value"] is False and item["required_value"] is False
            for item in invariants
        ),
        automatic_merge_allowed=False,
        automatic_external_commitment_allowed=False,
        external_action_performed=False,
    )


def evaluate_completion_request(
    payload: Mapping[str, Any],
    truth_id: str,
    *,
    evidence_ids: Sequence[str] = (),
    operator_attested: bool = False,
) -> CompletionEvaluation:
    validate_semantics(payload)
    transitions = {
        str(item["truth_id"]): dict(item)
        for item in payload["transition_targets"]
    }
    target = transitions.get(truth_id)
    if target is None:
        raise TruthProcurementError(f"Unknown transition target: {truth_id}")

    missing_dependencies = [
        dependency
        for dependency in target.get("dependencies") or []
        if transitions[dependency]["current_value"] is not True
    ]
    normalized_evidence = [str(value).strip() for value in evidence_ids if str(value).strip()]
    required_evidence_count = len(target.get("required_evidence") or [])
    reasons: list[str] = []
    if target["current_value"] is True:
        reasons.append("Transition is already complete")
    if missing_dependencies:
        reasons.append("Required predecessor transitions are incomplete")
    if len(normalized_evidence) < required_evidence_count:
        reasons.append("Insufficient evidence references for the configured completion rule")
    if not operator_attested:
        reasons.append("Accountable operator attestation is required")
    if target["status"] == "blocked" and not normalized_evidence:
        reasons.append("Blocked transition has no recovery evidence")

    return CompletionEvaluation(
        truth_id=truth_id,
        ready=not reasons,
        reasons=reasons,
        missing_dependencies=missing_dependencies,
        evidence_count=len(normalized_evidence),
        required_evidence_count=required_evidence_count,
        operator_attested=operator_attested,
        external_action_performed=False,
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate AIGC unresolved-truth procurement and emit the next action"
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    payload = load_procurement(args.config)
    receipt = build_receipt(payload)
    rendered = asdict(receipt)
    if args.output:
        _write_json(Path(args.output), rendered)
    print(json.dumps(rendered, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
