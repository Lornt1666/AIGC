from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from src.mission_os.api import create_mission_app
from src.mission_os.projection import compose_projection


ROOT = Path(__file__).resolve().parents[1]


class MissionProjectionTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        path = root / "quests.sqlite3"
        connection = sqlite3.connect(path)
        connection.execute(
            """
            CREATE TABLE records(
                collection TEXT NOT NULL,
                record_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                revoked_at TEXT,
                retention_state TEXT NOT NULL
            )
            """
        )
        payload = {
            "quest_id": "quest_projection01",
            "title": "Projection fixture",
            "lifecycle_state": "PROPOSED",
            "external_action_performed": False,
        }
        connection.execute(
            "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "quests",
                payload["quest_id"],
                3,
                json.dumps(payload),
                "2026-08-02T00:00:00+00:00",
                "2026-08-02T01:00:00+00:00",
                None,
                "ACTIVE",
            ),
        )
        connection.commit()
        connection.close()
        return path

    def test_projection_reads_quest_and_registry_without_database_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            database = self._database(Path(temp))
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            snapshot = compose_projection(ROOT, database_path=database)
            after = hashlib.sha256(database.read_bytes()).hexdigest()

        self.assertEqual(before, after)
        self.assertEqual(snapshot["summary"]["quests_total"], 1)
        self.assertGreater(snapshot["summary"]["phases_registered"], 0)
        self.assertEqual(snapshot["validation"], {"mission": "VALID", "snapshot": "VALID"})
        self.assertFalse(snapshot["canonical_state_mutated"])
        self.assertFalse(snapshot["external_action_performed"])

    def test_missing_database_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "missing.sqlite3"
            snapshot = compose_projection(ROOT, database_path=database)
            self.assertFalse(database.exists())
        self.assertEqual(snapshot["summary"]["quests_total"], 0)

    def test_api_registers_get_only_projection_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            database = self._database(Path(temp))
            app = create_mission_app(ROOT, database_path=database)
            client = TestClient(app)
            response = client.get("/api/v1/mission/snapshot")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["mode"], "READ_ONLY")
            post = client.post("/api/v1/mission/snapshot")
            self.assertEqual(post.status_code, 405)
            methods = {
                method
                for route in app.routes
                if getattr(route, "path", "").startswith("/api/v1/mission")
                for method in (getattr(route, "methods", set()) or set())
            }
            self.assertEqual(methods, {"GET"})


if __name__ == "__main__":
    unittest.main()
