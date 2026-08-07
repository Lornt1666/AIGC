from __future__ import annotations

from src.core.epistemic.tool_broker import EpistemicToolBroker, RunBudgetSnapshot
from src.domain.epistemic.tooling import (
    AgentToolPolicy,
    HumanApprovalReference,
    ToolCapability,
    ToolInvocationRequest,
)


class MemoryLedger:
    """Test-only atomic ledger fake; production broker construction requires injection."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def claim(self, idempotency_key: str, request_digest: str) -> str:
        existing = self.values.get(idempotency_key)
        if existing is None:
            self.values[idempotency_key] = request_digest
            return "claimed"
        if existing == request_digest:
            return "duplicate"
        return "conflict"


class ConflictLedger:
    def claim(self, idempotency_key: str, request_digest: str) -> str:
        return "conflict"


def _policy(*, approval_scopes: tuple[str, ...] = ()) -> AgentToolPolicy:
    return AgentToolPolicy(
        agent_id="AGT-ARCHITECT",
        capabilities=(
            ToolCapability(
                tool_name="repository.read",
                scopes=("read",),
                side_effecting=False,
            ),
            ToolCapability(
                tool_name="repository.write",
                scopes=("write",),
                side_effecting=True,
            ),
        ),
        human_approval_scopes=approval_scopes,
        maximum_requests_per_run=2,
        maximum_cost_units_per_run=10,
    )


def _request(
    *,
    tool_name: str = "repository.read",
    scope: str = "read",
    parameters: dict | None = None,
    estimated_cost_units: int = 1,
    approval_reference: HumanApprovalReference | None = None,
) -> ToolInvocationRequest:
    provisional = ToolInvocationRequest(
        request_id="TREQ-0001",
        run_id="RUN-0001",
        agent_id="AGT-ARCHITECT",
        exact_revision="18bf461aa59c0e1eaf1c95912fbc981b97a0e808",
        tool_name=tool_name,
        scope=scope,
        purpose="epistemic contract test",
        resource_id="Lornt1666/AIGC",
        parameters=parameters or {"path": "README.md"},
        idempotency_key="0" * 64,
        estimated_cost_units=estimated_cost_units,
        approval_reference=approval_reference,
    )
    digest = EpistemicToolBroker.request_digest(provisional)
    return provisional.model_copy(update={"idempotency_key": digest})


def test_default_deny_without_agent_policy() -> None:
    request = _request()
    receipt = EpistemicToolBroker((), ledger=MemoryLedger()).evaluate(request)
    assert receipt.decision == "DENIED"
    assert "NO_AGENT_POLICY" in receipt.reason_codes
    assert receipt.external_action_performed is False


def test_denies_unlisted_tool_and_scope() -> None:
    broker = EpistemicToolBroker((_policy(),), ledger=MemoryLedger())
    receipt = broker.evaluate(_request(tool_name="shell.execute", scope="execute"))
    assert receipt.decision == "DENIED"
    assert "TOOL_NOT_ALLOWED" in receipt.reason_codes


def test_emergency_stop_denies_even_allowed_intent() -> None:
    broker = EpistemicToolBroker((_policy(),), ledger=MemoryLedger(), emergency_stop=True)
    receipt = broker.evaluate(_request())
    assert receipt.decision == "DENIED"
    assert "EMERGENCY_STOP_ACTIVE" in receipt.reason_codes


def test_invalid_idempotency_key_is_denied_before_ledger_claim() -> None:
    request = _request().model_copy(update={"idempotency_key": "f" * 64})
    broker = EpistemicToolBroker((_policy(),), ledger=MemoryLedger())
    receipt = broker.evaluate(request)
    assert receipt.decision == "DENIED"
    assert "INVALID_IDEMPOTENCY_KEY" in receipt.reason_codes


def test_raw_secret_material_is_rejected() -> None:
    broker = EpistemicToolBroker((_policy(),), ledger=MemoryLedger())
    receipt = broker.evaluate(_request(parameters={"api_key": "must-never-enter-contract"}))
    assert receipt.decision == "DENIED"
    assert "RAW_SECRET_MATERIAL_FORBIDDEN" in receipt.reason_codes


def test_request_and_cost_budgets_fail_closed() -> None:
    broker = EpistemicToolBroker((_policy(),), ledger=MemoryLedger())
    request_receipt = broker.evaluate(_request(), budget=RunBudgetSnapshot(requests_used=2))
    cost_receipt = broker.evaluate(
        _request(estimated_cost_units=2),
        budget=RunBudgetSnapshot(requests_used=0, cost_units_used=9),
    )
    assert "REQUEST_BUDGET_EXHAUSTED" in request_receipt.reason_codes
    assert "COST_BUDGET_EXCEEDED" in cost_receipt.reason_codes


def test_write_scope_requires_bound_human_approval() -> None:
    broker = EpistemicToolBroker((_policy(approval_scopes=("write",)),), ledger=MemoryLedger())
    request = _request(tool_name="repository.write", scope="write")
    receipt = broker.evaluate(request)
    assert receipt.decision == "APPROVAL_REQUIRED"
    assert receipt.external_action_performed is False


def test_approval_must_bind_exact_request_and_revision() -> None:
    broker = EpistemicToolBroker((_policy(approval_scopes=("write",)),), ledger=MemoryLedger())
    request = _request(tool_name="repository.write", scope="write")
    bad_approval = HumanApprovalReference(
        approval_id="APR-0001",
        approver_actor_id="operator-1",
        request_digest="a" * 64,
        exact_revision=request.exact_revision,
        status="active",
    )
    receipt = broker.evaluate(request.model_copy(update={"approval_reference": bad_approval}))
    assert receipt.decision == "DENIED"
    assert "APPROVAL_REQUEST_DIGEST_MISMATCH" in receipt.reason_codes


def test_valid_policy_permit_never_executes_tool() -> None:
    broker = EpistemicToolBroker((_policy(),), ledger=MemoryLedger())
    receipt = broker.evaluate(_request())
    assert receipt.decision == "POLICY_PERMIT_PENDING_EXECUTION_GATE"
    assert receipt.external_action_performed is False
    assert receipt.production_activation_authorized is False


def test_idempotent_duplicate_is_not_reported_as_execution_success() -> None:
    ledger = MemoryLedger()
    broker = EpistemicToolBroker((_policy(),), ledger=ledger)
    request = _request()
    first = broker.evaluate(request)
    second = broker.evaluate(request)
    assert first.decision == "POLICY_PERMIT_PENDING_EXECUTION_GATE"
    assert second.decision == "DUPLICATE_INTENT"
    assert second.external_action_performed is False


def test_ledger_conflict_fails_closed() -> None:
    broker = EpistemicToolBroker((_policy(),), ledger=ConflictLedger())
    receipt = broker.evaluate(_request())
    assert receipt.decision == "IDEMPOTENCY_CONFLICT"
    assert "IDEMPOTENCY_KEY_REUSED_FOR_DIFFERENT_REQUEST" in receipt.reason_codes
