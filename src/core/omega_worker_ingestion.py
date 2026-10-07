from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import json
from pathlib import Path

from .omega_worker_runtime import OmegaWorkerRuntime, WorkerEvent


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPPORTUNITY_SCHEMA = PROJECT_ROOT / "schemas" / "aigc_omega_worker_v0_1" / "opportunity_contract.schema.json"


class InvalidOpportunity(ValueError):
    pass


@dataclass(frozen=True)
class IngestionResult:
    opportunity_id: str
    accepted: bool
    disposition: str
    event: WorkerEvent


class OpportunityIngestor:
    """Validates the v0.1 OpportunityContract and binds it to a non-destructive runtime event."""

    REQUIRED = (
        "contract_version", "opportunity_id", "source", "title",
        "classification", "commercial", "fit", "risk", "decision",
    )

    def __init__(self, runtime: OmegaWorkerRuntime | None = None):
        self.runtime = runtime or OmegaWorkerRuntime()

    def validate(self, opportunity: Mapping[str, Any]) -> None:
        if set(opportunity) - set(self.REQUIRED):
            raise InvalidOpportunity("Opportunity contains unsupported top-level fields.")
        missing = [key for key in self.REQUIRED if key not in opportunity]
        if missing:
            raise InvalidOpportunity(f"Missing required fields: {', '.join(missing)}")
        if opportunity["contract_version"] != "AIGC-OMEGA-OPPORTUNITY-0.1":
            raise InvalidOpportunity("Unsupported opportunity contract version.")
        if not isinstance(opportunity["opportunity_id"], str) or not opportunity["opportunity_id"]:
            raise InvalidOpportunity("opportunity_id must be a non-empty string.")
        if not isinstance(opportunity["title"], str) or not opportunity["title"]:
            raise InvalidOpportunity("title must be a non-empty string.")
        if opportunity["decision"] not in {"PENDING", "TARGET", "REJECT", "ESCALATE"}:
            raise InvalidOpportunity("Invalid opportunity decision.")
        if not isinstance(opportunity["source"], Mapping) or not {"kind", "locator"} <= set(opportunity["source"]):
            raise InvalidOpportunity("source requires kind and locator.")
        for section in ("classification", "commercial", "fit", "risk"):
            if not isinstance(opportunity[section], Mapping):
                raise InvalidOpportunity(f"{section} must be an object.")
        score = opportunity["fit"].get("capability_score")
        strategic = opportunity["fit"].get("strategic_score")
        if not isinstance(score, (int, float)) or not 0 <= score <= 100:
            raise InvalidOpportunity("capability_score must be between 0 and 100.")
        if not isinstance(strategic, (int, float)) or not 0 <= strategic <= 100:
            raise InvalidOpportunity("strategic_score must be between 0 and 100.")
        if opportunity["risk"].get("level") not in {"low", "medium", "high", "critical"}:
            raise InvalidOpportunity("Invalid risk level.")

    def ingest(self, opportunity: Mapping[str, Any], *, iteration_id: str) -> IngestionResult:
        self.validate(opportunity)
        decision = opportunity["decision"]
        if decision == "REJECT":
            disposition = "REJECT"
        elif decision == "ESCALATE":
            disposition = "ESCALATE"
        else:
            disposition = "EVALUATE"

        event_type = "evaluate"
        event = WorkerEvent(
            event_id=f"opp:{opportunity['opportunity_id']}:{iteration_id}",
            event_type=event_type,
            iteration_id=iteration_id,
            contract_id=opportunity["opportunity_id"],
            source=str(opportunity["source"]["locator"]),
            observed_at=str(opportunity["source"].get("observed_at", "")),
            idempotency_key=f"opportunity:{opportunity['opportunity_id']}:{iteration_id}",
        )

        # Ingestion never claims targeting, approval, application, engagement, or execution.
        self.runtime.process(event, {"opportunity_contract_valid"})
        return IngestionResult(
            opportunity_id=opportunity["opportunity_id"],
            accepted=True,
            disposition=disposition,
            event=event,
        )
