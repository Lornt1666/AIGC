from datetime import datetime, timezone
import time
from .governed_runtime import GovernanceError, sha256_digest


class GovernedToolAdapter:
    """Reference adapter; callers must pass an explicitly approved callable."""
    def __init__(self, broker, store, telemetry=None):
        self.broker, self.store, self.telemetry = broker, store, telemetry

    def invoke(self, contract, permit, tool_name, action, resource, policy_version, idempotency_key, handler):
        request_digest = sha256_digest({
            "task_id": contract.task_id, "agent_id": contract.agent_id,
            "tool_name": tool_name, "action": action,
            "resource_digest": sha256_digest(resource), "policy_version": policy_version,
        })
        state = self.store.begin_invocation(idempotency_key, request_digest)
        if not state["created"]:
            if state["status"] == "SUCCEEDED":
                return {"status": "SUCCEEDED", "result": state["result"], "replayed": True}
            raise GovernanceError("invocation_outcome_unknown_requires_reconciliation")
        start = time.monotonic()
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        decision = self.broker.authorize(
            contract=contract, permit=permit, tool_name=tool_name, action=action,
            resource=resource, policy_version=policy_version, now=datetime.now(timezone.utc),
        )
        if not decision["allowed"]:
            result = {"status": "BLOCKED", "reason": decision["reason"], "audit_event_id": decision["audit_event_id"]}
            self.store.finish_invocation(idempotency_key, "FAILED", result)
            self._observe(contract, tool_name, timestamp, start, "BLOCKED", decision["reason"])
            return result
        try:
            output = handler()
            digest = sha256_digest(output)
            result = {"status": "SUCCEEDED", "output": output, "output_digest": digest,
                      "audit_event_id": decision["audit_event_id"]}
            self.store.finish_invocation(idempotency_key, "SUCCEEDED", result)
            self._observe(contract, tool_name, timestamp, start, "SUCCEEDED", None)
            return result
        except Exception as exc:
            result = {"status": "UNKNOWN", "error_type": type(exc).__name__,
                      "reconciliation_required": True, "audit_event_id": decision["audit_event_id"]}
            self.store.finish_invocation(idempotency_key, "UNKNOWN", result)
            self._observe(contract, tool_name, timestamp, start, "UNKNOWN", type(exc).__name__)
            return result

    def _observe(self, contract, tool_name, timestamp, start, status, reason):
        if self.telemetry:
            self.telemetry.record(task_id=contract.task_id, agent_id=contract.agent_id,
                tool_name=tool_name, started_at=timestamp,
                duration_ms=round((time.monotonic() - start) * 1000, 3),
                status=status, denial_reason=reason)
