from src.core.omega_worker_evidence_ledger import EvidenceLedger
from src.core.omega_worker_recovery import (
    FailureRecoveryEngine, RecoveryDenied, RetryPolicy, RollbackPolicy
)


def test_success_is_verified():
    calls = []
    engine = FailureRecoveryEngine(max_total_attempts=1)
    result = engine.recover(
        contract_id="c1", action="deliver", action_fn=lambda: calls.append(1),
        retry_policy=RetryPolicy(), rollback_policy=RollbackPolicy(),
        verification_check=lambda: True, evidence="e1", remaining_budget=1,
    )
    assert result.status == "VERIFIED"
    assert calls == [1]


def test_idempotency_required_for_retry():
    try:
        RetryPolicy(max_retries=1, idempotent=False)
    except ValueError:
        return
    assert False


def test_failed_idempotent_action_retries_within_bound():
    calls = []
    def fail():
        calls.append(1)
        raise RuntimeError("temporary")
    result = FailureRecoveryEngine(max_total_attempts=2).recover(
        contract_id="c1", action="deliver", action_fn=fail,
        retry_policy=RetryPolicy(max_retries=1, idempotent=True),
        rollback_policy=RollbackPolicy(),
        verification_check=lambda: False, evidence="e1", remaining_budget=2,
    )
    assert result.status == "ESCALATED"
    assert result.attempts == 2


def test_irreversible_action_never_retries():
    calls = []
    def fail():
        calls.append(1)
        raise RuntimeError("failed")
    result = FailureRecoveryEngine(max_total_attempts=3).recover(
        contract_id="c1", action="deliver", action_fn=fail,
        retry_policy=RetryPolicy(max_retries=2, idempotent=True),
        rollback_policy=RollbackPolicy(),
        verification_check=lambda: False, evidence="e1", remaining_budget=3,
        irreversible=True,
    )
    assert result.status == "ESCALATED"
    assert result.attempts == 1
    assert calls == [1]


def test_emergency_stop_blocks_recovery():
    result = FailureRecoveryEngine(max_total_attempts=3, emergency_stop=True).recover(
        contract_id="c1", action="deliver", action_fn=lambda: (_ for _ in ()).throw(RuntimeError()),
        retry_policy=RetryPolicy(max_retries=2, idempotent=True),
        rollback_policy=RollbackPolicy(),
        verification_check=lambda: False, evidence="e1", remaining_budget=3,
    )
    assert result.status == "ESCALATED"
    assert result.reason == "EMERGENCY_STOP"


def test_rollback_requires_authorization_and_compensating_action():
    try:
        RollbackPolicy(enabled=True, authorized=False, compensating_action="undo")
    except ValueError:
        pass
    else:
        assert False
    try:
        RollbackPolicy(enabled=True, authorized=True)
    except ValueError:
        return
    assert False


def test_escalation_package_is_explicit():
    package = FailureRecoveryEngine().build_escalation(
        contract_id="c1",
        failure_reason="verification failed",
        attempted_actions=("deliver",),
        remaining_budget=0,
        recommended_disposition="OWNER_REVIEW",
    )
    assert package.remaining_budget == 0
    assert package.recommended_disposition == "OWNER_REVIEW"


def test_evidence_ledger_can_record_recovery():
    ledger = EvidenceLedger()
    ledger.append("recovery-1", {"status": "ESCALATED", "contract_id": "c1"})
    assert ledger.verify()


def test_missing_evidence_is_denied():
    try:
        FailureRecoveryEngine().recover(
            contract_id="c1", action="deliver", action_fn=lambda: None,
            retry_policy=RetryPolicy(), rollback_policy=RollbackPolicy(),
            verification_check=lambda: True, evidence="", remaining_budget=1,
        )
    except RecoveryDenied:
        return
    assert False
