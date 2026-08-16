from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from .contracts import (
    AutopoieticPolicy,
    CandidateTemplate,
    StrictContract,
)


class IndependenceMatrix(StrictContract):
    compute_targets: tuple[str, ...] = Field(min_length=1, max_length=32)
    model_protocols: tuple[str, ...] = Field(min_length=1, max_length=32)
    execution_formats: tuple[str, ...] = Field(min_length=1, max_length=32)
    storage_formats: tuple[str, ...] = Field(min_length=1, max_length=32)
    orchestration_targets: tuple[str, ...] = Field(min_length=1, max_length=32)
    required_proprietary_providers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def no_required_proprietary_provider(self) -> "IndependenceMatrix":
        if self.required_proprietary_providers:
            raise ValueError("sovereign profile cannot require proprietary providers")
        return self


class EcosystemPlane(StrictContract):
    plane_id: str = Field(pattern=r"^PLANE-[A-Z0-9-]{3,80}$")
    purpose: str = Field(min_length=8, max_length=1_000)
    authority_source: str = Field(min_length=3, max_length=240)
    durable_state: tuple[str, ...] = Field(default=(), max_length=32)


class AutopoieticEcosystemConfig(StrictContract):
    schema_version: str
    ecosystem_id: str = Field(pattern=r"^AIGC-ECO-[A-Z0-9-]{3,80}$")
    owner: str
    operating_mode: str
    invariants: tuple[str, ...] = Field(min_length=1, max_length=64)
    planes: tuple[EcosystemPlane, ...] = Field(min_length=8, max_length=24)
    independence: IndependenceMatrix
    policy: AutopoieticPolicy
    templates: tuple[CandidateTemplate, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique_registry_ids(self) -> "AutopoieticEcosystemConfig":
        plane_ids = [item.plane_id for item in self.planes]
        template_ids = [item.template_id for item in self.templates]
        if len(plane_ids) != len(set(plane_ids)):
            raise ValueError("plane IDs must be unique")
        if len(template_ids) != len(set(template_ids)):
            raise ValueError("template IDs must be unique")
        return self


def load_ecosystem_config(path: str | Path) -> AutopoieticEcosystemConfig:
    return AutopoieticEcosystemConfig.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def config_sha256(config: AutopoieticEcosystemConfig) -> str:
    from .contracts import canonical_sha256

    return canonical_sha256(config.model_dump(mode="json"))


def dump_config(config: AutopoieticEcosystemConfig) -> dict[str, Any]:
    return json.loads(config.model_dump_json())
