"""Fail-closed Redis Streams worker for admitted AIGC tasks.

This worker validates contracts and records blockers. It intentionally dispatches no
agent because all registry agents are disabled/specification-only. It never imports
agent modules dynamically or executes model-generated code.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from pydantic import ValidationError

from core.contracts import TaskContract
from core.orchestrator import OrchestrationError, SagaCoordinator, canonical_json, sha256_text


def load_registry(path: str) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    agents = data.get("agents") if isinstance(data, dict) else None
    if not isinstance(agents, list):
        raise ValueError("agent_registry_invalid")
    registry: dict[str, dict[str, Any]] = {}
    for agent in agents:
        if not isinstance(agent, dict) or not isinstance(agent.get("id"), str):
            raise ValueError("agent_registry_entry_invalid")
        if agent["id"] in registry:
            raise ValueError("duplicate_agent_id")
        if agent.get("enabled") is not False:
            raise ValueError("reference_worker_refuses_enabled_registry_agent")
        registry[agent["id"]] = agent
    return registry


async def process_task_event(event: Mapping[str, Any], conn: AsyncConnection,
                             registry: Mapping[str, Mapping[str, Any]]) -> None:
    """Validate a task and persist a terminal blocker in the same transaction as dedupe."""
    if event.get("event_type") != "TASK_ACCEPTED":
        raise OrchestrationError("unsupported_task_event_type")
    contract_payload = event.get("contract")
    try:
        contract = TaskContract.model_validate(contract_payload)
    except (ValidationError, TypeError) as exc:
        raise OrchestrationError("task_contract_invalid") from exc
    if str(contract.task_id) != event.get("task_id"):
        raise OrchestrationError("task_id_contract_binding_mismatch")
    missing = sorted(agent_id for agent_id in contract.allowed_agent_ids if agent_id not in registry)
    disabled = sorted(agent_id for agent_id in contract.allowed_agent_ids
                      if agent_id in registry and registry[agent_id].get("enabled") is not True)
    no_handler = sorted(agent_id for agent_id in contract.allowed_agent_ids
                        if agent_id in registry and registry[agent_id].get("enabled") is True)
    blockers = []
    if missing:
        blockers.append("unknown_agent_ids:" + ",".join(missing))
    if disabled:
        blockers.append("agents_disabled_or_not_production_integrated:" + ",".join(disabled))
    if no_handler:
        blockers.append("runtime_handler_not_registered:" + ",".join(no_handler))
    if not blockers:
        blockers.append("no_registered_execution_adapter; fail_closed")
    reason = ";".join(blockers)
    task_id = str(contract.task_id)
    async with conn.cursor() as cur:
        await cur.execute("SELECT status FROM aigc_tasks WHERE task_id=%s FOR UPDATE", (task_id,))
        task_row = await cur.fetchone()
        if not task_row:
            raise OrchestrationError("accepted_task_missing_from_durable_ledger")
        if task_row["status"] != "ACCEPTED":
            return
        await cur.execute("SELECT COALESCE(MAX(sequence),0)+1 AS seq FROM aigc_events WHERE task_id=%s", (task_id,))
        sequence = int((await cur.fetchone())["seq"])
        event_id = uuid4()
        payload = {
            "event_id": str(event_id), "task_id": task_id, "sequence": sequence,
            "event_type": "TASK_BLOCKED", "reason": reason,
            "agent_ids": list(contract.allowed_agent_ids), "policy_version": contract.policy_version,
            "side_effects_performed": False, "production_authorization": False,
        }
        encoded = canonical_json(payload)
        await cur.execute(
            "INSERT INTO aigc_events(event_id,task_id,sequence,event_type,payload,payload_sha256) VALUES(%s,%s,%s,%s,%s::jsonb,%s)",
            (str(event_id), task_id, sequence, "TASK_BLOCKED", encoded, sha256_text(encoded)))
        await cur.execute("UPDATE aigc_tasks SET status='BLOCKED',updated_at=now() WHERE task_id=%s AND status='ACCEPTED'",
                          (task_id,))


async def run_worker() -> None:
    registry_path = os.environ.get("AIGC_REGISTRY_PATH", "config/regenexcalibur_aigc_agent_registry.json")
    registry = load_registry(registry_path)
    coordinator = SagaCoordinator(
        database_url=os.environ["DATABASE_URL"],
        redis_url=os.environ["REDIS_URL"],
        dry_run=True,
        max_hops=int(os.environ.get("AIGC_MAX_HOPS", "10")),
        max_concurrency=int(os.environ.get("AIGC_MAX_CONCURRENCY", "16")),
    )
    await coordinator.open()
    try:
        async def handler(event: Mapping[str, Any], conn: AsyncConnection) -> None:
            await process_task_event(event, conn, registry)
        while True:
            await coordinator.consume_once(handler, block_ms=1000)
    finally:
        await coordinator.close()


if __name__ == "__main__":
    asyncio.run(run_worker())
