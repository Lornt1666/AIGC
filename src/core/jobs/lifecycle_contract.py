from __future__ import annotations

from collections import deque
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class JobLifecycleContractError(ValueError):
    """Raised when a lifecycle contract is structurally unsafe or ambiguous."""


def load_json_object(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise JobLifecycleContractError(f"Expected JSON object: {file_path}")
    return payload


def canonical_digest(payload: Mapping[str, Any]) -> str:
    material = json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256(material.encode("utf-8")).hexdigest()


def _duplicates(values: Sequence[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def analyze_lifecycle_contract(contract: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    states = list(contract.get("states") or [])
    transitions = list(contract.get("transitions") or [])
    authority_classes = {str(item) for item in contract.get("authority_classes") or []}

    state_ids = [str(item.get("state_id") or "") for item in states if isinstance(item, Mapping)]
    transition_ids = [
        str(item.get("transition_id") or "")
        for item in transitions
        if isinstance(item, Mapping)
    ]

    for duplicate in sorted(_duplicates(state_ids)):
        findings.append(f"DUPLICATE_STATE:{duplicate}")
    for duplicate in sorted(_duplicates(transition_ids)):
        findings.append(f"DUPLICATE_TRANSITION:{duplicate}")

    if "ACCEPTED" in state_ids:
        findings.append("AMBIGUOUS_GENERIC_ACCEPTED_STATE")

    initial_states = [
        str(item.get("state_id"))
        for item in states
        if isinstance(item, Mapping) and item.get("initial") is True
    ]
    if len(initial_states) != 1:
        findings.append(f"INITIAL_STATE_COUNT:{len(initial_states)}")

    state_set = set(state_ids)
    terminal_states = {
        str(item.get("state_id"))
        for item in states
        if isinstance(item, Mapping) and item.get("terminal") is True
    }
    outgoing: dict[str, set[str]] = {state_id: set() for state_id in state_set}

    for transition in transitions:
        if not isinstance(transition, Mapping):
            findings.append("TRANSITION_NOT_OBJECT")
            continue
        transition_id = str(transition.get("transition_id") or "UNKNOWN")
        from_state = str(transition.get("from_state") or "")
        to_state = str(transition.get("to_state") or "")
        authority_class = str(transition.get("authority_class") or "")

        if from_state not in state_set:
            findings.append(f"UNDEFINED_FROM_STATE:{transition_id}:{from_state}")
        if to_state not in state_set:
            findings.append(f"UNDEFINED_TO_STATE:{transition_id}:{to_state}")
        if authority_class not in authority_classes:
            findings.append(f"UNDEFINED_AUTHORITY_CLASS:{transition_id}:{authority_class}")
        if from_state in outgoing and to_state:
            outgoing[from_state].add(to_state)

        if transition.get("action_effect") == "EXTERNALLY_CONSEQUENTIAL":
            findings.append(f"EXTERNAL_ACTION_INSIDE_LIFECYCLE:{transition_id}")

    for state_id in sorted(terminal_states):
        if outgoing.get(state_id):
            findings.append(f"TERMINAL_STATE_HAS_OUTBOUND:{state_id}")

    if len(initial_states) == 1:
        reachable: set[str] = set()
        queue: deque[str] = deque(initial_states)
        while queue:
            current = queue.popleft()
            if current in reachable:
                continue
            reachable.add(current)
            queue.extend(sorted(outgoing.get(current, set()) - reachable))
        for state_id in sorted(state_set - reachable):
            findings.append(f"UNREACHABLE_STATE:{state_id}")

    if contract.get("external_action_performed") is not False:
        findings.append("EXTERNAL_ACTION_FLAG_MUST_BE_FALSE")

    delivered_edges = [
        transition
        for transition in transitions
        if isinstance(transition, Mapping) and transition.get("to_state") == "DELIVERED"
    ]
    if not delivered_edges:
        findings.append("DELIVERED_TRANSITION_MISSING")
    for transition in delivered_edges:
        transition_id = str(transition.get("transition_id") or "UNKNOWN")
        evidence = {str(item) for item in transition.get("evidence_required") or []}
        if transition.get("external_action_boundary") != "SEPARATE_CONNECTOR_RECEIPT_REQUIRED":
            findings.append(f"DELIVERY_BOUNDARY_MISSING:{transition_id}")
        if "DELIVERY_EXECUTION_RECEIPT" not in evidence:
            findings.append(f"DELIVERY_RECEIPT_MISSING:{transition_id}")

    if "WORK_ACCEPTED" not in state_set:
        findings.append("WORK_ACCEPTED_STATE_MISSING")
    if "ACCEPTED_FOR_DELIVERY" not in state_set:
        findings.append("ACCEPTED_FOR_DELIVERY_STATE_MISSING")

    return findings


def analyze_compatibility_map(
    contract: Mapping[str, Any],
    compatibility_map: Mapping[str, Any],
) -> list[str]:
    findings: list[str] = []
    state_ids = {
        str(item.get("state_id"))
        for item in contract.get("states") or []
        if isinstance(item, Mapping)
    }

    if compatibility_map.get("canonical_contract_id") != contract.get("contract_id"):
        findings.append("CANONICAL_CONTRACT_ID_MISMATCH")
    if compatibility_map.get("canonical_contract_version") != contract.get("version"):
        findings.append("CANONICAL_CONTRACT_VERSION_MISMATCH")

    source_ids: list[str] = []
    for source in compatibility_map.get("source_contracts") or []:
        if not isinstance(source, Mapping):
            findings.append("SOURCE_CONTRACT_NOT_OBJECT")
            continue
        source_id = str(source.get("source_contract_id") or "")
        source_ids.append(source_id)
        source_states: list[str] = []
        for mapping in source.get("mappings") or []:
            if not isinstance(mapping, Mapping):
                findings.append(f"MAPPING_NOT_OBJECT:{source_id}")
                continue
            source_state = str(mapping.get("source_state") or "")
            source_states.append(source_state)
            target_state = mapping.get("target_state")
            status = str(mapping.get("status") or "")
            decision_required = mapping.get("operator_decision_required") is True

            if target_state is not None and str(target_state) not in state_ids:
                findings.append(f"UNKNOWN_TARGET_STATE:{source_id}:{source_state}:{target_state}")
            if status in {"CONFLICTING", "UNSUPPORTED", "TRANSITION_EXPANSION_REQUIRED"} and not decision_required:
                findings.append(f"OPERATOR_DECISION_REQUIRED:{source_id}:{source_state}")

        for duplicate in sorted(_duplicates(source_states)):
            findings.append(f"DUPLICATE_SOURCE_STATE:{source_id}:{duplicate}")

    for duplicate in sorted(_duplicates(source_ids)):
        findings.append(f"DUPLICATE_SOURCE_CONTRACT:{duplicate}")

    if compatibility_map.get("operator_review_required") is not True:
        findings.append("COMPATIBILITY_OPERATOR_REVIEW_REQUIRED")
    if compatibility_map.get("external_action_performed") is not False:
        findings.append("COMPATIBILITY_EXTERNAL_ACTION_FLAG_MUST_BE_FALSE")

    return findings


def build_reconciliation_report(
    contract: Mapping[str, Any],
    compatibility_map: Mapping[str, Any],
    *,
    source_revision: str,
) -> dict[str, Any]:
    if not isinstance(source_revision, str) or len(source_revision.strip()) < 7:
        raise JobLifecycleContractError("SOURCE_REVISION_REQUIRED")

    structural_findings = analyze_lifecycle_contract(contract)
    compatibility_findings = analyze_compatibility_map(contract, compatibility_map)
    unresolved_conflicts = [
        dict(item)
        for item in compatibility_map.get("unresolved_conflicts") or []
        if isinstance(item, Mapping)
    ]
    blocking_conflicts = [
        item for item in unresolved_conflicts if item.get("severity") == "BLOCKING"
    ]

    return {
        "report_id": "AIGC-JOB-LIFECYCLE-RECONCILIATION-" + canonical_digest(
            {
                "contract_digest": canonical_digest(contract),
                "compatibility_digest": canonical_digest(compatibility_map),
                "source_revision": source_revision,
            }
        )[:24].upper(),
        "source_revision": source_revision,
        "contract_id": contract.get("contract_id"),
        "contract_version": contract.get("version"),
        "contract_digest": canonical_digest(contract),
        "compatibility_map_digest": canonical_digest(compatibility_map),
        "state_count": len(contract.get("states") or []),
        "transition_count": len(contract.get("transitions") or []),
        "structural_findings": structural_findings,
        "compatibility_findings": compatibility_findings,
        "unresolved_conflicts": unresolved_conflicts,
        "blocking_conflict_count": len(blocking_conflicts),
        "ready_for_runtime_integration": not structural_findings
        and not compatibility_findings
        and not unresolved_conflicts
        and contract.get("status") == "RATIFIED",
        "operator_review_required": True,
        "external_action_performed": False,
    }


def require_structurally_valid(
    contract: Mapping[str, Any],
    compatibility_map: Mapping[str, Any],
) -> None:
    findings = analyze_lifecycle_contract(contract) + analyze_compatibility_map(
        contract, compatibility_map
    )
    if findings:
        raise JobLifecycleContractError(";".join(findings))
