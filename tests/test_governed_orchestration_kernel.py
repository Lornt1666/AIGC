from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from src.core.arbiter import audit_source
from src.core.contracts import MutationPayload, TaskContract
from src.core.orchestrator import SagaAction, SagaExecutionError, RedisStreamsCoordinator
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
