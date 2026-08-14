from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _canonical_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SourceAuthority(StrEnum):
    ISCO = "ISCO"
    ESCO = "ESCO"
    NOC = "NOC"
    SOC = "SOC"
    ONET = "ONET"
    AIGC = "AIGC"


class ConceptKind(StrEnum):
    OCCUPATION = "OCCUPATION"
    TITLE = "TITLE"
    SKILL = "SKILL"
    KNOWLEDGE = "KNOWLEDGE"
    WORK_ACTIVITY = "WORK_ACTIVITY"
    TASK = "TASK"
    WORK_CONTEXT = "WORK_CONTEXT"
    ABILITY = "ABILITY"
    WORK_STYLE = "WORK_STYLE"
    TECHNOLOGY = "TECHNOLOGY"
    CREDENTIAL_REQUIREMENT = "CREDENTIAL_REQUIREMENT"


class CrosswalkRelation(StrEnum):
    EXACT_MATCH = "EXACT_MATCH"
    CLOSE_MATCH = "CLOSE_MATCH"
    BROADER_THAN = "BROADER_THAN"
    NARROWER_THAN = "NARROWER_THAN"
    SPLIT_INTO = "SPLIT_INTO"
    MERGED_FROM = "MERGED_FROM"
    DEPRECATED_BY = "DEPRECATED_BY"
    UNMAPPED = "UNMAPPED"


class ClassificationStatus(StrEnum):
    OFFICIAL = "OFFICIAL"
    OBSERVED = "OBSERVED"
    PROVISIONAL = "PROVISIONAL"
    EVIDENCE_ACCUMULATING = "EVIDENCE_ACCUMULATING"
    MAPPED_TO_EXISTING = "MAPPED_TO_EXISTING"
    AIGC_EXTENSION_ACCEPTED = "AIGC_EXTENSION_ACCEPTED"
    REVIEWED = "REVIEWED"
    DEPRECATED = "DEPRECATED"


class SourceDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authority: SourceAuthority
    version: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_uri: str | None = None
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class OccupationalConcept(BaseModel):
    """Versioned source concept. Labels are mutable across versions; identity is not."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aigc_id: str
    kind: ConceptKind
    preferred_label: str
    description: str | None = None
    alternate_labels: tuple[str, ...] = ()
    source: SourceDescriptor
    status: ClassificationStatus = ClassificationStatus.OFFICIAL
    supersedes_aigc_id: str | None = None
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @property
    def digest(self) -> str:
        return _canonical_digest(self.model_dump(mode="json", exclude={"source": {"imported_at"}}))


class CrosswalkEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_id: str
    from_aigc_id: str
    to_aigc_id: str
    relation: CrosswalkRelation
    confidence: float = Field(ge=0.0, le=1.0)
    method: Literal["OFFICIAL", "EXPERT", "SEMANTIC", "EXPERT_SEMANTIC", "RULE_BASED"]
    evidence_refs: tuple[str, ...] = ()
    reviewed_at: datetime | None = None

    @model_validator(mode="after")
    def exact_match_requires_strong_evidence(self) -> "CrosswalkEdge":
        if self.relation == CrosswalkRelation.EXACT_MATCH and self.confidence < 0.95:
            raise ValueError("EXACT_MATCH requires confidence >= 0.95")
        return self


class OccupationProfileV3(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    occupation_id: str
    preferred_title: str
    description: str | None = None
    classification_ids: dict[str, str] = Field(default_factory=dict)
    title_ids: tuple[str, ...] = ()
    specialization_ids: tuple[str, ...] = ()
    role_ids: tuple[str, ...] = ()
    task_ids: tuple[str, ...] = ()
    work_activity_ids: tuple[str, ...] = ()
    work_context_ids: tuple[str, ...] = ()
    knowledge_ids: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()
    ability_ids: tuple[str, ...] = ()
    work_style_ids: tuple[str, ...] = ()
    technology_ids: tuple[str, ...] = ()
    credential_requirement_ids: tuple[str, ...] = ()
    jurisdiction_ids: tuple[str, ...] = ()
    includes_occupation_ids: tuple[str, ...] = ()
    excludes_occupation_ids: tuple[str, ...] = ()
    adjacent_occupation_ids: tuple[str, ...] = ()
    progresses_to_occupation_ids: tuple[str, ...] = ()
    mobility_to_occupation_ids: tuple[str, ...] = ()


class EmergentOccupationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    observed_title: str
    status: ClassificationStatus
    evidence_refs: tuple[str, ...] = ()
    candidate_existing_occupation_ids: tuple[str, ...] = ()
    reviewed_by: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_emergent_status(self) -> "EmergentOccupationCandidate":
        allowed = {
            ClassificationStatus.OBSERVED,
            ClassificationStatus.PROVISIONAL,
            ClassificationStatus.EVIDENCE_ACCUMULATING,
            ClassificationStatus.MAPPED_TO_EXISTING,
            ClassificationStatus.AIGC_EXTENSION_ACCEPTED,
            ClassificationStatus.REVIEWED,
        }
        if self.status not in allowed:
            raise ValueError("invalid emergent occupation state")
        if self.status in {
            ClassificationStatus.MAPPED_TO_EXISTING,
            ClassificationStatus.AIGC_EXTENSION_ACCEPTED,
            ClassificationStatus.REVIEWED,
        } and not self.evidence_refs:
            raise ValueError("promoted emergent occupation state requires evidence")
        return self


class TitleResolutionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    occupation_id: str
    score: float = Field(ge=0.0, le=1.0)
    title_score: float = Field(ge=0.0, le=1.0)
    task_score: float = Field(ge=0.0, le=1.0)
    skill_score: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = ()


class OccupationalKnowledgeRegistry:
    """Append-only, source-versioned in-memory registry used by ingestion adapters."""

    def __init__(self) -> None:
        self._concepts: dict[str, OccupationalConcept] = {}
        self._source_keys: dict[tuple[str, str, str, str], str] = {}
        self._crosswalks: dict[str, CrosswalkEdge] = {}

    @staticmethod
    def stable_aigc_id(kind: ConceptKind, source: SourceAuthority, version: str, source_id: str) -> str:
        material = f"{kind.value}|{source.value}|{version}|{source_id}".encode()
        return f"AIGC-{kind.value[:3]}-{hashlib.sha256(material).hexdigest()[:20]}"

    def import_concept(
        self,
        *,
        kind: ConceptKind,
        authority: SourceAuthority,
        version: str,
        source_id: str,
        preferred_label: str,
        source_hash: str,
        source_uri: str | None = None,
        description: str | None = None,
        alternate_labels: Iterable[str] = (),
        metadata: dict[str, str | int | float | bool] | None = None,
        status: ClassificationStatus = ClassificationStatus.OFFICIAL,
    ) -> OccupationalConcept:
        key = (authority.value, version, kind.value, source_id)
        aigc_id = self.stable_aigc_id(kind, authority, version, source_id)
        concept = OccupationalConcept(
            aigc_id=aigc_id,
            kind=kind,
            preferred_label=preferred_label.strip(),
            description=description,
            alternate_labels=tuple(dict.fromkeys(label.strip() for label in alternate_labels if label.strip())),
            source=SourceDescriptor(
                authority=authority,
                version=version,
                source_id=source_id,
                source_uri=source_uri,
                source_hash=source_hash,
            ),
            status=status,
            metadata=metadata or {},
        )
        existing_id = self._source_keys.get(key)
        if existing_id:
            existing = self._concepts[existing_id]
            if existing.digest != concept.digest:
                raise ValueError("source/version concept is immutable; import a new taxonomy version")
            return existing
        self._source_keys[key] = aigc_id
        self._concepts[aigc_id] = concept
        return concept

    def add_crosswalk(self, edge: CrosswalkEdge) -> None:
        if edge.from_aigc_id not in self._concepts or edge.to_aigc_id not in self._concepts:
            raise KeyError("crosswalk endpoints must already exist")
        existing = self._crosswalks.get(edge.edge_id)
        if existing and existing != edge:
            raise ValueError("crosswalk edge IDs are immutable")
        self._crosswalks[edge.edge_id] = edge

    def concept(self, aigc_id: str) -> OccupationalConcept:
        return self._concepts[aigc_id]

    def concepts(self, *, kind: ConceptKind | None = None) -> tuple[OccupationalConcept, ...]:
        values = tuple(self._concepts.values())
        return values if kind is None else tuple(c for c in values if c.kind == kind)

    def crosswalks(self) -> tuple[CrosswalkEdge, ...]:
        return tuple(self._crosswalks.values())


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(value.lower()))


def _overlap_score(query: str, corpus: Iterable[str]) -> float:
    q = _tokens(query)
    if not q:
        return 0.0
    best = 0.0
    for item in corpus:
        t = _tokens(item)
        if not t:
            continue
        best = max(best, len(q & t) / len(q | t))
    return best


class TitleResolver:
    """Evidence-aware resolver. Titles seed candidates; task/skill evidence can change ranking."""

    def resolve(
        self,
        *,
        title: str,
        occupations: Iterable[OccupationProfileV3],
        concept_lookup: dict[str, OccupationalConcept],
        job_description: str = "",
        observed_skills: Iterable[str] = (),
        limit: int = 5,
    ) -> tuple[TitleResolutionCandidate, ...]:
        skill_text = " ".join(observed_skills)
        candidates: list[TitleResolutionCandidate] = []
        for occupation in occupations:
            title_labels = [occupation.preferred_title]
            title_labels.extend(
                concept_lookup[tid].preferred_label
                for tid in occupation.title_ids
                if tid in concept_lookup
            )
            task_labels = [
                concept_lookup[tid].preferred_label
                for tid in occupation.task_ids
                if tid in concept_lookup
            ]
            skill_labels = [
                concept_lookup[sid].preferred_label
                for sid in occupation.skill_ids
                if sid in concept_lookup
            ]
            title_score = _overlap_score(title, title_labels)
            task_score = _overlap_score(job_description, task_labels) if job_description else 0.0
            skill_score = _overlap_score(skill_text, skill_labels) if skill_text else 0.0
            score = min(1.0, 0.5 * title_score + 0.3 * task_score + 0.2 * skill_score)
            if score > 0:
                candidates.append(
                    TitleResolutionCandidate(
                        occupation_id=occupation.occupation_id,
                        score=score,
                        title_score=title_score,
                        task_score=task_score,
                        skill_score=skill_score,
                    )
                )
        candidates.sort(key=lambda item: (-item.score, item.occupation_id))
        return tuple(candidates[:limit])
