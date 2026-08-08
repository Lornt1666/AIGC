from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .domain import WorkOrder
from .governed_bundle import GovernedOrchestrationBundle
from .orchestration import canonical_sha256


@dataclass(frozen=True)
class OrchestrationAdmissionEnvelope:
    """Final planning-only admission record for one authorized WorkOrder."""

    work_order: WorkOrder
    governed_bundle: GovernedOrchestrationBundle

    def __post_init__(self) -> None:
        if not self.work_order.authorized:
            raise ValueError("admission envelope requires an authorized WorkOrder")
        bundle = self.governed_bundle
        if self.work_order.work_order_id != bundle.task_dag.work_order_id:
            raise ValueError("WorkOrder and governed bundle IDs differ")
        if self.work_order.work_order_id != bundle.swarm_plan.work_order_id:
            raise ValueError("WorkOrder and SwarmPlan IDs differ")
        if (
            self.work_order.engagement_id
            != bundle.effective_policy.employer_policy.engagement_id
        ):
            raise ValueError("WorkOrder and effective policy engagements differ")
        definitions = {
            item.definition_id: item
            for item in bundle.definitions_of_done
        }
        for task in bundle.task_dag.tasks:
            definition = definitions.get(task.definition_of_done_id)
            if definition is None:
                raise ValueError("task references missing DefinitionOfDone")
            if not definition.covers(self.work_order):
                raise ValueError(
                    "DefinitionOfDone does not cover every WorkOrder obligation"
                )

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "schema_version": "1.0.0",
            "work_order": work_order_record(self.work_order),
            "governed_bundle": self.governed_bundle.to_record(),
            "authority": {
                "execution_authorized": False,
                "external_action_authorized": False,
                "merge_authorized": False,
                "deployment_authorized": False,
                "live_model_call_authorized": False,
                "financial_action_authorized": False,
            },
        }
        record["record_sha256"] = canonical_sha256(record)
        return record

    @classmethod
    def from_record(
        cls,
        record: dict[str, Any],
    ) -> OrchestrationAdmissionEnvelope:
        source = dict(record)
        expected_digest = source.pop("record_sha256", None)
        if not isinstance(expected_digest, str):
            raise ValueError("admission envelope requires a record digest")
        if canonical_sha256(source) != expected_digest:
            raise ValueError("admission envelope record digest mismatch")
        if source.get("schema_version") != "1.0.0":
            raise ValueError("unsupported admission envelope schema version")
        expected_authority = {
            "execution_authorized": False,
            "external_action_authorized": False,
            "merge_authorized": False,
            "deployment_authorized": False,
            "live_model_call_authorized": False,
            "financial_action_authorized": False,
        }
        if source.get("authority") != expected_authority:
            raise ValueError("admission envelope grants prohibited authority")
        envelope = cls(
            work_order=work_order_from_record(source["work_order"]),
            governed_bundle=GovernedOrchestrationBundle.from_record(
                source["governed_bundle"]
            ),
        )
        if envelope.to_record() != record:
            raise ValueError("admission envelope round trip lost information")
        return envelope


def work_order_record(work_order: WorkOrder) -> dict[str, object]:
    return {
        "work_order_id": work_order.work_order_id,
        "engagement_id": work_order.engagement_id,
        "objective": work_order.objective,
        "requirement_ids": list(work_order.requirement_ids),
        "acceptance_criteria": list(work_order.acceptance_criteria),
        "authorized": work_order.authorized,
    }


def work_order_from_record(record: dict[str, Any]) -> WorkOrder:
    return WorkOrder(
        work_order_id=str(record["work_order_id"]),
        engagement_id=str(record["engagement_id"]),
        objective=str(record["objective"]),
        requirement_ids=tuple(record["requirement_ids"]),
        acceptance_criteria=tuple(record["acceptance_criteria"]),
        authorized=bool(record["authorized"]),
    )
