from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.core.epistemic.canonicalization import canonical_sha256


class ShadowMetaLearner:
    """Deterministic meta-policy proposer that can never apply its own update."""

    def __init__(self, fallback_config: Mapping[str, float]) -> None:
        self.fallback_config = dict(sorted(fallback_config.items()))

    def suggest_config(self, state: Mapping[str, Any]) -> dict[str, Any]:
        state_sha256 = canonical_sha256(dict(state))
        return {
            "mode": "STABLE_FALLBACK",
            "state_sha256": state_sha256,
            "config": self.fallback_config,
            "exploration_enabled": False,
            "applied": False,
        }

    def propose_update(
        self, episodes: Sequence[Mapping[str, Any]], *, maximum_delta: float = 0.01
    ) -> dict[str, Any]:
        if maximum_delta <= 0 or maximum_delta > 0.01:
            raise ValueError("maximum_delta must be greater than zero and no more than 0.01")
        rewards = [
            max(-1.0, min(1.0, float(item.get("reward", 0.0)))) for item in episodes
        ]
        average_reward = sum(rewards) / len(rewards) if rewards else 0.0
        delta = max(-maximum_delta, min(maximum_delta, average_reward * maximum_delta))
        candidate = {
            key: round(value + delta, 6) for key, value in self.fallback_config.items()
        }
        proposal = {
            "schema_version": "aigc.alpha-meta-policy-proposal.v1",
            "episode_count": len(episodes),
            "average_reward": round(average_reward, 6),
            "maximum_delta": maximum_delta,
            "fallback_config": self.fallback_config,
            "candidate_config": candidate,
            "shadow_evaluation_required": True,
            "human_review_required": True,
            "applied": False,
        }
        proposal["proposal_sha256"] = canonical_sha256(proposal)
        return proposal
