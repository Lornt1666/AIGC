from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .knowledge_ingestion import OccupationalConcept, OccupationalKnowledgeRegistry
from .source_adapters import NormalizedSourceRecord, OccupationalSourceAdapter, RawSourcePackage


class IngestionDiff(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    new_concepts: int = 0
    unchanged_concepts: int = 0
    conflicting_concepts: int = 0
    sample_new_ids: tuple[str, ...] = ()
    conflict_keys: tuple[str, ...] = ()


class IngestionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    authority: str
    version: str
    source_uri: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    normalized_record_count: int = Field(ge=0)
    imported_concept_count: int = Field(ge=0)
    mode: Literal["DRY_RUN", "COMMIT"]
    result: Literal["PASS", "BLOCKED", "FAIL"]
    diff: IngestionDiff
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: tuple[str, ...] = ()


class OccupationalRegistryStore(Protocol):
    """Persistence boundary. Implementations must preserve append-only taxonomy history."""

    def existing(self, authority: str, version: str, kind: str, source_id: str) -> OccupationalConcept | None: ...
    def persist(self, concepts: Iterable[OccupationalConcept], receipt: IngestionReceipt) -> None: ...


class InMemoryRegistryStore:
    def __init__(self) -> None:
        self._concepts: dict[tuple[str, str, str, str], OccupationalConcept] = {}
        self.receipts: list[IngestionReceipt] = []

    def existing(self, authority: str, version: str, kind: str, source_id: str) -> OccupationalConcept | None:
        return self._concepts.get((authority, version, kind, source_id))

    def persist(self, concepts: Iterable[OccupationalConcept], receipt: IngestionReceipt) -> None:
        for concept in concepts:
            key = (
                concept.source.authority.value,
                concept.source.version,
                concept.kind.value,
                concept.source.source_id,
            )
            current = self._concepts.get(key)
            if current is not None and current.digest != concept.digest:
                raise ValueError("persistent taxonomy history is append-only")
            self._concepts[key] = concept
        self.receipts.append(receipt)


class OccupationalIngestionPipeline:
    def __init__(self, store: OccupationalRegistryStore | None = None) -> None:
        self.store = store or InMemoryRegistryStore()

    def _materialize(self, records: Iterable[NormalizedSourceRecord]) -> tuple[OccupationalConcept, ...]:
        registry = OccupationalKnowledgeRegistry()
        concepts: list[OccupationalConcept] = []
        for record in records:
            concepts.append(registry.import_concept(
                kind=record.kind,
                authority=record.authority,
                version=record.version,
                source_id=record.source_id,
                preferred_label=record.preferred_label,
                source_hash=record.source_hash,
                source_uri=record.source_uri,
                description=record.description,
                alternate_labels=record.alternate_labels,
                metadata=record.metadata,
            ))
        return tuple(concepts)

    def dry_run(self, package: RawSourcePackage, adapter: OccupationalSourceAdapter, *, receipt_id: str) -> IngestionReceipt:
        records = adapter.normalize(package)
        concepts = self._materialize(records)
        new_ids: list[str] = []
        conflicts: list[str] = []
        unchanged = 0
        for concept in concepts:
            existing = self.store.existing(
                concept.source.authority.value,
                concept.source.version,
                concept.kind.value,
                concept.source.source_id,
            )
            if existing is None:
                new_ids.append(concept.aigc_id)
            elif existing.digest == concept.digest:
                unchanged += 1
            else:
                conflicts.append(f"{concept.source.authority}:{concept.source.version}:{concept.kind}:{concept.source.source_id}")
        diff = IngestionDiff(
            new_concepts=len(new_ids),
            unchanged_concepts=unchanged,
            conflicting_concepts=len(conflicts),
            sample_new_ids=tuple(new_ids[:20]),
            conflict_keys=tuple(conflicts[:20]),
        )
        return IngestionReceipt(
            receipt_id=receipt_id,
            authority=package.authority.value,
            version=package.version,
            source_uri=package.source_uri,
            source_sha256=package.actual_sha256,
            normalized_record_count=len(records),
            imported_concept_count=0,
            mode="DRY_RUN",
            result="BLOCKED" if conflicts else "PASS",
            diff=diff,
            notes=("no canonical registry mutation occurred",),
        )

    def commit(self, package: RawSourcePackage, adapter: OccupationalSourceAdapter, *, receipt_id: str) -> IngestionReceipt:
        dry = self.dry_run(package, adapter, receipt_id=f"{receipt_id}:dry-run")
        if dry.result != "PASS":
            return IngestionReceipt(
                receipt_id=receipt_id,
                authority=dry.authority,
                version=dry.version,
                source_uri=dry.source_uri,
                source_sha256=dry.source_sha256,
                normalized_record_count=dry.normalized_record_count,
                imported_concept_count=0,
                mode="COMMIT",
                result="BLOCKED",
                diff=dry.diff,
                notes=("commit denied because dry-run detected immutable-history conflicts",),
            )
        records = adapter.normalize(package)
        concepts = self._materialize(records)
        new_concepts = [
            concept for concept in concepts
            if self.store.existing(
                concept.source.authority.value,
                concept.source.version,
                concept.kind.value,
                concept.source.source_id,
            ) is None
        ]
        receipt = IngestionReceipt(
            receipt_id=receipt_id,
            authority=package.authority.value,
            version=package.version,
            source_uri=package.source_uri,
            source_sha256=package.actual_sha256,
            normalized_record_count=len(records),
            imported_concept_count=len(new_concepts),
            mode="COMMIT",
            result="PASS",
            diff=dry.diff,
            notes=("source package checksum verified", "append-only persistence enforced"),
        )
        self.store.persist(new_concepts, receipt)
        return receipt
