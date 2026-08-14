from __future__ import annotations

import csv
import hashlib
import io
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .knowledge_ingestion import ConceptKind, SourceAuthority


class RawSourcePackage(BaseModel):
    """Verified bytes supplied to an adapter. Network acquisition is deliberately external."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authority: SourceAuthority
    version: str = Field(min_length=1)
    source_uri: str
    payload: bytes
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str = "text/csv"

    @property
    def actual_sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def verify(self) -> None:
        if self.actual_sha256 != self.expected_sha256:
            raise ValueError("source package checksum mismatch")


class NormalizedSourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authority: SourceAuthority
    version: str
    source_id: str
    kind: ConceptKind
    preferred_label: str
    description: str | None = None
    alternate_labels: tuple[str, ...] = ()
    source_uri: str | None = None
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class OccupationalSourceAdapter(ABC):
    authority: SourceAuthority
    supported_kinds: frozenset[ConceptKind]

    def validate_package(self, package: RawSourcePackage) -> None:
        if package.authority != self.authority:
            raise ValueError(f"adapter {self.authority} cannot ingest {package.authority}")
        package.verify()

    @abstractmethod
    def normalize(self, package: RawSourcePackage) -> tuple[NormalizedSourceRecord, ...]:
        raise NotImplementedError

    @staticmethod
    def _decode_csv(package: RawSourcePackage) -> list[dict[str, str]]:
        text = package.payload.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))

    @staticmethod
    def _first(row: Mapping[str, str], *names: str) -> str:
        for name in names:
            value = row.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""


class IscoAdapter(OccupationalSourceAdapter):
    authority = SourceAuthority.ISCO
    supported_kinds = frozenset({ConceptKind.OCCUPATION})

    def normalize(self, package: RawSourcePackage) -> tuple[NormalizedSourceRecord, ...]:
        self.validate_package(package)
        records: list[NormalizedSourceRecord] = []
        for row in self._decode_csv(package):
            code = self._first(row, "code", "ISCO08Code", "ISCO 08 Code", "unit_group_code")
            label = self._first(row, "title", "label", "occupation", "Title EN")
            if not code or not label:
                continue
            records.append(NormalizedSourceRecord(
                authority=self.authority,
                version=package.version,
                source_id=code,
                kind=ConceptKind.OCCUPATION,
                preferred_label=label,
                description=self._first(row, "definition", "description") or None,
                source_uri=package.source_uri,
                source_hash=package.actual_sha256,
                metadata={"classification_level": self._first(row, "level", "classification_level") or "UNKNOWN"},
            ))
        return tuple(records)


class EscoAdapter(OccupationalSourceAdapter):
    authority = SourceAuthority.ESCO
    supported_kinds = frozenset({ConceptKind.OCCUPATION, ConceptKind.TITLE, ConceptKind.SKILL, ConceptKind.KNOWLEDGE})

    def normalize(self, package: RawSourcePackage) -> tuple[NormalizedSourceRecord, ...]:
        self.validate_package(package)
        records: list[NormalizedSourceRecord] = []
        for row in self._decode_csv(package):
            source_id = self._first(row, "conceptUri", "conceptURI", "uri", "id")
            label = self._first(row, "preferredLabel", "preferred_label", "title")
            type_raw = self._first(row, "conceptType", "type").lower()
            if not source_id or not label:
                continue
            if "skill" in type_raw:
                kind = ConceptKind.SKILL
            elif "knowledge" in type_raw:
                kind = ConceptKind.KNOWLEDGE
            elif "title" in type_raw:
                kind = ConceptKind.TITLE
            else:
                kind = ConceptKind.OCCUPATION
            alt = self._first(row, "altLabels", "alternativeLabels", "alternate_labels")
            records.append(NormalizedSourceRecord(
                authority=self.authority,
                version=package.version,
                source_id=source_id,
                kind=kind,
                preferred_label=label,
                description=self._first(row, "description") or None,
                alternate_labels=tuple(x.strip() for x in alt.split("|") if x.strip()),
                source_uri=source_id if source_id.startswith("http") else package.source_uri,
                source_hash=package.actual_sha256,
            ))
        return tuple(records)


class NocAdapter(OccupationalSourceAdapter):
    authority = SourceAuthority.NOC
    supported_kinds = frozenset({ConceptKind.OCCUPATION, ConceptKind.TITLE, ConceptKind.CREDENTIAL_REQUIREMENT})

    def normalize(self, package: RawSourcePackage) -> tuple[NormalizedSourceRecord, ...]:
        self.validate_package(package)
        records: list[NormalizedSourceRecord] = []
        for row in self._decode_csv(package):
            code = self._first(row, "NOC Code", "noc_code", "code")
            label = self._first(row, "Title", "title", "unit_group_title")
            if not code or not label:
                continue
            teer = self._first(row, "TEER", "teer")
            records.append(NormalizedSourceRecord(
                authority=self.authority,
                version=package.version,
                source_id=code,
                kind=ConceptKind.OCCUPATION,
                preferred_label=label,
                description=self._first(row, "Lead Statement", "description") or None,
                source_uri=package.source_uri,
                source_hash=package.actual_sha256,
                metadata={"teer": teer or "UNKNOWN"},
            ))
        return tuple(records)


class SocAdapter(OccupationalSourceAdapter):
    authority = SourceAuthority.SOC
    supported_kinds = frozenset({ConceptKind.OCCUPATION})

    def normalize(self, package: RawSourcePackage) -> tuple[NormalizedSourceRecord, ...]:
        self.validate_package(package)
        records: list[NormalizedSourceRecord] = []
        for row in self._decode_csv(package):
            code = self._first(row, "SOC Code", "soc_code", "code")
            label = self._first(row, "SOC Title", "title", "occupation")
            if not code or not label:
                continue
            records.append(NormalizedSourceRecord(
                authority=self.authority,
                version=package.version,
                source_id=code,
                kind=ConceptKind.OCCUPATION,
                preferred_label=label,
                source_uri=package.source_uri,
                source_hash=package.actual_sha256,
            ))
        return tuple(records)


class OnetAdapter(OccupationalSourceAdapter):
    authority = SourceAuthority.ONET
    supported_kinds = frozenset({
        ConceptKind.OCCUPATION, ConceptKind.TITLE, ConceptKind.TASK,
        ConceptKind.WORK_ACTIVITY, ConceptKind.WORK_CONTEXT, ConceptKind.SKILL,
        ConceptKind.KNOWLEDGE, ConceptKind.ABILITY, ConceptKind.WORK_STYLE,
        ConceptKind.TECHNOLOGY,
    })

    _KIND_MAP = {
        "occupation": ConceptKind.OCCUPATION,
        "title": ConceptKind.TITLE,
        "task": ConceptKind.TASK,
        "work_activity": ConceptKind.WORK_ACTIVITY,
        "work context": ConceptKind.WORK_CONTEXT,
        "work_context": ConceptKind.WORK_CONTEXT,
        "skill": ConceptKind.SKILL,
        "knowledge": ConceptKind.KNOWLEDGE,
        "ability": ConceptKind.ABILITY,
        "work_style": ConceptKind.WORK_STYLE,
        "technology": ConceptKind.TECHNOLOGY,
    }

    def normalize(self, package: RawSourcePackage) -> tuple[NormalizedSourceRecord, ...]:
        self.validate_package(package)
        records: list[NormalizedSourceRecord] = []
        for row in self._decode_csv(package):
            source_id = self._first(row, "O*NET-SOC Code", "onet_soc_code", "code", "id")
            label = self._first(row, "Title", "title", "Element Name", "label", "Task")
            raw_kind = self._first(row, "kind", "concept_kind", "table").lower()
            kind = self._KIND_MAP.get(raw_kind, ConceptKind.OCCUPATION)
            if not source_id or not label:
                continue
            records.append(NormalizedSourceRecord(
                authority=self.authority,
                version=package.version,
                source_id=source_id,
                kind=kind,
                preferred_label=label,
                description=self._first(row, "Description", "description") or None,
                source_uri=package.source_uri,
                source_hash=package.actual_sha256,
            ))
        return tuple(records)


ADAPTERS: dict[SourceAuthority, type[OccupationalSourceAdapter]] = {
    SourceAuthority.ISCO: IscoAdapter,
    SourceAuthority.ESCO: EscoAdapter,
    SourceAuthority.NOC: NocAdapter,
    SourceAuthority.SOC: SocAdapter,
    SourceAuthority.ONET: OnetAdapter,
}


def adapter_for(authority: SourceAuthority) -> OccupationalSourceAdapter:
    try:
        return ADAPTERS[authority]()
    except KeyError as exc:
        raise ValueError(f"no source adapter for {authority}") from exc
