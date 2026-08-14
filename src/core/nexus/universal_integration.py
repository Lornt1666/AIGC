"""Deterministic readiness evaluation for AIGC integration surfaces.

This module is intentionally pure and performs no network, cloud, billing,
repository, provider, store, marketplace, or public-traffic action.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # The repository CI installs jsonschema from requirements.txt.
    Draft202012Validator = None  # type: ignore[assignment]


class RegistryValidationError(ValueError):
    """Raised when a registry violates the fail-closed core contract."""


@dataclass(frozen=True, slots=True)
class IntegrationReadiness:
    registry_sha256: str
    applicable_required_checks: int
    verified_required_checks: int
    verified_applicable_ratio: float
    production_ready: bool
    blockers: tuple[str, ...]
    authority_granted: bool = False
    external_action_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_sha256": self.registry_sha256,
            "applicable_required_checks": self.applicable_required_checks,
            "verified_required_checks": self.verified_required_checks,
            "verified_applicable_ratio": self.verified_applicable_ratio,
            "production_ready": self.production_ready,
            "blockers": list(self.blockers),
            "authority_granted": self.authority_granted,
            "external_action_performed": self.external_action_performed,
        }


def canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_and_validate_registry(registry_path: Path, schema_path: Path) -> dict[str, Any]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    _validate_core_contract(registry)
    if Draft202012Validator is not None:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(registry)
    return registry


def _validate_core_contract(registry: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "registry_id",
        "template_only",
        "release_binding",
        "subsystems",
        "surfaces",
        "connectors",
        "authority",
        "completion_policy",
    }
    missing = sorted(required.difference(registry))
    if missing:
        raise RegistryValidationError(f"missing required fields: {', '.join(missing)}")
    if registry["schema_version"] != "aigc.universal-integration-registry.v1":
        raise RegistryValidationError("unsupported schema_version")
    if registry["release_binding"].get("repository") != "Lornt1666/AIGC":
        raise RegistryValidationError("release_binding.repository must be Lornt1666/AIGC")

    valid_statuses = {
        "not_implemented",
        "proposed",
        "implemented",
        "verified",
        "blocked",
        "not_applicable",
    }
    subsystem_ids: set[str] = set()
    for subsystem in registry["subsystems"]:
        subsystem_id = subsystem.get("id")
        if not subsystem_id or subsystem_id in subsystem_ids:
            raise RegistryValidationError("subsystem ids must be present and unique")
        subsystem_ids.add(subsystem_id)
        if subsystem.get("status") not in valid_statuses:
            raise RegistryValidationError(f"invalid subsystem status: {subsystem_id}")
        if subsystem.get("verification_scope") != "LOCAL_CONTRACT_ONLY":
            raise RegistryValidationError(
                f"subsystem {subsystem_id} verification scope must remain LOCAL_CONTRACT_ONLY"
            )
        contracts = set(subsystem.get("contracts", ()))
        receipt_keys = set(subsystem.get("evidence_receipts", {}))
        unknown_receipts = sorted(receipt_keys.difference(contracts))
        if unknown_receipts:
            raise RegistryValidationError(
                f"subsystem {subsystem_id} has receipts for undeclared contracts: "
                + ", ".join(unknown_receipts)
            )
        if subsystem.get("authority_granted") is not False:
            raise RegistryValidationError(f"subsystem {subsystem_id} cannot grant authority")
        if subsystem.get("external_action_performed") is not False:
            raise RegistryValidationError(f"subsystem {subsystem_id} cannot claim an external action")

    for collection in ("surfaces", "connectors"):
        seen: set[str] = set()
        for item in registry[collection]:
            item_id = item.get("id")
            if not item_id or item_id in seen:
                raise RegistryValidationError(f"{collection} ids must be present and unique")
            seen.add(item_id)
            if item.get("status") not in valid_statuses:
                raise RegistryValidationError(f"invalid {collection} status: {item_id}")
            if collection == "surfaces":
                required_evidence = set(item.get("required_evidence", ()))
                receipt_keys = set(item.get("evidence_receipts", {}))
                unknown_receipts = sorted(receipt_keys.difference(required_evidence))
                if unknown_receipts:
                    raise RegistryValidationError(
                        f"surface {item_id} has receipts for undeclared evidence: "
                        + ", ".join(unknown_receipts)
                    )
            elif collection == "connectors":
                certification = item.get("certification", {})
                terms_reviewed = certification.get("terms_reviewed") is True
                terms_receipt = certification.get("terms_review_receipt_id")
                if terms_reviewed != (isinstance(terms_receipt, str) and bool(terms_receipt)):
                    raise RegistryValidationError(
                        f"connector {item_id} terms review and receipt must be bound together"
                    )

    threshold = registry["completion_policy"].get("minimum_verified_applicable_ratio")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0 <= threshold <= 1:
        raise RegistryValidationError("minimum_verified_applicable_ratio must be between 0 and 1")
    if registry["completion_policy"].get("unknowns_block_release") is not True:
        raise RegistryValidationError("unknowns_block_release must remain true")


def evaluate_registry(registry: Mapping[str, Any]) -> IntegrationReadiness:
    blockers: set[str] = set()
    applicable = 0
    verified = 0

    if registry.get("template_only") is True:
        blockers.add("registry remains template_only")

    release = registry["release_binding"]
    if release["evidence_state"] != "current":
        blockers.add(f"release evidence is {release['evidence_state']}")

    for subsystem in registry["subsystems"]:
        applicable += 1
        contracts = subsystem["contracts"]
        receipt_keys = set(subsystem["evidence_receipts"])
        verified_count = sum(1 for contract in contracts if contract in receipt_keys)
        if subsystem["status"] == "verified" and verified_count == len(contracts):
            verified += 1
        else:
            blockers.add(
                f"subsystem {subsystem['id']} is {subsystem['status']} with "
                f"{verified_count}/{len(contracts)} receipt-bound contracts"
            )

    for surface in registry["surfaces"]:
        if not surface["required_for_v1"]:
            continue
        required_evidence = surface["required_evidence"]
        applicable += max(1, len(required_evidence))
        evidence_receipts = surface["evidence_receipts"]
        verified_count = sum(1 for item in required_evidence if item in evidence_receipts)
        if surface["status"] in {"implemented", "verified"}:
            verified += verified_count
        if surface["status"] != "verified" or verified_count != len(required_evidence):
            blockers.add(
                f"required surface {surface['id']} is {surface['status']} with "
                f"{verified_count}/{len(required_evidence)} receipt-bound checks"
            )

    for connector in registry["connectors"]:
        if not connector["required_for_v1"]:
            continue
        certification = connector["certification"]
        checks = (
            connector["status"] == "verified",
            certification["terms_reviewed"] and bool(certification["terms_review_receipt_id"]),
            certification["identity_bound"],
            certification["scope_bound"],
            certification["recovery_tested"],
            bool(certification["live_receipt_ids"]),
        )
        applicable += len(checks)
        verified += sum(bool(check) for check in checks)
        if not all(checks):
            blockers.add(f"required connector {connector['id']} is not fully certified")

    authority = registry["authority"]
    for key in registry["completion_policy"]["required_authorities"]:
        applicable += 1
        if authority.get(key) is True:
            verified += 1
        else:
            blockers.add(f"required authority {key} is false")

    ratio = verified / applicable if applicable else 0.0
    threshold = registry["completion_policy"]["minimum_verified_applicable_ratio"]
    production_ready = ratio >= threshold and not blockers

    return IntegrationReadiness(
        registry_sha256=canonical_sha256(registry),
        applicable_required_checks=applicable,
        verified_required_checks=verified,
        verified_applicable_ratio=round(ratio, 6),
        production_ready=production_ready,
        blockers=tuple(sorted(blockers)),
    )
