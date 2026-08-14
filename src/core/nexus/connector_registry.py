from __future__ import annotations

"""Machine-enforced connector passports derived from the AIGC constitution."""

import json
from pathlib import Path
from typing import Any

from src.domain.nexus.connectors import (
    ConnectorActionDecision,
    ConnectorCapability,
    ConnectorPassport,
    ConnectorStage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = (
    PROJECT_ROOT / "config" / "aigc_employment_connector_registry.v1.json"
)


class ConnectorRegistry:
    def __init__(self, passports: tuple[ConnectorPassport, ...]) -> None:
        if not passports:
            raise ValueError("connector registry cannot be empty")
        keyed = {item.connector_id: item for item in passports}
        if len(keyed) != len(passports):
            raise ValueError("duplicate connector passport")
        self._passports = keyed

    @classmethod
    def from_constitution(cls, path: Path = DEFAULT_REGISTRY_PATH) -> "ConnectorRegistry":
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("connectors"), list):
            raise ValueError("constitution connectors must be a list")
        passports = tuple(
            ConnectorPassport(
                connector_id=item["id"],
                name=item["name"],
                owner=item["owner"],
                certification_status=item["certification_status"],
                identity_binding=item["identity_binding"],
                terms_binding=item["terms_binding"],
                capabilities=tuple(
                    ConnectorCapability.model_validate(capability)
                    for capability in item["capabilities"]
                ),
            )
            for item in value["connectors"]
        )
        return cls(passports)

    def passports(self) -> tuple[ConnectorPassport, ...]:
        return tuple(self._passports[key] for key in sorted(self._passports))

    def assess(self, connector_id: str, action: str, stage: ConnectorStage) -> ConnectorActionDecision:
        try:
            passport = self._passports[connector_id]
        except KeyError:
            return ConnectorActionDecision(
                connector_id=connector_id,
                action=action,
                stage=stage,
                connector_status="NOT_IMPLEMENTED",
                capability_status="NOT_IMPLEMENTED",
                disposition="BLOCKED",
                reason="connector passport is absent",
            )

        capability = next(
            (
                item
                for item in passport.capabilities
                if item.action == action and item.stage == stage
            ),
            None,
        )
        if capability is None:
            return ConnectorActionDecision(
                connector_id=connector_id,
                action=action,
                stage=stage,
                connector_status=passport.certification_status,
                capability_status="NOT_IMPLEMENTED",
                disposition="BLOCKED",
                reason="action and stage are not declared by the connector passport",
            )

        if capability.status == "HUMAN_HANDOFF":
            disposition = "HUMAN_HANDOFF_REQUIRED"
        elif capability.status == "DRAFT_ONLY" and stage in {"DRAFT", "SIMULATE"}:
            disposition = "LOCAL_PREPARATION_ONLY"
        elif capability.status == "READ_ONLY" and stage in {"OBSERVE", "VERIFY", "RECONCILE"}:
            disposition = "PROCEED_TO_AUTHORITY_GATE"
        elif capability.status == "CERTIFIED":
            disposition = "PROCEED_TO_AUTHORITY_GATE"
        else:
            disposition = "BLOCKED"

        admitted = disposition in {"PROCEED_TO_AUTHORITY_GATE", "LOCAL_PREPARATION_ONLY"}
        return ConnectorActionDecision(
            connector_id=connector_id,
            action=action,
            stage=stage,
            connector_status=passport.certification_status,
            capability_status=capability.status,
            disposition=disposition,
            reason=capability.reason,
            capability_admitted=admitted,
            live_mutation_possible=bool(
                admitted
                and passport.certification_status == "CERTIFIED"
                and capability.live_mutation_allowed
            ),
        )

    def status_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "connector_id": passport.connector_id,
                "name": passport.name,
                "status": passport.certification_status,
                "capability_count": len(passport.capabilities),
                "live_mutation_capability_count": sum(
                    1 for item in passport.capabilities if item.live_mutation_allowed
                ),
                "authority_granted": False,
            }
            for passport in self.passports()
        ]


def build_connector_status_snapshot() -> list[dict[str, Any]]:
    return ConnectorRegistry.from_constitution().status_snapshot()
