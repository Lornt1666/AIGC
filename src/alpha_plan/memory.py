from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.epistemic.canonicalization import canonical_sha256
from src.security.redactor import Redactor


def _utc_epoch() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _safe_json(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    if Redactor().redact_text(serialized) != serialized:
        raise ValueError("memory payload contains credential-like material")
    return serialized


class SQLiteAlphaMemory:
    """Local durable memory with explicit consent, retention, and audit bindings.

    This store is not invoked by the read-only MCP planner. A trusted local runtime
    may inject it after choosing an exact database path and retention policy.
    """

    def __init__(self, path: Path) -> None:
        if path == Path(":memory:"):
            self.path = path
        else:
            self.path = path.resolve()
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path))
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS alpha_facts (
                fact_key TEXT PRIMARY KEY,
                fact_id TEXT NOT NULL UNIQUE,
                value_json TEXT NOT NULL,
                value_sha256 TEXT NOT NULL,
                consent_artifact_ref TEXT NOT NULL,
                created_at_epoch INTEGER NOT NULL,
                expires_at_epoch INTEGER
            );
            CREATE TABLE IF NOT EXISTS alpha_episodes (
                episode_id TEXT PRIMARY KEY,
                episode_json TEXT NOT NULL,
                episode_sha256 TEXT NOT NULL,
                created_at_epoch INTEGER NOT NULL,
                expires_at_epoch INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_alpha_episode_expiry
                ON alpha_episodes(expires_at_epoch);
            """
        )

    def close(self) -> None:
        self._connection.close()

    def save_fact(
        self,
        key: str,
        value: Mapping[str, Any],
        *,
        consent_artifact_ref: str,
        ttl_seconds: int | None = None,
        authoritative_epoch: int | None = None,
    ) -> str:
        if not key or len(key) > 200:
            raise ValueError("fact key must contain 1 to 200 characters")
        if not consent_artifact_ref.startswith("consent://"):
            raise PermissionError("durable facts require a consent:// artifact reference")
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        now = _utc_epoch() if authoritative_epoch is None else authoritative_epoch
        value_json = _safe_json(value)
        value_sha256 = canonical_sha256(dict(value))
        fact_id = "ALPHA-FACT-" + canonical_sha256(
            {
                "key": key,
                "value_sha256": value_sha256,
                "consent_artifact_ref": consent_artifact_ref,
            }
        )[:24].upper()
        expiry = None if ttl_seconds is None else now + ttl_seconds
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO alpha_facts (
                    fact_key, fact_id, value_json, value_sha256,
                    consent_artifact_ref, created_at_epoch, expires_at_epoch
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fact_key) DO UPDATE SET
                    fact_id=excluded.fact_id,
                    value_json=excluded.value_json,
                    value_sha256=excluded.value_sha256,
                    consent_artifact_ref=excluded.consent_artifact_ref,
                    created_at_epoch=excluded.created_at_epoch,
                    expires_at_epoch=excluded.expires_at_epoch
                """,
                (
                    key,
                    fact_id,
                    value_json,
                    value_sha256,
                    consent_artifact_ref,
                    now,
                    expiry,
                ),
            )
        return fact_id

    def get_fact(
        self, key: str, *, authoritative_epoch: int | None = None
    ) -> dict[str, Any] | None:
        now = _utc_epoch() if authoritative_epoch is None else authoritative_epoch
        row = self._connection.execute(
            """
            SELECT fact_id, value_json, value_sha256, consent_artifact_ref,
                   created_at_epoch, expires_at_epoch
            FROM alpha_facts
            WHERE fact_key = ?
              AND (expires_at_epoch IS NULL OR expires_at_epoch > ?)
            """,
            (key, now),
        ).fetchone()
        if row is None:
            return None
        return {
            "fact_id": row["fact_id"],
            "key": key,
            "value": json.loads(row["value_json"]),
            "value_sha256": row["value_sha256"],
            "consent_artifact_ref": row["consent_artifact_ref"],
            "created_at_epoch": row["created_at_epoch"],
            "expires_at_epoch": row["expires_at_epoch"],
        }

    def query_facts(
        self,
        prefix: str = "",
        limit: int = 10,
        *,
        authoritative_epoch: int | None = None,
    ) -> list[dict[str, Any]]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        now = _utc_epoch() if authoritative_epoch is None else authoritative_epoch
        rows = self._connection.execute(
            """
            SELECT fact_key, fact_id, value_json, value_sha256,
                   consent_artifact_ref, created_at_epoch, expires_at_epoch
            FROM alpha_facts
            WHERE fact_key LIKE ?
              AND (expires_at_epoch IS NULL OR expires_at_epoch > ?)
            ORDER BY fact_key
            LIMIT ?
            """,
            (f"{prefix}%", now, limit),
        ).fetchall()
        return [
            {
                "fact_id": row["fact_id"],
                "key": row["fact_key"],
                "value": json.loads(row["value_json"]),
                "value_sha256": row["value_sha256"],
                "consent_artifact_ref": row["consent_artifact_ref"],
                "created_at_epoch": row["created_at_epoch"],
                "expires_at_epoch": row["expires_at_epoch"],
            }
            for row in rows
        ]

    def delete_fact(self, key: str, *, consent_artifact_ref: str) -> bool:
        if not consent_artifact_ref.startswith("consent://"):
            raise PermissionError("durable fact deletion requires consent evidence")
        with self._connection:
            removed = self._connection.execute(
                "DELETE FROM alpha_facts WHERE fact_key = ?", (key,)
            ).rowcount
        return removed == 1

    def append_episode(
        self,
        episode: Mapping[str, Any],
        *,
        retention_seconds: int,
        authoritative_epoch: int | None = None,
    ) -> str:
        if retention_seconds <= 0:
            raise ValueError("retention_seconds must be positive")
        now = _utc_epoch() if authoritative_epoch is None else authoritative_epoch
        episode_json = _safe_json(episode)
        episode_sha256 = canonical_sha256(dict(episode))
        episode_id = "ALPHA-EPISODE-" + episode_sha256[:24].upper()
        with self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO alpha_episodes (
                    episode_id, episode_json, episode_sha256,
                    created_at_epoch, expires_at_epoch
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    episode_json,
                    episode_sha256,
                    now,
                    now + retention_seconds,
                ),
            )
        return episode_id

    def sample_meta_batch(
        self, batch_size: int = 32, *, authoritative_epoch: int | None = None
    ) -> list[dict[str, Any]]:
        if batch_size < 1 or batch_size > 1024:
            raise ValueError("batch_size must be between 1 and 1024")
        now = _utc_epoch() if authoritative_epoch is None else authoritative_epoch
        rows = self._connection.execute(
            """
            SELECT episode_json FROM alpha_episodes
            WHERE expires_at_epoch > ?
            ORDER BY created_at_epoch DESC, episode_id DESC
            LIMIT ?
            """,
            (now, batch_size),
        ).fetchall()
        return [json.loads(row["episode_json"]) for row in rows]

    def purge_expired(self, *, authoritative_epoch: int | None = None) -> int:
        now = _utc_epoch() if authoritative_epoch is None else authoritative_epoch
        with self._connection:
            facts = self._connection.execute(
                "DELETE FROM alpha_facts WHERE expires_at_epoch IS NOT NULL AND expires_at_epoch <= ?",
                (now,),
            ).rowcount
            episodes = self._connection.execute(
                "DELETE FROM alpha_episodes WHERE expires_at_epoch <= ?", (now,)
            ).rowcount
        return facts + episodes
