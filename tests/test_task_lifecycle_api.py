from __future__ import annotations

import hashlib
import pytest
from fastapi.testclient import TestClient

from src.webapp import app as app_module


class FakeTaskStore:
    def __init__(self):
        self.records = {}
        self.keys = {}

    def submit_task(self, *, owner_id, idempotency_key, task):
        digest = hashlib.sha256(task.model_dump_json(exclude={"task_id", "created_at", "telemetry"}).encode()).hexdigest()
        key = (owner_id, idempotency_key)
        if key in self.keys:
            task_id = self.keys[key]
            prior = self.records[task_id]
            if prior["_digest"] != digest:
                from src.core.task_lifecycle_store import TaskIdempotencyConflict
                raise TaskIdempotencyConflict("conflicting replay")
            return {k: v for k, v in prior.items() if k != "_digest"} | {"replayed": True}
        record = {
            "task_id": task.task_id, "owner_id": owner_id, "status": "queued",
            "attempt": 0, "version": 1, "created_at": "now", "updated_at": "now",
            "result": None, "artifact_sha256": None, "evidence": None,
            "_digest": digest, "replayed": False,
        }
        self.records[task.task_id] = record
        self.keys[key] = task.task_id
        return {k: v for k, v in record.items() if k != "_digest"}

    def get_task(self, *, owner_id, task_id):
        record = self.records.get(task_id)
        if not record or record["owner_id"] != owner_id:
            return None
        return {k: v for k, v in record.items() if k != "_digest"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AIGC_COMMAND_CENTER_TOKEN", "test-secret")
    monkeypatch.setattr(app_module, "_TASK_LIFECYCLE_STORE", FakeTaskStore())
    return TestClient(app_module.app)


def test_task_api_requires_operator_auth(client):
    response = client.get("/api/tasks/AIGC-TASK-12345678")
    assert response.status_code == 401


def test_task_api_submits_and_reads_owner_scoped_task(client):
    headers = {"Authorization": "Bearer test-secret", "Idempotency-Key": "api-key-123456"}
    body = {
        "idempotency_key": "api-key-123456",
        "task_type": "test.echo",
        "payload": {"message": "hello"},
    }
    submitted = client.post("/api/tasks", headers=headers, json=body)
    assert submitted.status_code == 202
    task_id = submitted.json()["task_id"]
    assert "owner_id" not in submitted.json()
    fetched = client.get(f"/api/tasks/{task_id}", headers={"Authorization": "Bearer test-secret"})
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "queued"


def test_task_api_fails_closed_for_unregistered_task_type(client):
    headers = {"Authorization": "Bearer test-secret", "Idempotency-Key": "api-key-987654"}
    response = client.post(
        "/api/tasks",
        headers=headers,
        json={"idempotency_key": "api-key-987654", "task_type": "shell.exec", "payload": {}},
    )
    assert response.status_code == 422
