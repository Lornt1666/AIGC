import asyncio
import unittest

from core.orchestrator import SagaCoordinator, canonical_json, sha256_text


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *args):
        return False


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.query = ""
        self.params = ()
        self.rowcount = -1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, query, params=()):
        self.query, self.params = query, params
        if "UPDATE aigc_dead_letters SET published_at" in query:
            self.rowcount = 1

    async def fetchone(self):
        if "FROM aigc_dead_letters WHERE disposition_id=%s" in self.query:
            return self.row
        raise AssertionError("unexpected fetchone query: " + self.query)


class _Connection:
    def __init__(self, row):
        self.cursor_instance = _Cursor(row)

    def cursor(self):
        return self.cursor_instance

    def transaction(self):
        return _AsyncContext(None)


class _Pool:
    def __init__(self, row):
        self.connections = []
        self.row = row

    def connection(self):
        connection = _Connection(self.row)
        self.connections.append(connection)
        return _AsyncContext(connection)


class _Redis:
    def __init__(self):
        self.calls = []

    async def eval(self, *args):
        self.calls.append(args)
        return b"42-0"


class DeadLetterProjectionTests(unittest.TestCase):
    def test_projection_uses_atomic_redis_dedupe_and_persists_publish_receipt(self):
        disposition_id = "a" * 64
        row = {
            "source_stream": "aigc:events:v1",
            "source_stream_id": "17-0",
            "event_id": "event-17",
            "payload": '{"event_type":"poison"}',
            "payload_sha256": "b" * 64,
            "failure_type": "OrchestrationError",
            "delivery_count": 5,
        }
        coordinator = SagaCoordinator(database_url="postgresql://unused", redis_url="redis://localhost")
        coordinator.pool = _Pool(row)
        coordinator.redis = _Redis()
        coordinator.dead_letter_stream = "aigc:dead-letter:v1"

        async def run():
            await coordinator._publish_dead_letter(disposition_id)

        asyncio.run(run())
        self.assertEqual(len(coordinator.redis.calls), 1)
        call = coordinator.redis.calls[0]
        self.assertEqual(call[1], 2)
        self.assertEqual(call[2], "aigc:dlq-published:v1:" + sha256_text(canonical_json(["aigc:dead-letter:v1", disposition_id])))
        self.assertEqual(call[3], "aigc:dead-letter:v1")
        self.assertIn("XADD", call[0])
        self.assertIn("SET", call[0])
        self.assertEqual(call[-1], "5")
        update_cursor = coordinator.pool.connections[-1].cursor_instance
        self.assertIn("UPDATE aigc_dead_letters SET published_at", update_cursor.query)
        self.assertEqual(update_cursor.params, (disposition_id,))


if __name__ == "__main__":
    unittest.main()
