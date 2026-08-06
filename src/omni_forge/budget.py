from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetEnvelope:
    maximum_tokens: int
    maximum_cost_cad: float
    maximum_attempts: int = 3
    consumed_tokens: int = 0
    consumed_cost_cad: float = 0.0
    attempts: int = 0

    def verify(self) -> None:
        if self.maximum_tokens <= 0:
            raise ValueError("maximum_tokens must be positive")
        if not 0 <= self.maximum_cost_cad <= 200:
            raise ValueError("maximum_cost_cad must be between CAD 0 and CAD 200")
        if not 1 <= self.maximum_attempts <= 3:
            raise ValueError("maximum_attempts must be between one and three")
        if self.consumed_tokens < 0 or self.consumed_cost_cad < 0 or self.attempts < 0:
            raise ValueError("consumption values cannot be negative")
        if self.consumed_tokens > self.maximum_tokens:
            raise PermissionError("token budget exceeded")
        if self.consumed_cost_cad > self.maximum_cost_cad:
            raise PermissionError("cost budget exceeded")
        if self.attempts > self.maximum_attempts:
            raise PermissionError("repair attempt budget exceeded")

    def reserve(self, *, tokens: int, cost_cad: float) -> "BudgetEnvelope":
        if tokens <= 0 or cost_cad < 0:
            raise ValueError("reservation must be positive and non-negative")
        candidate = BudgetEnvelope(
            maximum_tokens=self.maximum_tokens,
            maximum_cost_cad=self.maximum_cost_cad,
            maximum_attempts=self.maximum_attempts,
            consumed_tokens=self.consumed_tokens + tokens,
            consumed_cost_cad=round(self.consumed_cost_cad + cost_cad, 8),
            attempts=self.attempts + 1,
        )
        candidate.verify()
        return candidate
