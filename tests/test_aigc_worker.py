import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from core.worker import load_registry


class WorkerRegistryTests(unittest.TestCase):
    def test_registry_loader_rejects_enabled_agents_in_reference_worker(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "registry.json"
            path.write_text(json.dumps({"agents": [{"id": "RX-155", "enabled": True}]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "refuses_enabled"):
                load_registry(str(path))

    def test_registry_loader_rejects_duplicate_ids(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "registry.json"
            path.write_text(json.dumps({"agents": [{"id": "RX-155", "enabled": False}, {"id": "RX-155", "enabled": False}]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate_agent_id"):
                load_registry(str(path))


if __name__ == "__main__":
    unittest.main()
