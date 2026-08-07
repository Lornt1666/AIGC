from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.core.epistemic.config_loader import load_epistemic_config
from src.domain.epistemic.models import ArtifactState, Claim, Entity, Relation


CONFIG_PATH = Path("config/epistemic-genesis.v2.yaml")
SCHEMA_PATH = Path("schemas/epistemic/aigc-epistemic-config-v2.schema.json")


def _entity(entity_id: str = "ENT-ALPHA01") -> Entity:
    return Entity(
        id=entity_id,
        name="Alpha",
        description="Canonical test entity",
        entity_type="primitive",
    )


def _observation(claim_id: str = "CLM-OBSERV01") -> Claim:
    return Claim(
        id=claim_id,
        statement="Observed canonical fact",
        basis="observation",
        verification_state="verified",
        confidence=0.99,
        evidence_refs=("evidence:test:001",),
    )


def test_runtime_configuration_validates_fail_closed() -> None:
    config = load_epistemic_config(CONFIG_PATH, SCHEMA_PATH)
    assert config["version"] == "2.0.0"
    assert len(config["polyphonic_agents"]) == 4


def test_runtime_configuration_rejects_unknown_property(tmp_path: Path) -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    config["unexpected_runtime_escape_hatch"] = True
    candidate = tmp_path / "invalid.yaml"
    candidate.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Additional properties are not allowed"):
        load_epistemic_config(candidate, SCHEMA_PATH)


def test_contract_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Entity(
            id="ENT-ALPHA01",
            name="Alpha",
            description="Canonical test entity",
            entity_type="primitive",
            hallucinated_field="must fail",
        )


def test_frozen_contract_prevents_assignment() -> None:
    entity = _entity()
    with pytest.raises(ValidationError):
        entity.name = "Mutated"  # type: ignore[misc]


def test_verified_claim_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="require evidence_refs"):
        Claim(
            id="CLM-VERIFY01",
            statement="Unsupported verified claim",
            basis="observation",
            verification_state="verified",
            confidence=1.0,
        )


def test_hypothesis_requires_falsifier() -> None:
    with pytest.raises(ValidationError, match="require a falsifier"):
        Claim(
            id="CLM-HYPOTH01",
            statement="A falsifiable hypothesis without its falsifier",
            basis="hypothesis",
            confidence=0.5,
        )


def test_inference_requires_existing_lineage() -> None:
    with pytest.raises(ValidationError, match="derived_from lineage"):
        Claim(
            id="CLM-INFER001",
            statement="Inference without lineage",
            basis="inference",
            confidence=0.5,
        )


def test_artifact_rejects_dangling_relation() -> None:
    relation = Relation(
        id="REL-ALPHA01",
        source_id="ENT-ALPHA01",
        target_id="ENT-MISSING1",
        relation_type="depends_on",
        description="Dangling target must be rejected",
    )
    with pytest.raises(ValidationError, match="target entity ENT-MISSING1 does not exist"):
        ArtifactState(stage="architect", revision=1, entities=(_entity(),), relations=(relation,))


def test_artifact_rejects_missing_claim_dependency() -> None:
    claim = Claim(
        id="CLM-INFER001",
        statement="Inference with a missing parent",
        basis="inference",
        confidence=0.5,
        derived_from=("CLM-MISSING1",),
    )
    with pytest.raises(ValidationError, match="derived claim CLM-MISSING1 does not exist"):
        ArtifactState(stage="critic", revision=1, claims=(claim,))


def test_artifact_rejects_cyclic_claim_derivation() -> None:
    left = Claim(
        id="CLM-CYCLE001",
        statement="Left cycle node",
        basis="inference",
        confidence=0.4,
        derived_from=("CLM-CYCLE002",),
    )
    right = Claim(
        id="CLM-CYCLE002",
        statement="Right cycle node",
        basis="inference",
        confidence=0.4,
        derived_from=("CLM-CYCLE001",),
    )
    with pytest.raises(ValidationError, match="Cyclic claim derivation"):
        ArtifactState(stage="critic", revision=1, claims=(left, right))


def test_artifact_rejects_duplicate_ids() -> None:
    first = _entity("ENT-DUPLIC01")
    second = Entity(
        id="ENT-DUPLIC01",
        name="Second",
        description="Duplicate identifier",
        entity_type="artifact",
    )
    with pytest.raises(ValidationError, match="Duplicate entity IDs"):
        ArtifactState(stage="architect", revision=1, entities=(first, second))


def test_canonical_serialization_and_hash_are_deterministic() -> None:
    state = ArtifactState(
        stage="architect",
        revision=1,
        entities=(_entity(),),
        claims=(_observation(),),
    )
    reconstructed = ArtifactState.model_validate(deepcopy(state.model_dump(mode="python")))

    assert canonical_json_bytes(state) == canonical_json_bytes(reconstructed)
    assert canonical_sha256(state) == canonical_sha256(reconstructed)
    assert len(canonical_sha256(state)) == 64
