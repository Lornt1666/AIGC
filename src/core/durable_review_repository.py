"""Durable repository boundary for AIGC review packets and work-order governance.

This module centralizes logical keys and version-bound JSON collection operations.
It deliberately does not replace the webapp's production fail-closed guard: approval
mutations and phase-evidence writers must be migrated before production can be enabled.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from src.core.artifact_store_factory import artifact_store_from_env
from src.core.durable_json_artifacts import (
    JsonCollectionSnapshot,
    load_json_collection,
    save_json_collection,
)
from src.core.production_artifact_store import ArtifactRef, S3PostgresArtifactStore


AUTHORIZATION_PACKETS_KEY = "aigc/review/authorization-packets"
WORK_ORDER_GOVERNANCE_KEY = "aigc/review/work-order-governance"
COLLECTION_SCHEMA_VERSION = "1"
COLLECTION_PROVENANCE = "aigc-durable-review-repository"


@dataclass(frozen=True)
class ReviewCollectionsSnapshot:
    """Consistent-by-reference snapshots loaded from the authoritative store.

    The two collections are separate artifacts, not a cross-key database snapshot.
    Callers must not assume atomic consistency between them.
    """

    authorization_packets: JsonCollectionSnapshot
    work_order_governance: JsonCollectionSnapshot


class DurableReviewRepository:
    """Version-bound access to authoritative review and work-order collections."""

    def __init__(self, store: S3PostgresArtifactStore) -> None:
        self._store = store

    @classmethod
    def from_env(cls) -> "DurableReviewRepository":
        """Build the shared store using workload identity and verified TLS settings."""
        return cls(artifact_store_from_env())

    def load_authorization_packets(self) -> JsonCollectionSnapshot:
        return load_json_collection(self._store, AUTHORIZATION_PACKETS_KEY)

    def load_work_orders(self) -> JsonCollectionSnapshot:
        return load_json_collection(self._store, WORK_ORDER_GOVERNANCE_KEY)

    def load_review_collections(self) -> ReviewCollectionsSnapshot:
        """Load both collections; any missing or invalid authority fails closed."""
        return ReviewCollectionsSnapshot(
            authorization_packets=self.load_authorization_packets(),
            work_order_governance=self.load_work_orders(),
        )

    def save_authorization_packets(
        self,
        *,
        items: Iterable[dict[str, Any]],
        expected: ArtifactRef | None,
        operation_id: str,
    ) -> ArtifactRef:
        return save_json_collection(
            self._store,
            key=AUTHORIZATION_PACKETS_KEY,
            items=items,
            expected=expected,
            operation_id=operation_id,
            schema_version=COLLECTION_SCHEMA_VERSION,
            provenance=COLLECTION_PROVENANCE,
        )

    def save_work_orders(
        self,
        *,
        items: Iterable[dict[str, Any]],
        expected: ArtifactRef | None,
        operation_id: str,
    ) -> ArtifactRef:
        return save_json_collection(
            self._store,
            key=WORK_ORDER_GOVERNANCE_KEY,
            items=items,
            expected=expected,
            operation_id=operation_id,
            schema_version=COLLECTION_SCHEMA_VERSION,
            provenance=COLLECTION_PROVENANCE,
        )


def new_review_operation_id() -> str:
    """Create a stable-format operation ID; callers must persist and reuse it on retry."""
    return str(uuid.uuid4())
