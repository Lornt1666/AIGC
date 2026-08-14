from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.autonomy_policy import assess_autonomy
from src.core.nexus.occupation_registry import load_occupation_packs
from src.core.nexus.research_procurement import build_deep_research_plan
from src.core.nexus.universal_integration import evaluate_registry, load_and_validate_registry
from src.domain.nexus.autonomy import ActionIntent
from src.domain.nexus.contracts import EffectClass
from src.domain.nexus.research import ResearchProcurementRequest
from src.operations.employer_sandbox import run_employer_sandbox as run_employer_sandbox_operation
from src.webapp.nexus_dashboard import build_nexus_dashboard_snapshot


DryRunGoal = Literal[
    "WORK_SEARCH",
    "APPLICATION_PREPARATION",
    "EMPLOYER_COMMUNICATION",
    "DAILY_WORK",
]
SandboxScenario = Literal[
    "NORMAL_TASK",
    "PROMPT_INJECTION",
    "EXTERNAL_ACTION_REQUEST",
    "REGULATED_SCOPE_REQUEST",
]

ROOT = Path(__file__).resolve().parents[3]


def get_aigc_status() -> dict[str, object]:
    """Return a concise, safe status projection without reading external systems."""

    snapshot = build_nexus_dashboard_snapshot()
    readiness = evaluate_registry(
        load_and_validate_registry(
            ROOT / "config" / "aigc_universal_integration_registry.v1.json",
            ROOT / "schemas" / "aigc_universal_integration_registry.schema.json",
        )
    )
    occupations = [
        {
            "pack_id": pack.pack_id,
            "name": pack.name,
            "version": pack.version,
            "status": pack.status,
            "capability_ids": [item.capability_id for item in pack.capabilities],
            "classification_mappings": [
                item.model_dump(mode="json") for item in pack.classification_mappings
            ],
            "autonomy_ceiling": pack.autonomy_ceiling,
            "recertification_days": pack.recertification_days,
            "grants_external_authority": False,
        }
        for pack in load_occupation_packs()
    ]
    return {
        "product": snapshot["product"],
        "system": snapshot["system"],
        "connectors": snapshot["connectors"],
        "occupation_packs": occupations,
        "readiness": readiness.to_dict(),
        "authority_granted": False,
        "external_action_performed": False,
    }


def assess_aigc_action(
    *,
    intent_id: str,
    effect_class: EffectClass,
    public_read_only: bool = False,
    internal_sandbox_only: bool = False,
    accesses_private_data: bool = False,
    credentials_required: bool = False,
    persistent_internal_mutation: bool = False,
    external_mutation: bool = False,
    communication: bool = False,
    financial_spend_cad: str = "0.00",
    legal_commitment: bool = False,
    security_sensitive: bool = False,
    production_change: bool = False,
    physical_effect: bool = False,
    destructive: bool = False,
    irreversible: bool = False,
    outcome_indeterminate: bool = False,
) -> dict[str, object]:
    """Classify consequence only; caller input can never grant execution authority."""

    try:
        spend = Decimal(financial_spend_cad)
    except InvalidOperation as exc:
        raise ValueError("financial_spend_cad must be a decimal string") from exc
    assessment = assess_autonomy(
        ActionIntent(
            intent_id=intent_id,
            effect_class=effect_class,
            public_read_only=public_read_only,
            internal_sandbox_only=internal_sandbox_only,
            accesses_private_data=accesses_private_data,
            credentials_required=credentials_required,
            persistent_internal_mutation=persistent_internal_mutation,
            external_mutation=external_mutation,
            communication=communication,
            financial_spend_cad=spend,
            authorized_spend_cad=Decimal("0.00"),
            legal_commitment=legal_commitment,
            security_sensitive=security_sensitive,
            production_change=production_change,
            physical_effect=physical_effect,
            destructive=destructive,
            irreversible=irreversible,
            outcome_indeterminate=outcome_indeterminate,
            existing_explicit_authority=False,
            permit_id=None,
        )
    )
    return assessment.model_dump(mode="json")


def run_aigc_dry_run(*, goal: DryRunGoal) -> dict[str, object]:
    """Simulate a governed workflow with no credentials, network, or mutations."""

    plans: dict[DryRunGoal, tuple[tuple[str, str], ...]] = {
        "WORK_SEARCH": (
            ("OBSERVE", "inspect supplied or certified discovery evidence"),
            ("DRAFT", "rank opportunities and explain match assumptions"),
            ("SIMULATE", "prepare a review queue"),
            ("EXECUTE", "blocked until a certified discovery connector exists"),
        ),
        "APPLICATION_PREPARATION": (
            ("OBSERVE", "validate candidate facts and opportunity provenance"),
            ("DRAFT", "prepare truthful application materials"),
            ("SIMULATE", "check required fields, recipient, and duplicate risk"),
            ("EXECUTE", "blocked until the exact application route is certified"),
        ),
        "EMPLOYER_COMMUNICATION": (
            ("OBSERVE", "inspect an explicitly supplied thread reference"),
            ("DRAFT", "prepare a recipient-bound response"),
            ("SIMULATE", "screen content and verify destination"),
            ("EXECUTE", "blocked; no send-capable connector is admitted"),
        ),
        "DAILY_WORK": (
            ("OBSERVE", "validate work order, employer scope, and occupation pack"),
            ("DRAFT", "prepare a local deliverable"),
            ("SIMULATE", "run occupation-specific evaluation gates"),
            ("EXECUTE", "blocked until employer acceptance and exact work authority exist"),
        ),
    }
    stages = [
        {
            "stage": stage,
            "description": description,
            "status": "BLOCKED_PERMISSION" if stage == "EXECUTE" else "SIMULATED",
        }
        for stage, description in plans[goal]
    ]
    receipt_seed = {"goal": goal, "stages": stages, "zero_egress": True}
    return {
        "goal": goal,
        "stages": stages,
        "receipt_id": "DRY-" + canonical_sha256(receipt_seed)[:24].upper(),
        "zero_egress": True,
        "authority_granted": False,
        "external_action_performed": False,
        "final_status": "BLOCKED_BEFORE_EXECUTE",
    }


def run_employer_sandbox(
    *,
    pack_id: str,
    capability_id: str,
    scenario: SandboxScenario = "NORMAL_TASK",
) -> dict[str, object]:
    """Compatibility wrapper for the canonical employer-sandbox operation."""

    return run_employer_sandbox_operation(
        mode="sandbox",
        pack_id=pack_id,
        capability_id=capability_id,
        scenario=scenario,
    )


def procure_deep_research_plan(
    *,
    request_id: str,
    question: str,
    intended_decision: str,
    jurisdictions: list[str] | None = None,
    maximum_sources: int = 20,
    maximum_spend_cad: str = "0.00",
) -> dict[str, object]:
    """Create a source- and decision-bound plan; never retrieve sources or call a provider."""

    request = ResearchProcurementRequest(
        request_id=request_id,
        question=question,
        intended_decision=intended_decision,
        jurisdictions=tuple(jurisdictions or ("GLOBAL",)),
        maximum_sources=maximum_sources,
        maximum_spend_cad=maximum_spend_cad,
    )
    return build_deep_research_plan(request)
