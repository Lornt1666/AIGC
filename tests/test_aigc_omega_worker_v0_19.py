from src.core.omega_worker_task_contract import TaskContract
from src.core.omega_worker_recovery import RetryPolicy, RollbackPolicy
from src.core.omega_worker_synthetic_coliseum import SyntheticColiseum, SyntheticScenario


def make_contract(**kw):
    d=dict(
        contract_id="tc-synth", objective="synthetic delivery",
        authorized_scope="synthetic; idempotent", resource_budget=3,
        permitted_actions=("deliver",), evidence_requirements=("proof",),
        postconditions=("verified",), termination_conditions=("done",),
        retry_max=1, rollback_enabled=True,
        rollback_compensating_action="undo-synthetic",
        escalation_policy="OWNER_REVIEW", owner="owner",
        policy_reference="policy", expiration="2099-01-01T00:00:00Z")
    d.update(kw)
    return TaskContract(**d)


def scenario(**kw):
    d=dict(
        scenario_id="s1", contract=make_contract(), action="deliver",
        metrics=None, owner_gate=True, permit=None, postcondition=None,
        action_fn=lambda: None, verification_check=lambda: True,
        evidence="synthetic-proof", remaining_budget=3,
        retry_policy=RetryPolicy(), rollback_policy=RollbackPolicy())
    d.update(kw)
    return SyntheticScenario(**d)


def test_happy_path_is_verified_and_side_effect_free():
    result=SyntheticColiseum().run(scenario())
    assert result.status=="VERIFIED"
    assert result.ledger_valid
    assert result.external_side_effects is False


def test_owner_gate_prevents_execution():
    calls=[]
    result=SyntheticColiseum().run(scenario(owner_gate=False, action_fn=lambda: calls.append(1)))
    assert result.status=="BLOCKED"
    assert calls==[]


def test_failed_verification_enters_recovery():
    result=SyntheticColiseum().run(
        scenario(verification_check=lambda: False,
                 retry_policy=RetryPolicy(max_retries=1, idempotent=True)))
    assert result.recovery_status in {"ESCALATED", "ROLLBACK_REQUIRED", "BLOCKED"}
    assert result.external_side_effects is False


def test_irreversible_failure_does_not_retry():
    calls=[]
    def fail():
        calls.append(1)
        raise RuntimeError("synthetic failure")
    result=SyntheticColiseum().run(
        scenario(action_fn=fail, irreversible=True,
                 retry_policy=RetryPolicy(max_retries=2, idempotent=True)))
    assert result.status=="ESCALATED"
    assert calls==[1]


def test_ledger_contains_run_evidence():
    harness=SyntheticColiseum()
    harness.run(scenario())
    assert len(harness.ledger.entries)==2
    assert harness.ledger.verify()
