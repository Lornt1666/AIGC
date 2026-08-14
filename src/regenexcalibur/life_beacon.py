from __future__ import annotations

from typing import Any


_AUTHORITY_SHAPED_KEYS = frozenset(
    {
        "permit_id",
        "authority",
        "authority_granted",
        "credential",
        "credentials",
        "secret",
        "token",
        "api_key",
        "execute",
        "deploy",
        "publish",
        "send",
        "spend",
    }
)


def validate_universe_gate_request(request: dict[str, Any]) -> None:
    unknown = sorted(set(request).difference({"seed", "requested_evolution_depth"}))
    if unknown:
        raise ValueError(f"unknown Universe Gate fields: {', '.join(unknown)}")
    seed = request.get("seed")
    if not isinstance(seed, dict):
        raise ValueError("seed must be an object")
    forbidden = sorted(set(seed).intersection(_AUTHORITY_SHAPED_KEYS))
    if forbidden:
        raise ValueError(f"authority-shaped seed fields are forbidden: {', '.join(forbidden)}")


def life_gate(*, requested_depth: int, recursion_limit: int) -> dict[str, object]:
    if requested_depth < 0:
        raise ValueError("requested_evolution_depth must be non-negative")
    allowed = requested_depth <= recursion_limit
    return {
        "status": "PASS" if allowed else "BLOCKED_PERMISSION",
        "requested_depth": requested_depth,
        "recursion_limit": recursion_limit,
        "requires_human_review": True,
        "self_modification_performed": False,
        "external_action_performed": False,
        "reason": (
            "bounded evolution proposal admitted for review"
            if allowed
            else "requested recursion exceeds the seed's fail-closed limit"
        ),
    }
