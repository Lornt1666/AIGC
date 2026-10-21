"""ARCHON-GENESIS reference runtime control plane.
In-memory reference only; not production scheduler. Production requires durable queue,
external identity, persistent audit, and OS/container isolation. No release authority.
"""
from __future__ import annotations
import asyncio, hashlib, json, time, uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

CONTRACT_VERSION = "aigc-agent-task/1.0"
RELEASE_AUTHORITY = "Release Assurance Agent"
FORBIDDEN_CAPABILITIES = frozenset({"admin","grant_privileges","merge","deploy","release","approve_self","override_policy","financial_commit","secrets_write"})
FORBIDDEN_TOOLS = frozenset({"admin","grant_privileges","merge","deploy","release","approve_self","override_policy","financial_commit","secrets_write"})
class RuntimeBlocked(RuntimeError): pass

@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    service_principal: str
    allowed_tools: frozenset[str]
    capabilities: frozenset[str] = frozenset({"read","draft"})
    max_cost_units: int = 10
    max_attempts: int = 2
    timeout_seconds: float = 10.0
    def validate(self):
        if not self.agent_id or not self.service_principal: raise RuntimeBlocked("identity_missing")
        if self.capabilities & FORBIDDEN_CAPABILITIES: raise RuntimeBlocked("forbidden_capability")
        if self.max_cost_units < 1 or not 1 <= self.max_attempts <= 3: raise RuntimeBlocked("invalid_budget_or_retry_policy")
        if not 0.05 <= self.timeout_seconds <= 120: raise RuntimeBlocked("invalid_timeout")

@dataclass(frozen=True)
class TaskContract:
    task_id: str
    schema_version: str
    agent_id: str
    requested_by: str
    tool: str
    payload: Mapping[str, Any]
    cost_units: int = 1
    timeout_seconds: float | None = None
    idempotency_key: str = ""

@dataclass
class Circuit:
    failures: int = 0
    opened_until: float = 0.0
    def permit(self): return time.monotonic() >= self.opened_until
    def record_failure(self):
        self.failures += 1
        if self.failures >= 3: self.opened_until = time.monotonic() + 30.0
    def record_success(self): self.failures, self.opened_until = 0, 0.0

Handler = Callable[[Mapping[str, Any], asyncio.Event], Awaitable[Mapping[str, Any]]]

class AuditLedger:
    """Process-local tamper-evident chain; production needs durable external anchoring."""
    def __init__(self): self.events, self._last_hash = [], "0" * 64
    def append(self, event_type, fields):
        event = {"sequence":len(self.events)+1,"timestamp_unix":int(time.time()),"event_type":event_type,"fields":dict(fields),"previous_hash":self._last_hash}
        raw = json.dumps(event,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
        event["event_hash"] = hashlib.sha256(raw).hexdigest()
        self._last_hash = event["event_hash"]; self.events.append(event); return event
    def verify(self):
        previous = "0"*64
        for n, stored in enumerate(self.events,1):
            event = dict(stored); digest = event.pop("event_hash",None)
            if event.get("sequence") != n or event.get("previous_hash") != previous: return False
            actual = hashlib.sha256(json.dumps(event,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
            if digest != actual: return False
            previous = digest
        return True

class AgentRuntime:
    def __init__(self):
        self.identities, self.handlers, self.circuits = {}, {}, {}
        self.ledger, self.cancel_events, self.spent, self.idempotency = AuditLedger(), {}, {}, {}
    def register(self, identity, handlers):
        identity.validate()
        if identity.agent_id in self.identities: raise RuntimeBlocked("duplicate_agent_identity")
        if identity.allowed_tools & FORBIDDEN_TOOLS: raise RuntimeBlocked("forbidden_tool_in_allowlist")
        if not handlers or set(handlers)-identity.allowed_tools: raise RuntimeBlocked("handler_outside_tool_allowlist")
        self.identities[identity.agent_id] = identity; self.circuits[identity.agent_id] = Circuit()
        for tool, handler in handlers.items(): self.handlers[(identity.agent_id,tool)] = handler
        self.ledger.append("agent_registered",{"agent_id":identity.agent_id,"service_principal":identity.service_principal,"allowed_tools":sorted(identity.allowed_tools),"capabilities":sorted(identity.capabilities)})
    async def dispatch(self, task):
        identity = self.identities.get(task.agent_id)
        if identity is None: return self._blocked(task,"unknown_agent")
        if task.schema_version != CONTRACT_VERSION: return self._blocked(task,"unsupported_contract_version")
        if task.tool not in identity.allowed_tools or (task.agent_id,task.tool) not in self.handlers: return self._blocked(task,"tool_not_allowed")
        if task.requested_by == identity.service_principal: return self._blocked(task,"self_approval_or_self_request_forbidden")
        if task.cost_units < 1 or task.cost_units > identity.max_cost_units: return self._blocked(task,"task_budget_exceeded")
        if task.idempotency_key and task.idempotency_key in self.idempotency: return dict(self.idempotency[task.idempotency_key])
        circuit = self.circuits[task.agent_id]
        if not circuit.permit(): return self._blocked(task,"circuit_open")
        if self.spent.get(task.agent_id,0)+task.cost_units > identity.max_cost_units: return self._blocked(task,"agent_budget_exhausted")
        timeout = min(task.timeout_seconds or identity.timeout_seconds,identity.timeout_seconds)
        if timeout <= 0: return self._blocked(task,"invalid_timeout")
        cancel = asyncio.Event(); self.cancel_events[task.task_id] = cancel
        self.spent[task.agent_id] = self.spent.get(task.agent_id,0)+task.cost_units
        self.ledger.append("task_accepted",{"task_id":task.task_id,"agent_id":task.agent_id,"tool":task.tool,"cost_units":task.cost_units,"contract_version":task.schema_version})
        handler = self.handlers[(task.agent_id,task.tool)]; last_error = "handler_failed"
        for attempt in range(1,identity.max_attempts+1):
            try:
                if cancel.is_set(): return self._blocked(task,"task_cancelled")
                result = await asyncio.wait_for(handler(dict(task.payload),cancel),timeout=timeout)
                if cancel.is_set(): return self._blocked(task,"task_cancelled")
                if not isinstance(result,Mapping): raise RuntimeBlocked("invalid_handler_result")
                safe = dict(result)
                for key in ("release_decision","approved","grant_privileges","deployment_authority"): safe.pop(key,None)
                circuit.record_success()
                response = {"status":"COMPLETED","task_id":task.task_id,"agent_id":task.agent_id,"contract_version":CONTRACT_VERSION,"attempts":attempt,"result":safe}
                self.ledger.append("task_completed",{"task_id":task.task_id,"agent_id":task.agent_id,"attempts":attempt})
                if task.idempotency_key: self.idempotency[task.idempotency_key] = response
                return response
            except asyncio.CancelledError:
                cancel.set(); self.ledger.append("task_cancelled",{"task_id":task.task_id,"agent_id":task.agent_id}); raise
            except Exception as exc:
                last_error = "timeout" if isinstance(exc,asyncio.TimeoutError) else type(exc).__name__
                self.ledger.append("task_attempt_failed",{"task_id":task.task_id,"agent_id":task.agent_id,"attempt":attempt,"error_class":last_error})
                if attempt < identity.max_attempts and not cancel.is_set(): await asyncio.sleep(0)
        circuit.record_failure()
        return self._blocked(task,"retries_exhausted:"+last_error)
    def cancel(self,task_id):
        event = self.cancel_events.get(task_id)
        if event is None:
            self.ledger.append("cancel_rejected",{"task_id":task_id,"reason":"task_not_active"}); return False
        event.set(); self.ledger.append("cancel_requested",{"task_id":task_id}); return True
    def health(self):
        valid = self.ledger.verify()
        return {"status":"ok" if valid else "unhealthy","contract_version":CONTRACT_VERSION,"registered_agents":len(self.identities),"audit_chain_valid":valid,"release_authority":RELEASE_AUTHORITY,"runtime_is_release_authority":False}
    def _blocked(self,task,reason):
        self.ledger.append("task_blocked",{"task_id":task.task_id,"agent_id":task.agent_id,"reason":reason})
        return {"status":"BLOCKED","task_id":task.task_id,"reason":reason,"release_decision":"BLOCK","production_authority":False}

def make_task(agent_id,requested_by,tool,payload,**kwargs):
    return TaskContract(task_id=kwargs.pop("task_id",str(uuid.uuid4())),schema_version=kwargs.pop("schema_version",CONTRACT_VERSION),agent_id=agent_id,requested_by=requested_by,tool=tool,payload=payload,**kwargs)
