from src.core.omega_worker_task_contract import TaskContract, TaskContractError


def contract(**overrides):
    data = dict(
        contract_id="tc-1",
        objective="deliver verified work",
        authorized_scope="deliver-only; idempotent",
        resource_budget=10,
        permitted_actions=("deliver",),
        evidence_requirements=("delivery-proof",),
        postconditions=("accepted",),
        termination_conditions=("verified",),
        retry_max=1,
        rollback_enabled=True,
        rollback_compensating_action="withdraw-draft",
        escalation_policy="OWNER_REVIEW",
        owner="owner-1",
        policy_reference="policy-1",
        expiration="2099-01-01T00:00:00Z",
    )
    data.update(overrides)
    return TaskContract(**data)


def test_contract_is_authoritative_for_action_scope():
    c = contract()
    assert c.allows_action("deliver")
    try:
        c.validate_action("publish")
    except TaskContractError:
        return
    assert False


def test_retry_requires_explicit_idempotency():
    try:
        contract(authorized_scope="deliver-only", retry_max=1)
    except TaskContractError:
        return
    assert False


def test_rollback_requires_compensating_action():
    try:
        contract(rollback_enabled=True, rollback_compensating_action="")
    except TaskContractError:
        return
    assert False


def test_budget_is_bounded():
    c = contract(resource_budget=5)
    c.validate_budget(5)
    try:
        c.validate_budget(6)
    except TaskContractError:
        return
    assert False


def test_required_evidence_cannot_be_empty():
    c = contract()
    try:
        c.validate_evidence("")
    except TaskContractError:
        return
    assert False


def test_missing_contract_metadata_fails_closed():
    try:
        contract(policy_reference="")
    except TaskContractError:
        return
    assert False
