from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


EntityType = Literal["primitive", "agent", "artifact", "domain_concept"]
ClaimBasis = Literal["axiom", "observation", "inference", "simulation", "hypothesis"]
VerificationState = Literal[
    "verified",
    "corroborated",
    "unverified",
    "falsified",
    "not_applicable",
]
TerminalState = Literal["accepted", "rejected", "blocked", "requires_human_review"]


class ContractModel(BaseModel):
    """Closed, frozen contract base for deterministic epistemic state."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        str_strip_whitespace=True,
    )


class Entity(ContractModel):
    """Atomic structural unit within an epistemic artifact."""

    id: str = Field(pattern=r"^ENT-[A-Z0-9][A-Z0-9_-]{5,63}$")
    name: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=4000)
    entity_type: EntityType


class Relation(ContractModel):
    """Directed, typed mapping R: E_i x E_j -> Y."""

    id: str = Field(pattern=r"^REL-[A-Z0-9][A-Z0-9_-]{5,63}$")
    source_id: str = Field(pattern=r"^ENT-[A-Z0-9][A-Z0-9_-]{5,63}$")
    target_id: str = Field(pattern=r"^ENT-[A-Z0-9][A-Z0-9_-]{5,63}$")
    relation_type: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    evidence_refs: tuple[str, ...] = ()


class Claim(ContractModel):
    """Multi-dimensional epistemic claim envelope with enforceable lineage."""

    id: str = Field(pattern=r"^CLM-[A-Z0-9][A-Z0-9_-]{5,63}$")
    statement: str = Field(min_length=1, max_length=12000)
    basis: ClaimBasis
    verification_state: VerificationState = "unverified"
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = ()
    derived_from: tuple[str, ...] = ()
    falsifier: str | None = Field(default=None, max_length=4000)
    falsification_evidence_refs: tuple[str, ...] = ()
    supersedes: str | None = Field(
        default=None,
        pattern=r"^CLM-[A-Z0-9][A-Z0-9_-]{5,63}$",
    )

    @model_validator(mode="after")
    def enforce_epistemic_invariants(self) -> "Claim":
        if self.verification_state in {"verified", "corroborated"} and not self.evidence_refs:
            raise ValueError(
                f"Claim {self.id}: {self.verification_state} claims require evidence_refs"
            )
        if self.basis == "hypothesis" and not self.falsifier:
            raise ValueError(f"Claim {self.id}: hypothesis claims require a falsifier")
        if self.basis == "inference" and not self.derived_from:
            raise ValueError(f"Claim {self.id}: inference claims require derived_from lineage")
        if self.verification_state == "falsified" and not self.falsification_evidence_refs:
            raise ValueError(
                f"Claim {self.id}: falsified claims require falsification_evidence_refs"
            )
        if self.id in self.derived_from:
            raise ValueError(f"Claim {self.id}: a claim cannot derive from itself")
        if self.supersedes == self.id:
            raise ValueError(f"Claim {self.id}: a claim cannot supersede itself")
        return self


class ArtifactState(ContractModel):
    """Immutable state transported across epistemic pipeline boundaries."""

    stage: str = Field(min_length=1, max_length=100)
    revision: int = Field(ge=1)
    entities: tuple[Entity, ...] = ()
    claims: tuple[Claim, ...] = ()
    relations: tuple[Relation, ...] = ()
    parent_state_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def enforce_referential_integrity(self) -> "ArtifactState":
        entity_ids = [entity.id for entity in self.entities]
        claim_ids = [claim.id for claim in self.claims]
        relation_ids = [relation.id for relation in self.relations]

        self._require_unique("entity", entity_ids)
        self._require_unique("claim", claim_ids)
        self._require_unique("relation", relation_ids)

        entity_id_set = set(entity_ids)
        claim_id_set = set(claim_ids)

        for relation in self.relations:
            if relation.source_id not in entity_id_set:
                raise ValueError(
                    f"Relation {relation.id}: source entity {relation.source_id} does not exist"
                )
            if relation.target_id not in entity_id_set:
                raise ValueError(
                    f"Relation {relation.id}: target entity {relation.target_id} does not exist"
                )

        graph: dict[str, set[str]] = {claim_id: set() for claim_id in claim_ids}
        for claim in self.claims:
            for dependency in claim.derived_from:
                if dependency not in claim_id_set:
                    raise ValueError(
                        f"Claim {claim.id}: derived claim {dependency} does not exist"
                    )
                graph[claim.id].add(dependency)
            if claim.supersedes is not None and claim.supersedes not in claim_id_set:
                raise ValueError(
                    f"Claim {claim.id}: superseded claim {claim.supersedes} does not exist"
                )

        self._require_acyclic_claim_graph(graph)
        return self

    @staticmethod
    def _require_unique(kind: str, values: list[str]) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for value in values:
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        if duplicates:
            raise ValueError(f"Duplicate {kind} IDs: {', '.join(sorted(duplicates))}")

    @staticmethod
    def _require_acyclic_claim_graph(graph: dict[str, set[str]]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError(f"Cyclic claim derivation detected at {node}")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for claim_id in graph:
            visit(claim_id)


class RunReceipt(ContractModel):
    """Final immutable provenance receipt for a completed governed run."""

    run_id: str = Field(min_length=1, max_length=200)
    parent_run_id: str | None = Field(default=None, max_length=200)
    configuration_version: str = Field(default="2.0.0", pattern=r"^2\.0\.0$")
    schema_id: str = "urn:aigc:schema:meta-epistemic-config:2.0.0"
    prompt_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    event_hashes: tuple[str, ...] = ()
    started_at: datetime
    completed_at: datetime
    terminal_state: TerminalState

    @model_validator(mode="after")
    def enforce_receipt_temporal_integrity(self) -> "RunReceipt":
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self
