from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Protocol

from src.core.epistemic.canonicalization import canonical_sha256
from src.domain.epistemic.tooling import (
    AgentToolPolicy,
    ToolDecisionReceipt,
    ToolInvocationRequest,
)


IdempotencyClaim = Literal["claimed", "duplicate", "conflict"]


class IdempotencyLedger(Protocol):
    """Atomic persistence boundary required by the broker.

    Production implementations must durably bind one idempotency key to exactly one
    canonical request digest. This interface intentionally has no in-memory default.
    """

    def claim(self, idempotency_key: str, request_digest: str) -> IdempotencyClaim: ...


@dataclass(frozen=True)
class RunBudgetSnapshot:
    requests_used: int = 0
    cost_units_used: int = 0


class EpistemicToolBroker:
    """Default-deny authorization boundary for epistemic tool intents.

    This PR does not dispatch tools. A policy permit means only that the intent may
    proceed to a later, separately governed execution gate.
    """

    _SENSITIVE_KEY_FRAGMENTS = (
        "password",
        "passwd",
        "token",
        "secret",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "private_key",
    )

    def __init__(
        self,
        policies: tuple[AgentToolPolicy, ...],
        *,
        ledger: IdempotencyLedger,
        emergency_stop: bool = False,
    ) -> None:
        policy_map = {policy.agent_id: policy for policy in policies}
        if len(policy_map) != len(policies):
            raise ValueError("Duplicate agent policies are not permitted")
        self._policies = policy_map
        self._ledger = ledger
        self._emergency_stop = bool(emergency_stop)

    @staticmethod
    def request_digest(request: ToolInvocationRequest) -> str:
        payload = request.model_dump(
            mode="json",
            exclude={"approval_reference", "idempotency_key"},
        )
        return canonical_sha256(payload)

    @staticmethod
    def parameters_hash(request: ToolInvocationRequest) -> str:
        return canonical_sha256(request.parameters)

    def evaluate(
        self,
        request: ToolInvocationRequest,
        *,
        budget: RunBudgetSnapshot = RunBudgetSnapshot(),
    ) -> ToolDecisionReceipt:
        digest = self.request_digest(request)
        parameters_hash = self.parameters_hash(request)
        reasons: list[str] = []

        if self._emergency_stop:
            reasons.append("EMERGENCY_STOP_ACTIVE")

        if request.idempotency_key != digest:
            reasons.append("INVALID_IDEMPOTENCY_KEY")

        policy = self._policies.get(request.agent_id)
        if policy is None:
            reasons.append("NO_AGENT_POLICY")
            return self._receipt(request, digest, parameters_hash, "DENIED", reasons)

        capability = next(
            (item for item in policy.capabilities if item.tool_name == request.tool_name),
            None,
        )
        if capability is None:
            reasons.append("TOOL_NOT_ALLOWED")
        elif request.scope not in capability.scopes:
            reasons.append("SCOPE_NOT_ALLOWED")

        if budget.requests_used >= policy.maximum_requests_per_run:
            reasons.append("REQUEST_BUDGET_EXHAUSTED")
        if budget.cost_units_used + request.estimated_cost_units > policy.maximum_cost_units_per_run:
            reasons.append("COST_BUDGET_EXCEEDED")

        if self._contains_raw_secret_material(request.parameters):
            reasons.append("RAW_SECRET_MATERIAL_FORBIDDEN")

        if reasons:
            return self._receipt(request, digest, parameters_hash, "DENIED", reasons)

        if request.scope in policy.human_approval_scopes:
            approval = request.approval_reference
            if approval is None:
                return self._receipt(
                    request,
                    digest,
                    parameters_hash,
                    "APPROVAL_REQUIRED",
                    ["HUMAN_APPROVAL_REQUIRED"],
                )
            approval_reasons: list[str] = []
            if approval.status != "active":
                approval_reasons.append("APPROVAL_NOT_ACTIVE")
            if approval.request_digest != digest:
                approval_reasons.append("APPROVAL_REQUEST_DIGEST_MISMATCH")
            if approval.exact_revision != request.exact_revision:
                approval_reasons.append("APPROVAL_REVISION_MISMATCH")
            if approval_reasons:
                return self._receipt(
                    request,
                    digest,
                    parameters_hash,
                    "DENIED",
                    approval_reasons,
                )

        claim = self._ledger.claim(request.idempotency_key, digest)
        if claim == "duplicate":
            return self._receipt(
                request,
                digest,
                parameters_hash,
                "DUPLICATE_INTENT",
                ["IDEMPOTENT_DUPLICATE"],
            )
        if claim == "conflict":
            return self._receipt(
                request,
                digest,
                parameters_hash,
                "IDEMPOTENCY_CONFLICT",
                ["IDEMPOTENCY_KEY_REUSED_FOR_DIFFERENT_REQUEST"],
            )

        return self._receipt(
            request,
            digest,
            parameters_hash,
            "POLICY_PERMIT_PENDING_EXECUTION_GATE",
            ["POLICY_AND_IDEMPOTENCY_CHECKS_PASSED"],
        )

    @classmethod
    def _contains_raw_secret_material(cls, value: object) -> bool:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                normalized = str(key).lower().replace("-", "_")
                if any(fragment in normalized for fragment in cls._SENSITIVE_KEY_FRAGMENTS):
                    return True
                if cls._contains_raw_secret_material(nested):
                    return True
            return False
        if isinstance(value, (list, tuple, set)):
            return any(cls._contains_raw_secret_material(item) for item in value)
        return False

    @staticmethod
    def _receipt(
        request: ToolInvocationRequest,
        digest: str,
        parameters_hash: str,
        decision: str,
        reasons: list[str],
    ) -> ToolDecisionReceipt:
        return ToolDecisionReceipt(
            request_id=request.request_id,
            run_id=request.run_id,
            agent_id=request.agent_id,
            tool_name=request.tool_name,
            scope=request.scope,
            exact_revision=request.exact_revision,
            request_digest=digest,
            parameters_hash=parameters_hash,
            idempotency_key=request.idempotency_key,
            decision=decision,
            reason_codes=tuple(sorted(set(reasons))),
        )
