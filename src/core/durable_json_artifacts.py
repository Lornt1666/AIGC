"""JSON collection helpers over the authoritative shared artifact store.

Runtime authorization packets and work-order collections must be stored as versioned
JSON artifacts in production. Callers must bind mutations to the exact version they read.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable

from src.core.production_artifact_store import (
    ArtifactIntegrityError,
    ArtifactNotFound,
    ArtifactRef,
    S3PostgresArtifactStore,
)


@dataclass(frozen=True)
class JsonCollectionSnapshot:
    key: str
    items: list[dict[str, Any]]
    ref: ArtifactRef


def load_json_collection(
    store: S3PostgresArtifactStore,
    key: str,
) -> JsonCollectionSnapshot:
    """Load the latest authoritative JSON list; missing or malformed data fails closed."""
    current = store.get_current(key)
    if current is None:
        raise ArtifactNotFound(f"authoritative JSON collection is missing: {key}")
    ref, content = current
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError("authoritative JSON collection is not valid UTF-8 JSON") from exc
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ArtifactIntegrityError("authoritative JSON collection must be a list of objects")
    return JsonCollectionSnapshot(key=key, items=payload, ref=ref)


def save_json_collection(
    store: S3PostgresArtifactStore,
    *,
    key: str,
    items: Iterable[dict[str, Any]],
    expected: ArtifactRef | None,
    operation_id: str,
    schema_version: str,
    provenance: str,
) -> ArtifactRef:
    """Commit a JSON list using expected-version CAS; never silently overwrite a newer snapshot."""
    if expected is not None and expected.key != key:
        raise ValueError("expected artifact reference belongs to a different logical key")
    materialized = list(items)
    if any(not isinstance(item, dict) for item in materialized):
        raise ValueError("JSON collection entries must be objects")
    content = json.dumps(
        materialized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return store.put(
        key=key,
        content=content,
        media_type="application/json",
        schema_version=schema_version,
        provenance=provenance,
        operation_id=operation_id,
        expected_current_version_id=expected.version_id if expected else None,
    )
