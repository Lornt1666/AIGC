from __future__ import annotations

import math
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable


TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)


class RetrievalPolicyError(ValueError):
    """Raised when unapproved material is offered to the local retriever."""


@dataclass(frozen=True)
class RetrievalDocument:
    document_id: str
    title: str
    text: str
    source_reference: str
    rights_reviewed: bool


@dataclass(frozen=True)
class RetrievalMatch:
    document_id: str
    title: str
    source_reference: str
    score: float


class LocalGrantRetriever:
    """Deterministic local retrieval for approved, rights-reviewed text only."""

    def __init__(self, dimension: int = 256) -> None:
        if dimension < 16:
            raise ValueError("Local retrieval dimension must be at least 16.")
        self._dimension = dimension
        self._documents: dict[str, RetrievalDocument] = {}
        self._vectors: dict[str, list[float]] = {}

    def add(self, document: RetrievalDocument) -> None:
        if not document.rights_reviewed:
            raise RetrievalPolicyError(
                "Historical grant material requires a rights review before indexing."
            )
        if not document.source_reference.strip() or not document.text.strip():
            raise RetrievalPolicyError(
                "Indexed material requires source metadata and non-empty text."
            )
        self._documents[document.document_id] = document
        self._vectors[document.document_id] = self._vectorize(document.text)

    def search(self, query: str, limit: int = 3) -> list[RetrievalMatch]:
        if limit < 1:
            return []
        query_vector = self._vectorize(query)
        matches = [
            RetrievalMatch(
                document_id=document.document_id,
                title=document.title,
                source_reference=document.source_reference,
                score=round(self._cosine(query_vector, self._vectors[key]), 4),
            )
            for key, document in self._documents.items()
        ]
        return sorted(
            (match for match in matches if match.score > 0),
            key=lambda match: (-match.score, match.document_id),
        )[:limit]

    def documents(self) -> Iterable[RetrievalDocument]:
        return tuple(self._documents.values())

    def _vectorize(self, text: str) -> list[float]:
        values = [0.0] * self._dimension
        for token in TOKEN_PATTERN.findall(text.lower()):
            index = int(sha256(token.encode("utf-8")).hexdigest(), 16) % self._dimension
            values[index] += 1.0
        magnitude = math.sqrt(sum(value * value for value in values))
        if magnitude:
            return [value / magnitude for value in values]
        return values

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))
