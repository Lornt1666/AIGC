from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


class GladiatorStrategyError(ValueError):
    pass


@dataclass(frozen=True)
class GladiatorStrategyContract:
    strategy_id: str
    opportunity_id: str
    gladiator_id: str
    objective: str
    plan: str
    resource_budget: float
    evidence_requirements: tuple[str, ...]
    termination_conditions: tuple[str, ...]
    self_challenge_questions: tuple[str, ...]


@dataclass(frozen=True)
class StrategyAssessment:
    strategy_id: str
    ready: bool
    blockers: tuple[str, ...]
    challenge_count: int


class GladiatorStrategyFactory:
    """Builds bounded strategy contracts; it does not execute the strategy."""

    def build(self, data: Mapping[str, object]) -> GladiatorStrategyContract:
        required = (
            "strategy_id",
            "opportunity_id",
            "gladiator_id",
            "objective",
            "plan",
            "resource_budget",
            "evidence_requirements",
            "termination_conditions",
            "self_challenge_questions",
        )
        missing = [key for key in required if key not in data]
        if missing:
            raise GladiatorStrategyError(f"Missing strategy fields: {', '.join(missing)}")

        budget = float(data["resource_budget"])
        if budget < 0:
            raise GladiatorStrategyError("resource_budget cannot be negative.")

        collections = {}
        for key in (
            "evidence_requirements",
            "termination_conditions",
            "self_challenge_questions",
        ):
            value = data[key]
            if not isinstance(value, (list, tuple)) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                raise GladiatorStrategyError(f"{key} must be a non-empty string collection.")
            collections[key] = tuple(value)

        strings = ("strategy_id", "opportunity_id", "gladiator_id", "objective", "plan")
        if any(not str(data[key]).strip() for key in strings):
            raise GladiatorStrategyError("Strategy identity, objective, and plan are required.")

        return GladiatorStrategyContract(
            strategy_id=str(data["strategy_id"]),
            opportunity_id=str(data["opportunity_id"]),
            gladiator_id=str(data["gladiator_id"]),
            objective=str(data["objective"]),
            plan=str(data["plan"]),
            resource_budget=budget,
            **collections,
        )

    def assess(self, contract: GladiatorStrategyContract) -> StrategyAssessment:
        blockers: list[str] = []

        if not contract.evidence_requirements:
            blockers.append("Evidence requirements are absent.")
        if not contract.termination_conditions:
            blockers.append("Termination conditions are absent.")
        if not contract.self_challenge_questions:
            blockers.append("Self-challenge questions are absent.")
        if contract.resource_budget <= 0:
            blockers.append("Resource budget must be positive before execution planning.")

        return StrategyAssessment(
            strategy_id=contract.strategy_id,
            ready=not blockers,
            blockers=tuple(blockers),
            challenge_count=len(contract.self_challenge_questions),
        )
