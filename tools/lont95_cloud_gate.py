#!/usr/bin/env python3
"""Read-only Lont95 Mines analysis gate.

No login, network calls, deposits, withdrawals, wagers, tile selection, autoplay,
or attempt to predict unrevealed game outcomes.
"""

# Cloud trigger revision: workflow already exists before this push.

import argparse
import json
import math

GRID_TILES = 25
DEFAULT_RTP = 0.99


def survival_probability(mines: int, reveals: int, tiles: int = GRID_TILES) -> float:
    if not 1 <= mines < tiles:
        raise ValueError(f"mines must be between 1 and {tiles - 1}")
    safe = tiles - mines
    if not 0 <= reveals <= safe:
        raise ValueError(f"reveals must be between 0 and {safe}")
    return math.comb(safe, reveals) / math.comb(tiles, reveals)


def analyze(mines: int, reveals: int, wager: float, rtp: float,
            verified_external_value: float, transaction_costs: float) -> dict:
    if wager < 0:
        raise ValueError("wager cannot be negative")
    if not 0 < rtp <= 1:
        raise ValueError("rtp must be > 0 and <= 1")
    if verified_external_value < 0 or transaction_costs < 0:
        raise ValueError("external value and costs cannot be negative")

    p = survival_probability(mines, reveals)
    fair_multiplier = 1.0 / p
    expected_house_cost = wager * (1.0 - rtp)
    net_ev = verified_external_value - expected_house_cost - transaction_costs

    if net_ev <= 0:
        decision = "SKIP"
        reason = "No independently verified positive expected value after modeled house cost and transaction costs."
    else:
        decision = "HUMAN_REVIEW"
        reason = "Modeled external value is positive, but no wagering action is authorized or performed."

    return {
        "mode": "READ_ONLY_DRY_RUN",
        "mines": mines,
        "reveals": reveals,
        "wager_model_only": wager,
        "rtp": rtp,
        "survival_probability": p,
        "fair_multiplier": fair_multiplier,
        "theoretical_rtp_multiplier": fair_multiplier * rtp,
        "expected_return_before_external_value": wager * rtp,
        "expected_house_cost": expected_house_cost,
        "verified_external_value": verified_external_value,
        "transaction_costs": transaction_costs,
        "net_expected_value": net_ev,
        "decision": decision,
        "reason": reason,
        "execution_boundary": "NO_BETTING_OR_STAKE_CONNECTIVITY"
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mines", type=int, default=1)
    p.add_argument("--reveals", type=int, default=1)
    p.add_argument("--wager", type=float, default=10.0)
    p.add_argument("--rtp", type=float, default=DEFAULT_RTP)
    p.add_argument("--external-value", type=float, default=0.0)
    p.add_argument("--costs", type=float, default=0.0)
    args = p.parse_args()
    print(json.dumps(analyze(
        args.mines, args.reveals, args.wager, args.rtp,
        args.external_value, args.costs
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
