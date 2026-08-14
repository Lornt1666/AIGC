import pytest
from pydantic import ValidationError

from occupational.knowledge_ingestion import (
    ClassificationStatus,
    ConceptKind,
    CrosswalkEdge,
    CrosswalkRelation,
    EmergentOccupationCandidate,
    OccupationProfileV3,
    OccupationalKnowledgeRegistry,
    SourceAuthority,
    TitleResolver,
)


HASH_A = "a" * 64
HASH_B = "b" * 64


def test_stable_ids_are_source_version_kind_bound():
    a = OccupationalKnowledgeRegistry.stable_aigc_id(ConceptKind.OCCUPATION, SourceAuthority.ESCO, "1.2.1", "123")
    b = OccupationalKnowledgeRegistry.stable_aigc_id(ConceptKind.TITLE, SourceAuthority.ESCO, "1.2.1", "123")
    c = OccupationalKnowledgeRegistry.stable_aigc_id(ConceptKind.OCCUPATION, SourceAuthority.ESCO, "1.2.2", "123")
    assert a != b
    assert a != c


def test_same_source_version_cannot_be_silently_overwritten():
    registry = OccupationalKnowledgeRegistry()
    registry.import_concept(
        kind=ConceptKind.OCCUPATION,
        authority=SourceAuthority.ESCO,
        version="1.2.1",
        source_id="occ-1",
        preferred_label="Software developer",
        source_hash=HASH_A,
    )
    with pytest.raises(ValueError, match="new taxonomy version"):
        registry.import_concept(
            kind=ConceptKind.OCCUPATION,
            authority=SourceAuthority.ESCO,
            version="1.2.1",
            source_id="occ-1",
            preferred_label="Different meaning",
            source_hash=HASH_A,
        )


def test_title_and_occupation_are_distinct_concept_kinds():
    registry = OccupationalKnowledgeRegistry()
    occupation = registry.import_concept(
        kind=ConceptKind.OCCUPATION,
        authority=SourceAuthority.ONET,
        version="30.3",
        source_id="15-1252.00",
        preferred_label="Software Developers",
        source_hash=HASH_A,
    )
    title = registry.import_concept(
        kind=ConceptKind.TITLE,
        authority=SourceAuthority.ONET,
        version="30.3",
        source_id="title-1",
        preferred_label="Backend Developer",
        source_hash=HASH_B,
    )
    assert occupation.aigc_id != title.aigc_id
    assert occupation.kind == ConceptKind.OCCUPATION
    assert title.kind == ConceptKind.TITLE


def test_crosswalk_endpoints_must_exist_and_exact_match_requires_high_confidence():
    registry = OccupationalKnowledgeRegistry()
    left = registry.import_concept(
        kind=ConceptKind.OCCUPATION,
        authority=SourceAuthority.ESCO,
        version="1.2.1",
        source_id="esco-1",
        preferred_label="Developer",
        source_hash=HASH_A,
    )
    right = registry.import_concept(
        kind=ConceptKind.OCCUPATION,
        authority=SourceAuthority.NOC,
        version="2021.0",
        source_id="21232",
        preferred_label="Software developers and programmers",
        source_hash=HASH_B,
    )
    with pytest.raises(ValidationError):
        CrosswalkEdge(
            edge_id="cw-weak",
            from_aigc_id=left.aigc_id,
            to_aigc_id=right.aigc_id,
            relation=CrosswalkRelation.EXACT_MATCH,
            confidence=0.8,
            method="SEMANTIC",
        )
    edge = CrosswalkEdge(
        edge_id="cw-close",
        from_aigc_id=left.aigc_id,
        to_aigc_id=right.aigc_id,
        relation=CrosswalkRelation.CLOSE_MATCH,
        confidence=0.8,
        method="EXPERT_SEMANTIC",
        evidence_refs=("evidence-1",),
    )
    registry.add_crosswalk(edge)
    assert registry.crosswalks() == (edge,)


def test_promoted_emergent_occupation_requires_evidence():
    with pytest.raises(ValidationError):
        EmergentOccupationCandidate(
            candidate_id="em-1",
            observed_title="AI Agent Engineer",
            status=ClassificationStatus.AIGC_EXTENSION_ACCEPTED,
        )


def test_title_resolver_uses_task_and_skill_evidence_not_title_only():
    registry = OccupationalKnowledgeRegistry()
    title = registry.import_concept(
        kind=ConceptKind.TITLE,
        authority=SourceAuthority.ONET,
        version="30.3",
        source_id="title-ai",
        preferred_label="AI Platform Engineer",
        source_hash=HASH_A,
    )
    task = registry.import_concept(
        kind=ConceptKind.TASK,
        authority=SourceAuthority.ONET,
        version="30.3",
        source_id="task-api",
        preferred_label="Design software APIs and platform services",
        source_hash=HASH_A,
    )
    skill = registry.import_concept(
        kind=ConceptKind.SKILL,
        authority=SourceAuthority.ESCO,
        version="1.2.1",
        source_id="skill-python",
        preferred_label="Python programming",
        source_hash=HASH_B,
    )
    profile = OccupationProfileV3(
        occupation_id="occ-software",
        preferred_title="Software Engineer",
        title_ids=(title.aigc_id,),
        task_ids=(task.aigc_id,),
        skill_ids=(skill.aigc_id,),
    )
    lookup = {c.aigc_id: c for c in registry.concepts()}
    result = TitleResolver().resolve(
        title="AI Platform Engineer",
        occupations=(profile,),
        concept_lookup=lookup,
        job_description="Design platform services and software APIs",
        observed_skills=("Python programming",),
    )
    assert result
    assert result[0].occupation_id == "occ-software"
    assert result[0].task_score > 0
    assert result[0].skill_score > 0
