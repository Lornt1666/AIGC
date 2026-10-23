from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError

from src.core.arbiter import audit_source
from src.core.contracts import MutationPayload, TaskContract
from src.core.orchestrator import (
    IdempotencyConflict,
    SagaAction,
    SagaExecutionError,
    RedisStreamsCoordinator,
)
from src.core.contracts import SagaStepContract


def test_task_contract_rejects_timeout_above_runtime_ceiling() -> None:
    with pytest.raises(ValidationError):
        TaskContract(
            idempotency_key="idempotency-key-123",
            task_type="research",
            timeout_seconds=31,
        )


def test_external_mutation_requires_permit_and_human_approval_references() -> None:
    with pytest.raises(ValidationError):
        MutationPayload(
            idempotency_key="mutation-key-123",
            operation="message.send",
            resource="recipient-1",
            external_effect=True,
        )


def test_static_arbiter_rejects_shell_and_dynamic_execution_primitives() -> None:
    report = audit_source(
        "import subprocess\n"
        "def run(user_input):\n"
        "    return subprocess.run(user_input, shell=True)\n"
        "eval('1 + 1')\n"
    )

    assert report.accepted is False
    assert {finding.rule_id for finding in report.findings} >= {"AST010", "AST020", "AST021"}
    assert report.to_dict()["execution_performed"] is False
    assert report.to_dict()["sandbox_established"] is False


def test_static_arbiter_accepts_simple_pure_source() -> None:
    report = audit_source("def add(a: int, b: int) -> int:\n    return a + b\n")
    assert report.accepted is True
    assert report.findings == ()


def test_static_arbiter_fails_closed_on_invalid_syntax() -> None:
    report = audit_source("def broken(:\n    pass\n")
    assert report.accepted is False
    assert report.findings[0].rule_id == "AST002"


def test_saga_compensates_completed_steps_in_reverse_order() -> None:
    calls: list[str] = []

    async def first() -> str:
        calls.append("execute-1")
        return "ok"

    async def compensate_first() -> None:
        calls.append("compensate-1")

    async def second() -> str:
        calls.append("execute-2")
        raise RuntimeError("simulated failure")

    async def compensate_second() -> None:
        calls.append("compensate-2")

    actions = [
        SagaAction(
            SagaStepContract(
                step_id="step-1",
                action_name="create-record",
                compensation_name="delete-record",
                idempotency_key="saga-step-key-1",
            ),
            first,
            compensate_first,
        ),
        SagaAction(
            SagaStepContract(
                step_id="step-2",
                action_name="publish-event",
                compensation_name="retract-event",
                idempotency_key="saga-step-key-2",
            ),
            second,
            compensate_second,
        ),
    ]

    with pytest.raises(SagaExecutionError):
        asyncio.run(RedisStreamsCoordinator.run_saga(actions))

    assert calls == ["execute-1", "execute-2", "compensate-2", "compensate-1"]

class FakeRedis:
    def __init__(
        self,
        *,
        fail_result_publish: bool = False,
        fail_enqueue_publish: bool = False,
        eval_results: list[int] | None = None,
    ):
        self.fail_result_publish = fail_result_publish
        self.fail_enqueue_publish = fail_enqueue_publish
        self.eval_results = list(eval_results or [])
        self.eval_calls: list[tuple[str, int, tuple]] = []
        self.idempotency: dict[str, str] = {}
        self.entries: list[tuple[str, dict]] = []
        self.acks: list[tuple[str, str, str]] = []
        self.read_entries: list[tuple[str, dict]] = []
        self.group_created = False

    async def xgroup_create(self, **kwargs):
        self.group_created = True

    async def eval(self, script, numkeys, *args):
        self.eval_calls.append((script, numkeys, args))
        if self.eval_results:
            return self.eval_results.pop(0)
        key, task_id, digest = str(args[0]), str(args[2]), str(args[-1])
        existing = self.idempotency.get(key)
        if existing is not None:
            existing_digest, existing_task_id = existing.split("|", 1)
            return [0, existing_task_id] if existing_digest == digest else [-1, existing_task_id]
        if self.fail_enqueue_publish:
            self.fail_enqueue_publish = False
            # Model the Lua pcall/XADD failure path: its reservation is rolled back.
            raise OSError("simulated task stream outage")
        self.idempotency[key] = f"{digest}|{task_id}"
        return [1, task_id]

    async def xreadgroup(self, **kwargs):
        if not self.read_entries:
            return []
        entry = self.read_entries.pop(0)
        return [("aigc:tasks:v1", [entry])]

    async def xadd(self, stream, fields):
        if stream == "aigc:task-results:v1" and self.fail_result_publish:
            raise OSError("simulated result stream outage")
        self.entries.append((stream, fields))
        return b"2-0"

    async def xack(self, stream, group, message_id):
        self.acks.append((stream, group, str(message_id)))
        return 1


def test_enqueue_atomically_reserves_idempotency_key() -> None:
    redis = FakeRedis()
    coordinator = RedisStreamsCoordinator(redis)

    async def scenario():
        first_task = TaskContract(
            idempotency_key="stable-idempotency-key",
            task_type="research",
            payload={"query": "same request"},
        )
        retry_task = TaskContract(
            idempotency_key="stable-idempotency-key",
            task_type="research",
            payload={"query": "same request"},
        )
        first = await coordinator.enqueue_with_receipt(first_task)
        replay = await coordinator.enqueue_with_receipt(retry_task)
        return first, replay

    first, replay = asyncio.run(scenario())
    assert first.accepted is True
    assert replay.accepted is False
    assert first.task_id == replay.task_id
    assert redis.eval_calls[0][2][-1] == redis.eval_calls[1][2][-1]


def test_real_redis_enqueue_failure_releases_idempotency_reservation(monkeypatch) -> None:
    import os
    redis_url = os.environ.get("AIGC_REDIS_TEST_URL", "").strip()
    if not redis_url:
        pytest.skip("AIGC_REDIS_TEST_URL is not configured for real Redis integration testing")

    import redis.asyncio as redis_async
    from redis.exceptions import ResponseError

    async def scenario() -> None:
        client = redis_async.from_url(redis_url, decode_responses=True)
        suffix = __import__("uuid").uuid4().hex
        idem = f"aigc:idem:task:real-redis-retry-{suffix}"
        stream = f"aigc:test:tasks:{suffix}"
        coordinator = RedisStreamsCoordinator(client, stream=stream)
        task = TaskContract(
            idempotency_key=f"real-redis-retry-{suffix}",
            task_type="research",
            payload={"query": "verify reservation rollback"},
        )
        try:
            # A string at the stream key makes XADD fail with WRONGTYPE after SET.
            await client.set(stream, "wrong-type")
            with pytest.raises(ResponseError, match="WRONGTYPE"):
                await coordinator.enqueue(task)
            assert await client.get(idem) is None

            await client.delete(stream)
            first_receipt = await coordinator.enqueue_with_receipt(task)
            assert first_receipt.accepted is True
            assert first_receipt.task_id == task.task_id
            assert await client.get(idem) is not None
            replay_task = TaskContract(
                idempotency_key=task.idempotency_key,
                task_type=task.task_type,
                payload={"query": "verify reservation rollback"},
            )
            replay_receipt = await coordinator.enqueue_with_receipt(replay_task)
            assert replay_receipt.accepted is False
            assert replay_receipt.task_id == task.task_id
            entries = await client.xrange(stream, min="-", max="+")
            assert len(entries) == 1
            assert entries[0][1]["task_id"] == task.task_id
        finally:
            await client.delete(idem, stream)
            await client.aclose()

    asyncio.run(scenario())


def test_enqueue_publish_failure_does_not_poison_idempotency_key() -> None:
    redis = FakeRedis(fail_enqueue_publish=True)
    coordinator = RedisStreamsCoordinator(redis)
    task = TaskContract(
        idempotency_key="retry-after-publish-failure",
        task_type="research",
        payload={"query": "retry safely"},
    )

    async def scenario() -> bool:
        with pytest.raises(OSError, match="task stream outage"):
            await coordinator.enqueue(task)
        assert "aigc:idem:task:retry-after-publish-failure" not in redis.idempotency
        return await coordinator.enqueue(task)

    assert asyncio.run(scenario()) is True
    assert "redis.pcall('XADD'" in redis.eval_calls[0][0]
    assert "redis.call('DEL', KEYS[1])" in redis.eval_calls[0][0]


def test_enqueue_rejects_idempotency_key_reuse_with_changed_payload() -> None:
    redis = FakeRedis()
    coordinator = RedisStreamsCoordinator(redis)

    async def scenario() -> None:
        await coordinator.enqueue(TaskContract(
            idempotency_key="stable-idempotency-key",
            task_type="research",
            payload={"query": "original request"},
        ))
        with pytest.raises(IdempotencyConflict, match="different task payload"):
            await coordinator.enqueue(TaskContract(
                idempotency_key="stable-idempotency-key",
                task_type="research",
                payload={"query": "altered request"},
            ))

    asyncio.run(scenario())
    assert redis.eval_calls[0][2][-1] != redis.eval_calls[1][2][-1]


def test_result_stream_failure_leaves_task_pending_for_retry() -> None:
    redis = FakeRedis(fail_result_publish=True)
    task = TaskContract(
        idempotency_key="stable-idempotency-key",
        task_type="research",
    )
    redis.read_entries.append(("1-0", {"task_json": task.model_dump_json()}))
    coordinator = RedisStreamsCoordinator(redis)

    async def handler(_task: TaskContract) -> dict:
        return {"ok": True}

    with pytest.raises(OSError, match="result stream outage"):
        asyncio.run(coordinator.consume_once(consumer_name="worker-1", handler=handler))

    assert redis.acks == []
    assert not any(stream == "aigc:tasks:dead-letter:v1" for stream, _ in redis.entries)


def test_handler_failure_is_dead_lettered_before_acknowledgement() -> None:
    redis = FakeRedis()
    task = TaskContract(
        idempotency_key="stable-idempotency-key",
        task_type="research",
    )
    redis.read_entries.append(("1-0", {"task_json": task.model_dump_json()}))
    coordinator = RedisStreamsCoordinator(redis)

    async def handler(_task: TaskContract) -> dict:
        raise RuntimeError("poison payload")

    assert asyncio.run(coordinator.consume_once(consumer_name="worker-1", handler=handler)) is True
    assert redis.entries[0][0] == "aigc:tasks:dead-letter:v1"
    assert redis.acks == [("aigc:tasks:v1", "aigc-workers-v1", "1-0")]

def test_result_events_redact_secret_fields_and_values() -> None:
    redis = FakeRedis()
    task = TaskContract(
        idempotency_key="stable-idempotency-key",
        task_type="research",
    )
    redis.read_entries.append(("1-0", {"task_json": task.model_dump_json()}))
    coordinator = RedisStreamsCoordinator(redis)

    async def handler(_task: TaskContract) -> dict:
        return {
            "api_key": "sensitive-value",
            "message": "Authori" + "zation: Bearer sensitive-bearer",
            "summary": "safe result",
        }

    asyncio.run(coordinator.consume_once(consumer_name="worker-1", handler=handler))
    event_json = redis.entries[0][1]["event_json"]
    assert "sensitive-value" not in event_json
    assert "sensitive-bearer" not in event_json
    event = json.loads(event_json)
    assert event["data"]["result"]["api_key"] == "[REDACTED]"
    assert "[REDACTED]" in event["data"]["result"]["message"]


def test_dead_letter_does_not_duplicate_raw_task_payload() -> None:
    redis = FakeRedis()
    task = TaskContract(
        idempotency_key="stable-idempotency-key",
        task_type="research",
    )
    redis.read_entries.append(("1-0", {"task_json": task.model_dump_json()}))
    coordinator = RedisStreamsCoordinator(redis)

    async def handler(_task: TaskContract) -> dict:
        raise RuntimeError("failure")

    asyncio.run(coordinator.consume_once(consumer_name="worker-1", handler=handler))
    dead_letter = redis.entries[0][1]
    assert "task_json" not in dead_letter
    assert len(dead_letter["payload_sha256"]) == 64
