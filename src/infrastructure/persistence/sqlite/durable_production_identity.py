from __future__ import annotations

from datetime import datetime

from src.domain.identity.production_sessions import (
    ProductionSessionRecord,
    ProductionSessionState,
)

from .production_identity import (
    SQLiteProductionSessionRepository as _SQLiteProductionSessionRepository,
    _iso,
    _session,
    _utc,
)


class SQLiteDurableProductionSessionRepository(
    _SQLiteProductionSessionRepository
):
    """Production-session repository with optimistic idle-window renewal."""

    def touch(
        self,
        *,
        session_id: str,
        expected_revision: int,
        seen_at: datetime,
        idle_expires_at: datetime,
    ) -> ProductionSessionRecord:
        current = _utc(seen_at)
        requested_idle_expiry = _utc(idle_expires_at)
        with self.factory.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM production_identity_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Production session not found")
            existing = _session(row)
            if existing.revision != expected_revision:
                raise RuntimeError("Production session revision conflict")
            if existing.state is not ProductionSessionState.ACTIVE:
                raise RuntimeError("Only an active production session may be touched")
            if current < existing.last_seen_at:
                raise RuntimeError("Production session last-seen time cannot move backward")
            if requested_idle_expiry <= current:
                raise RuntimeError("Production session idle expiry must remain future-bound")
            if requested_idle_expiry > existing.absolute_expires_at:
                raise RuntimeError(
                    "Production session idle expiry cannot exceed absolute expiry"
                )
            cursor = connection.execute(
                """
                UPDATE production_identity_sessions
                SET last_seen_at = ?, idle_expires_at = ?, revision = ?
                WHERE session_id = ? AND revision = ? AND state = 'ACTIVE'
                """,
                (
                    _iso(current),
                    _iso(requested_idle_expiry),
                    expected_revision + 1,
                    session_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Production session changed concurrently")
        stored = self.get(session_id)
        if stored is None:
            raise RuntimeError("Touched production session is missing")
        return stored
