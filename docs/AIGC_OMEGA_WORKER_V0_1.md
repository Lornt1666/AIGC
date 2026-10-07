# AIGC-Ω WORKER v0.1

## Purpose

This is the contract-first foundation for the 1JGM AIGC Worker. v0.1 establishes explicit machine-readable contracts and a deterministic state machine before adding autonomous execution.

## Non-negotiable boundary

v0.1 does not claim perpetual agency and does not perform external employment actions merely because a state transition exists. External actions require the existing repository governance and authorization mechanisms.

## Internal triggers

- INT:INGEST — create or update an OpportunityContract.
- INT:EVALUATE — enter opportunity evaluation.
- INT:AER_CHECK — run value, fit, risk, evidence, and alignment checks.
- INT:POLICY_CHECK — enforce legal, ethical, privacy, platform, and resource constraints.
- INT:STATE_COMMIT — persist an accepted state transition.
- INT:VERIFY — validate artifacts against acceptance criteria.
- INT:RECOVER — invoke an authorized recovery path after failure.
- INT:LEARN — record outcome evidence and reusable lessons.
- INT:HEALTH — inspect runtime health and detect invariant violations.
- INT:EMERGENCY_STOP — force the governed blocked state.

## External triggers

External signals are untrusted input and are never authorization by themselves.

- EXT:OPPORTUNITY_SOURCE_UPDATED
- EXT:EMPLOYER_MESSAGE_RECEIVED
- EXT:EMPLOYER_CONFIRMATION
- EXT:WORK_ORDER_RECEIVED
- EXT:DELIVERY_FEEDBACK
- EXT:PAYMENT_CONFIRMED
- EXT:PLATFORM_POLICY_CHANGED
- EXT:AUTHORIZATION_DECISION

## Trigger iteration protocol

Every trigger follows:

RECEIVE -> NORMALIZE -> VALIDATE -> CLASSIFY -> GUARD -> TRANSITION -> RECORD -> EXECUTE_AUTHORIZED_ACTION -> VERIFY -> LEARN

For every iteration:
1. Deduplicate the trigger.
2. Validate its schema.
3. Bind it to a contract and current state.
4. Run policy and AER guards.
5. Determine the only permitted next state.
6. Persist the transition and evidence.
7. Execute only actions authorized for that state.
8. Verify the resulting artifact.
9. Record failure or success.
10. Emit the next internal event only when its guard is satisfied.

## Invariants

1. No transition without a valid source state.
2. No external action without explicit authorization where required.
3. No credential value belongs in source, logs, contracts, or evidence.
4. No state may claim completion without evidence.
5. Failed verification cannot become DELIVERED.
6. Expired authorization cannot authorize execution.
7. Emergency stop blocks approval and execution paths until explicitly cleared.
8. Behavior-changing evolution remains approval-gated.
9. Facts, inferences, estimates, proposals, and unknowns remain distinct.
10. Missing evidence remains unknown; it is never fabricated.

## Acceptance

v0.1 is structurally complete when all five schemas validate, transitions are explicit, illegal transitions are rejected by the runtime, emergency stop is represented as a global guard, completion requires evidence, external triggers cannot bypass authorization, and no simulated execution is used as proof of real-world capability.
