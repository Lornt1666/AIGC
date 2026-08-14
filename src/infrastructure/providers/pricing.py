from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_UP


@dataclass(frozen=True)
class TokenPricing:
    """Explicit CAD-denominated token pricing supplied by deployment configuration.

    Prices are intentionally not hard-coded in provider adapters because provider prices
    are external facts that change independently of repository code. Live adapters fail
    closed when exact usage or an explicit pricing table is unavailable.
    """

    input_cad_per_million: Decimal
    output_cad_per_million: Decimal

    def __post_init__(self) -> None:
        if self.input_cad_per_million < 0 or self.output_cad_per_million < 0:
            raise ValueError("provider pricing cannot be negative")

    def cost_cad(self, *, input_tokens: int, output_tokens: int) -> Decimal:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("provider token counts cannot be negative")
        million = Decimal(1_000_000)
        value = (
            Decimal(input_tokens) * self.input_cad_per_million / million
            + Decimal(output_tokens) * self.output_cad_per_million / million
        )
        return value.quantize(Decimal("0.000001"), rounding=ROUND_UP)
