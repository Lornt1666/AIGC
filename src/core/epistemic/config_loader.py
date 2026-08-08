from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


DEFAULT_CONFIG_PATH = Path("config/epistemic-genesis.v2.yaml")
DEFAULT_SCHEMA_PATH = Path("schemas/epistemic/aigc-epistemic-config-v2.schema.json")


def load_epistemic_config(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Load YAML and fail closed unless it satisfies the strict Draft 2020-12 schema."""
    config_file = Path(config_path)
    schema_file = Path(schema_path)

    with config_file.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    with schema_file.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)

    if not isinstance(config, dict):
        raise ValueError("Epistemic runtime configuration must be a mapping")

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(config), key=lambda error: list(error.absolute_path))
    if errors:
        rendered = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"{location}: {error.message}")
        raise ValueError("Invalid epistemic runtime configuration: " + "; ".join(rendered))

    weights = config["teleological_vector"]["information_utility_objective"]["semantic_fidelity"]["components"]
    weight_sum = sum(float(value) for value in weights.values())
    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError(f"Semantic fidelity weights must sum to 1.0; observed {weight_sum}")

    agents = config["polyphonic_agents"]
    agent_ids = [str(agent["id"]) for agent in agents]
    roles = [str(agent["role"]) for agent in agents]
    if len(agent_ids) != len(set(agent_ids)):
        raise ValueError("polyphonic_agents contains duplicate agent IDs")
    if set(roles) != {"Architect", "Critic", "Synthesizer", "Verifier"}:
        raise ValueError("polyphonic_agents must contain exactly Architect, Critic, Synthesizer, and Verifier")

    return config
