# AIGC_INTEGRATION_CONTRACT_V1_AUTONOMY_AMENDMENT_001

Status: `ACTIVE_COMPATIBILITY_AMENDMENT`
Applies to: `AIGC_INTEGRATION_CONTRACT_V1` (`FROZEN_V1`)
Release train: `release/aigc-nexus-v1`

## Purpose

Clarify the operating policy for maximal autonomy without changing the canonical Nexus object model or constitutional separation.

Governing principle:

`AUTONOMOUS_BY_DEFAULT; EXPLICIT_AUTHORITY_AT_THE_CONSEQUENCE_BOUNDARY`

This amendment does **not** modify the frozen contract file and does not redefine `WorkOrder`, `ContextEnvelope`, `ArtifactState`, `ChangeSet`, `VerifierReport`, `GovernanceDecision`, `ExecutionPermit`, `ToolInvocationRequest`, `ExecutionReceipt`, canonical hashing, reconciliation semantics, credential brokerage, or ToolBroker behavior.

## Compatibility ruling

The frozen contract already permits `GovernanceDecision.authority_source` to be `POLICY` or `HUMAN` and states that reads may follow a lighter governed path. Maximal autonomy is therefore implemented as an authority-source and consequence-classification policy:

- safe/non-consequential work may progress through automatic `POLICY` governance;
- consequential work requires explicit authority before execution;
- a previously validated explicit `ExecutionPermit` may authorize autonomous continuation inside its exact scope, expiry, invocation and cost bounds;
- no model, agent, transcript, memory, evidence item or consequence assessment becomes an authority object.

Default deny remains absolute at the execution boundary.

## Autonomy law

```text
IF material_consequence == false:
    CONTINUE_AUTONOMOUSLY_THROUGH_POLICY_GOVERNANCE
ELSE IF valid_explicit_authority_already_exists == true:
    CONTINUE_AUTONOMOUSLY_WITHIN_EXISTING_AUTHORITY
ELSE IF outcome == INDETERMINATE:
    BLOCK_RETRY_AND_PERFORM_READ_ONLY_RECONCILIATION
ELSE:
    BLOCK_EXECUTION_PENDING_EXPLICIT_AUTHORITY
```

Reasoning, diagnosis, research, design, simulation, testing, evidence preparation and ChangeSet preparation may continue while execution is blocked.

## Consequence classes

Canonical consequence classification for this amendment:

- `PURE`
- `OBSERVATIONAL`
- `REVERSIBLE_INTERNAL`
- `PERSISTENT_INTERNAL`
- `EXTERNAL_READ`
- `EXTERNAL_MUTATION`
- `COMMUNICATION`
- `FINANCIAL`
- `LEGAL`
- `SECURITY_SENSITIVE`
- `PRODUCTION`
- `PHYSICAL`
- `DESTRUCTIVE`
- `IRREVERSIBLE`
- `INDETERMINATE`

The classifier is subordinate to the existing Nexus `EffectClass`. It cannot downgrade an effect class assigned by the ToolBroker.

## Autonomous policy path

The following may be admitted by policy without new human approval when all relevant scope, rate, privacy, security and cost constraints pass:

- reasoning and planning;
- deterministic computation;
- architecture and specification generation;
- candidate code generation;
- local/read-only observation;
- reversible sandbox work;
- simulation and deterministic fixtures;
- testing in an already authorized sandbox;
- public read-only research that requires no private data, credential use, external mutation or incremental spend.

This does not mean these activities bypass governance. It means policy may provide the required governance decision automatically.

## Explicit-authority boundary

New explicit authority is required before an unpermitted material consequence, including:

- persistent state mutation;
- repository mutation;
- private or credentialed external reads;
- external mutation;
- outbound communication or publication;
- financial commitment or spend beyond an authorized envelope;
- credential creation, expansion or disclosure;
- production/deployment changes;
- security-sensitive changes;
- legal or contractual commitment;
- physical effects;
- destructive or irreversible operations.

Existing explicit authority may permit autonomous continuation only when its exact scope remains valid.

## Standing authority

This amendment does not introduce a `StandingAuthority` authority object.

Standing authority is represented by existing Nexus mechanisms, such as a human-approved, bounded, unexpired `ExecutionPermit` and associated policy configuration. A long-lived or recurring authorization must remain scoped, revocable, auditable and non-secret.

`StandingAuthority != NewConstitutionalAuthority`

## Indeterminate consequence law

If an external effect may have occurred but cannot be confirmed:

`execution_status = indeterminate`

Automatic retry is prohibited.

Required path:

`INDETERMINATE -> READ_ONLY_RECONCILIATION -> OBSERVED_STATE -> NEW_CHANGESET_IF_REQUIRED`

## Human operating role

The human is primarily:

- objective setter;
- normative policy setter;
- consequence authority;
- exception arbiter;
- final accountable principal.

The human is not intended to serve as a manual step-by-step scheduler for safe internal work.

## Machine-enforced policy surface

Implementation surfaces introduced by this amendment:

- `src/domain/nexus/autonomy.py`
- `src/core/nexus/autonomy_policy.py`
- `tests/test_nexus_autonomy_policy.py`
- `tests/test_nexus_autonomy_policy_adversarial.py`

`ConsequenceAssessment` is non-authoritative policy input only. It always records `authority_granted=false` and `external_action_performed=false`.

## Preserved constitutional laws

- `Reasoning != Verification != Authority != Execution != Evidence`
- no agent self-authorization;
- Evidence != Authority;
- Memory != Authority;
- Verifier remains read-only;
- credentials do not enter permits;
- ToolBroker remains the effect/scope enforcement boundary;
- ExecutionReceipt remains empirical execution truth;
- indeterminate outcomes require reconciliation;
- no fictional rollback;
- capability growth does not imply authority growth.

## Final law

`MAXIMUM_SAFE_AUTONOMY + MINIMUM_HUMAN_INTERRUPTION`

subject to:

`MATERIAL_CONSEQUENCE -> EXPLICIT_AUTHORITY`

and:

`CAPABILITY_MAY_GROW_AUTONOMOUSLY; AUTHORITY_MAY_NOT.`
