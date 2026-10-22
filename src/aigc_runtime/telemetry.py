"""Privacy-conscious structured runtime telemetry and local metric aggregation."""
from __future__ import annotations

from collections import Counter
from threading import Lock
from typing import Any

from .governed_runtime import sha256_digest


class RuntimeTelemetry:
    def __init__(self, ledger):
        self.ledger = ledger
        self._lock = Lock()
        self._counts = Counter()
        self._latency_ms = []

    def record(self, *, task_id: str, agent_id: str, tool_name: str, started_at: str,
               duration_ms: float, status: str, denial_reason: str | None = None) -> dict[str, Any]:
        if duration_ms < 0:
            raise ValueError("duration_must_be_nonnegative")
        span = {
            "trace_id": sha256_digest({"task_id": task_id, "agent_id": agent_id, "tool_name": tool_name, "started_at": started_at})[7:],
            "task_id": task_id, "agent_id": agent_id, "tool_name": tool_name,
            "started_at": started_at, "duration_ms": duration_ms, "status": status,
            "denial_reason": denial_reason,
        }
        event_id = self.ledger.append("runtime_span", span, started_at)
        with self._lock:
            self._counts[("status", status)] += 1
            if denial_reason:
                self._counts[("denial", denial_reason)] += 1
            self._latency_ms.append(duration_ms)
        return {"trace_id": span["trace_id"], "event_id": event_id}

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            latency = sorted(self._latency_ms)
            count = len(latency)
            percentile = lambda p: latency[min(count - 1, int((count - 1) * p))] if count else None
            return {
                "invocation_count": count,
                "status_counts": {key[1]: value for key, value in self._counts.items() if key[0] == "status"},
                "policy_denial_counts": {key[1]: value for key, value in self._counts.items() if key[0] == "denial"},
                "latency_ms": {"p50": percentile(0.50), "p95": percentile(0.95), "p99": percentile(0.99)},
                "metrics_digest": sha256_digest({"latency": latency, "counts": sorted((str(k), v) for k, v in self._counts.items())}),
            }
