from __future__ import annotations

import importlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

webapp = importlib.import_module("src.webapp.app")


def test_concurrent_accept_requests_allow_only_one_pending_transition(monkeypatch):
    review = SimpleNamespace(action_id="action-1", decision="pending")
    start = Barrier(3)
    accepted_commands = []

    def find_review(_action_id):
        return review

    def require_pending(current_review):
        if current_review.decision != "pending":
            raise HTTPException(status_code=409, detail="Review is no longer pending.")

    def run_command(*_args, **_kwargs):
        accepted_commands.append("accept")
        review.decision = "accepted"
        return SimpleNamespace(ok=True)

    monkeypatch.setattr(webapp, "_find_review", find_review)
    monkeypatch.setattr(webapp, "_require_pending_review", require_pending)
    monkeypatch.setattr(webapp, "build_accept_command", lambda *_args, **_kwargs: ["fake-accept"])
    monkeypatch.setattr(webapp, "run_command", run_command)
    monkeypatch.setattr(webapp, "_command_payload", lambda result: {"ok": result.ok})

    def attempt_accept():
        start.wait()
        try:
            return webapp.accept_review("action-1", webapp.DecisionRequest(phrase="approved"))
        except HTTPException as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt_accept) for _ in range(2)]
        start.wait()
        results = [future.result(timeout=5) for future in futures]

    successes = [result for result in results if isinstance(result, dict) and result.get("ok")]
    conflicts = [result for result in results if isinstance(result, HTTPException) and result.status_code == 409]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert accepted_commands == ["accept"]
    assert review.decision == "accepted"
