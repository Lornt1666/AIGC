"""Pure, fail-closed contracts for the five AIGC coordination subsystems.

The functions in this module perform deterministic local validation only.
They never grant authority, resolve credentials, call providers, or mutate an
external system.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # CI installs jsonschema from requirements.txt.
    Draft202012Validator = None  # type: ignore[assignment]


REQUIRED_SUBSYSTEMS = {
    "silva",
    "hexgate",
    "vanis",
    "correlation_station",
    "chorus",
}
HEXGATE_GATES = {"identity", "authorization", "privacy", "safety", "cost", "evidence"}


class SubsystemContractError(ValueError):
    """Raised when a subsystem contract or deterministic fixture is invalid."""


def canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_contract_set(config_path: Path, schema_path: Path) -> dict[str, Any]:
    contract_set = json.loads(config_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validate_contract_set(contract_set)
    if Draft202012Validator is not None:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(contract_set)
    return contract_set


def validate_contract_set(contract_set: Mapping[str, Any]) -> None:
    if contract_set.get("schema_version") != "aigc.subsystem-contract-set.v1":
        raise SubsystemContractError("unsupported subsystem contract schema_version")
    if contract_set.get("verification_scope") != "LOCAL_CONTRACT_ONLY":
        raise SubsystemContractError("verification_scope must remain LOCAL_CONTRACT_ONLY")
    if contract_set.get("authority_granted") is not False:
        raise SubsystemContractError("contract set cannot grant authority")
    if contract_set.get("external_action_performed") is not False:
        raise SubsystemContractError("contract set cannot claim external action")

    subsystem_ids: set[str] = set()
    for subsystem in contract_set.get("subsystems", ()):
        subsystem_id = subsystem.get("id")
        if subsystem_id in subsystem_ids:
            raise SubsystemContractError(f"duplicate subsystem id: {subsystem_id}")
        subsystem_ids.add(subsystem_id)
        if subsystem.get("authority_granted") is not False:
            raise SubsystemContractError(f"subsystem {subsystem_id} cannot grant authority")
        if subsystem.get("external_effects_allowed") is not False:
            raise SubsystemContractError(f"subsystem {subsystem_id} cannot allow external effects")
        contract_ids = [item.get("id") for item in subsystem.get("contracts", ())]
        if not contract_ids or len(contract_ids) != len(set(contract_ids)):
            raise SubsystemContractError(f"subsystem {subsystem_id} contracts must be present and unique")

    if subsystem_ids != REQUIRED_SUBSYSTEMS:
        missing = sorted(REQUIRED_SUBSYSTEMS.difference(subsystem_ids))
        extra = sorted(subsystem_ids.difference(REQUIRED_SUBSYSTEMS))
        raise SubsystemContractError(f"subsystem set mismatch; missing={missing}; extra={extra}")


def evaluate_silva(matrix: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not matrix:
        raise SubsystemContractError("SILVA requires at least one platform result")
    allowed = {"PASS", "FAIL", "UNVERIFIED"}
    for entry in matrix:
        if not entry.get("platform") or entry.get("status") not in allowed:
            raise SubsystemContractError("SILVA platform results require a platform and valid status")
    failed = sorted(
        str(entry["platform"])
        for entry in matrix
        if entry.get("required", True) and entry["status"] != "PASS"
    )
    return {
        "terminal_status": "PASS" if not failed else "BLOCKED",
        "failed_required_platforms": failed,
        "authority_granted": False,
        "external_action_performed": False,
    }


def evaluate_hexgate(gates: Mapping[str, bool]) -> dict[str, Any]:
    if set(gates) != HEXGATE_GATES or any(type(value) is not bool for value in gates.values()):
        raise SubsystemContractError("HexGate requires exactly six boolean gates")
    failed = sorted(key for key, value in gates.items() if not value)
    return {
        "terminal_status": "PASS" if not failed else "BLOCKED_PERMISSION",
        "failed_gates": failed,
        "simulation_admitted": not failed,
        "authority_granted": False,
        "external_action_performed": False,
    }


def evaluate_vanis(request: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "provider",
        "capability",
        "provider_allowlisted",
        "capability_allowlisted",
        "estimated_cost",
        "budget_ceiling",
    }
    if set(request) != required:
        raise SubsystemContractError("VANIS request fields must match the closed contract")
    estimated = request["estimated_cost"]
    ceiling = request["budget_ceiling"]
    if (
        type(request["provider_allowlisted"]) is not bool
        or type(request["capability_allowlisted"]) is not bool
        or not isinstance(estimated, (int, float))
        or isinstance(estimated, bool)
        or not isinstance(ceiling, (int, float))
        or isinstance(ceiling, bool)
        or estimated < 0
        or ceiling < 0
    ):
        raise SubsystemContractError("VANIS allowlist and budget fields are invalid")
    blockers = []
    if not request["provider_allowlisted"]:
        blockers.append("provider_not_allowlisted")
    if not request["capability_allowlisted"]:
        blockers.append("capability_not_allowlisted")
    if estimated > ceiling:
        blockers.append("budget_exceeded")
    return {
        "terminal_status": "PASS" if not blockers else "BLOCKED",
        "blockers": blockers,
        "local_route_selected": not blockers,
        "provider_dispatch_performed": False,
        "authority_granted": False,
        "external_action_performed": False,
    }


def evaluate_correlation_station(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    for event in events:
        event_id = event.get("id")
        parents = event.get("parent_ids")
        if not isinstance(event_id, str) or not event_id or event_id in seen:
            raise SubsystemContractError("Correlation Station event ids must be present and unique")
        if not isinstance(parents, list) or any(parent not in seen for parent in parents):
            raise SubsystemContractError("Correlation Station parents must reference earlier events")
        if event.get("authority_granted") is not False:
            raise SubsystemContractError("evidence lineage cannot grant authority")
        seen.add(event_id)
    return {
        "terminal_status": "PASS",
        "event_count": len(seen),
        "lineage_valid": True,
        "authority_granted": False,
        "external_action_performed": False,
    }


def evaluate_chorus(intent: Mapping[str, Any]) -> dict[str, Any]:
    if set(intent) != {"summary", "consequential", "approval_presented"}:
        raise SubsystemContractError("CHORUS intent fields must match the closed contract")
    if not isinstance(intent["summary"], str) or not intent["summary"].strip():
        raise SubsystemContractError("CHORUS requires a non-empty human-readable summary")
    if type(intent["consequential"]) is not bool or type(intent["approval_presented"]) is not bool:
        raise SubsystemContractError("CHORUS flags must be boolean")
    consequential = intent["consequential"]
    presented = intent["approval_presented"]
    return {
        "terminal_status": "AWAITING_HUMAN_APPROVAL" if consequential else "PASS",
        "approval_required": consequential,
        "approval_presented": presented,
        "execution_allowed": not consequential,
        "consent_inferred": False,
        "authority_granted": False,
        "external_action_performed": False,
    }


def build_local_validation_receipt(contract_set: Mapping[str, Any]) -> dict[str, Any]:
    validate_contract_set(contract_set)
    results = {
        "silva": evaluate_silva([{"platform": "linux-local", "required": True, "status": "PASS"}]),
        "hexgate": evaluate_hexgate({key: True for key in sorted(HEXGATE_GATES)}),
        "vanis": evaluate_vanis(
            {
                "provider": "local-fixture",
                "capability": "deterministic-validation",
                "provider_allowlisted": True,
                "capability_allowlisted": True,
                "estimated_cost": 0,
                "budget_ceiling": 0,
            }
        ),
        "correlation_station": evaluate_correlation_station(
            [
                {"id": "artifact", "parent_ids": [], "authority_granted": False},
                {"id": "verification", "parent_ids": ["artifact"], "authority_granted": False},
            ]
        ),
        "chorus": evaluate_chorus(
            {
                "summary": "Present a consequential action for explicit human review.",
                "consequential": True,
                "approval_presented": True,
            }
        ),
    }
    contract_hash = canonical_sha256(contract_set)
    payload: dict[str, Any] = {
        "schema_version": "aigc.subsystem-validation-receipt.v1",
        "verification_scope": "LOCAL_CONTRACT_ONLY",
        "contract_set_sha256": contract_hash,
        "terminal_status": "PASS",
        "subsystem_results": results,
        "provider_calls_performed": 0,
        "credentials_accessed": False,
        "authority_granted": False,
        "external_action_performed": False,
    }
    receipt_hash = canonical_sha256(payload)
    payload["receipt_sha256"] = receipt_hash
    payload["receipt_id"] = f"SUBSYS-{receipt_hash[:24].upper()}"
    return payload
