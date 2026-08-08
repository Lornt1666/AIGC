from __future__ import annotations

from enum import Enum


class ExecutionState(str, Enum):
    RECEIVED = "RECEIVED"
    ATTESTATION_VERIFIED = "ATTESTATION_VERIFIED"
    DECRYPTED = "DECRYPTED"
    SCHEMA_VALIDATED = "SCHEMA_VALIDATED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    PLANNED = "PLANNED"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMMITTED = "COMMITTED"
    RECEIPT_PUBLISHED = "RECEIPT_PUBLISHED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    UNCERTAIN_EXTERNAL_OUTCOME = "UNCERTAIN_EXTERNAL_OUTCOME"
    COMPENSATION_REQUIRED = "COMPENSATION_REQUIRED"


_TERMINAL = frozenset(
    {
        ExecutionState.RECEIPT_PUBLISHED,
        ExecutionState.REJECTED,
        ExecutionState.QUARANTINED,
        ExecutionState.CANCELLED,
        ExecutionState.TIMED_OUT,
        ExecutionState.UNCERTAIN_EXTERNAL_OUTCOME,
    }
)

_ALLOWED: dict[ExecutionState, frozenset[ExecutionState]] = {
    ExecutionState.RECEIVED: frozenset(
        {ExecutionState.ATTESTATION_VERIFIED, ExecutionState.REJECTED}
    ),
    ExecutionState.ATTESTATION_VERIFIED: frozenset(
        {ExecutionState.DECRYPTED, ExecutionState.REJECTED}
    ),
    ExecutionState.DECRYPTED: frozenset(
        {ExecutionState.SCHEMA_VALIDATED, ExecutionState.QUARANTINED}
    ),
    ExecutionState.SCHEMA_VALIDATED: frozenset(
        {ExecutionState.POLICY_EVALUATED, ExecutionState.REJECTED}
    ),
    ExecutionState.POLICY_EVALUATED: frozenset(
        {ExecutionState.PLANNED, ExecutionState.REJECTED}
    ),
    ExecutionState.PLANNED: frozenset(
        {
            ExecutionState.AUTHORIZATION_REQUIRED,
            ExecutionState.CANCELLED,
        }
    ),
    ExecutionState.AUTHORIZATION_REQUIRED: frozenset(
        {ExecutionState.AUTHORIZED, ExecutionState.REJECTED}
    ),
    ExecutionState.AUTHORIZED: frozenset(
        {ExecutionState.EXECUTING, ExecutionState.CANCELLED}
    ),
    ExecutionState.EXECUTING: frozenset(
        {
            ExecutionState.VERIFYING,
            ExecutionState.TIMED_OUT,
            ExecutionState.UNCERTAIN_EXTERNAL_OUTCOME,
            ExecutionState.COMPENSATION_REQUIRED,
        }
    ),
    ExecutionState.VERIFYING: frozenset(
        {
            ExecutionState.COMMITTED,
            ExecutionState.QUARANTINED,
            ExecutionState.COMPENSATION_REQUIRED,
        }
    ),
    ExecutionState.COMPENSATION_REQUIRED: frozenset(
        {
            ExecutionState.VERIFYING,
            ExecutionState.UNCERTAIN_EXTERNAL_OUTCOME,
        }
    ),
    ExecutionState.COMMITTED: frozenset({ExecutionState.RECEIPT_PUBLISHED}),
    **{state: frozenset() for state in _TERMINAL},
}


def transition(
    current: ExecutionState,
    target: ExecutionState,
    *,
    authorization_verified: bool = False,
    external_effect_requested: bool = False,
    idempotency_key_present: bool = False,
) -> ExecutionState:
    if target not in _ALLOWED[current]:
        raise ValueError(f"invalid execution transition: {current.value} -> {target.value}")
    if target is ExecutionState.AUTHORIZED and authorization_verified is not True:
        raise PermissionError("authorization transition requires verified authorization")
    if target is ExecutionState.EXECUTING and external_effect_requested:
        if authorization_verified is not True:
            raise PermissionError("external execution requires verified authorization")
        if idempotency_key_present is not True:
            raise PermissionError("external execution requires an idempotency key")
    return target


def is_terminal(state: ExecutionState) -> bool:
    return state in _TERMINAL
