# AIGC Canonical Job Lifecycle v1

Status: **Proposed for operator review**  
Contract: `AIGC-JOB-LIFECYCLE-001`  
Version: `1.0.0`

## Purpose

Provide one authoritative vocabulary for AIGC job acquisition, internal execution, review, delivery evidence, and closure before durable job persistence, Run/Accept API wiring, or operator UI implementation.

This standard is contract-first and non-executing. It does not mutate jobs, deliver work, invoke connectors, use credentials, deploy, or grant production authority.

## Two-ring lifecycle

### Ring A — acquisition and commitment

```text
DISCOVERED
→ QUALIFIED
→ PROPOSED
→ APPROVAL_REQUIRED
→ WORK_ACCEPTED
```

`WORK_ACCEPTED` means the operator authorizes AIGC to undertake bounded internal work. It does not mean completed work passed review.

### Ring B — internal execution and delivery evidence

```text
RESEARCHING
→ PLANNING
→ EXECUTING_LOCALLY
→ REVIEW_REQUIRED
→ ACCEPTED_FOR_DELIVERY
→ DELIVERED
→ CLOSED
```

`ACCEPTED_FOR_DELIVERY` means the operator accepted the reviewed work product. `DELIVERED` may be recorded only after a separate normalized delivery execution receipt exists. The lifecycle transition itself never performs the external delivery.

### Exception states

```text
REWORK_REQUIRED
REJECTED
CANCELLED
```

Rejection and cancellation require attributable reasons. Cancellation after work commitment requires compensation or rollback evidence where the transition contract specifies it.

## Semantic correction

The generic state `ACCEPTED` is prohibited because current repository artifacts use it for two different decisions:

1. acceptance of the work commitment before research; and
2. acceptance of completed work after review and before delivery.

The canonical terms are therefore:

- `WORK_ACCEPTED`
- `ACCEPTED_FOR_DELIVERY`

## Authority classes

| Authority class | Concrete control |
|---|---|
| `POLICY_AUTHORIZATION` | A valid internal policy decision permits a non-consequential state change. |
| `OPERATOR_JOB_ACCEPTANCE` | The operator accepts or rejects the proposed work commitment. |
| `OPERATOR_LOCAL_EXECUTION` | The operator authorizes execution inside the local, non-production boundary. |
| `OPERATOR_WORK_REVIEW` | The operator accepts, rejects, or returns completed work for rework. |
| `OPERATOR_DELIVERY_AUTHORIZATION` | The operator authorizes recording delivery only when the separate delivery receipt exists. |
| `OPERATOR_JOB_CLOSURE` | The operator closes the job after delivery and counterparty-status evidence. |
| `OPERATOR_CANCELLATION` | The operator cancels with an attributable reason and required compensation evidence. |

Authorization, operator decision, counterparty decision, connector execution, and verified outcome are distinct facts. None may be inferred from another.

## External-action boundary

The canonical lifecycle performs internal state changes only.

```text
Lifecycle decision
→ action proposal
→ Security & Privacy Wiring Gate
→ connector policy gateway
→ operator approval
→ connector adapter
→ normalized execution receipt
→ lifecycle records the verified outcome
```

Until the connector train is separately procured and approved, transitions requiring external receipts remain unavailable in runtime integration.

## Compatibility

The compatibility map records the current relationship to:

- `AIGC_FULL_STACK_ARCHITECTURE_PROGRAM.md`;
- draft PR #64's governed job state machine;
- the legacy work-order preparation module.

Mappings are classified as `EXACT`, `SEMANTIC_RENAME`, `TRANSITION_EXPANSION_REQUIRED`, `CONFLICTING`, or `UNSUPPORTED`. Lossy or conflicting mappings require an operator decision and may not occur silently.

## Persistence rule

When durable job storage is implemented, every job state record must include:

- canonical contract identifier;
- contract version;
- state identifier;
- revision;
- transition receipt identifier;
- authorization receipt identifier where required;
- exact source revision;
- audit event identifier.

Unknown contract versions or state identifiers fail closed.

## UI rule

Operator controls must use semantic verbs, not a generic `Accept` control:

- **Accept work**
- **Authorize local execution**
- **Accept for delivery**
- **Authorize delivery**
- **Close job**

Each control must present the current state, requested state, authority class, evidence, reason requirements, and external-action consequence before confirmation.

## Review and ratification

This proposed contract becomes authoritative only after:

1. schema and graph tests pass;
2. exact-head CI evidence is proven;
3. all blocking semantic conflicts are resolved;
4. PR #64 receives a documented correction or sub-lifecycle classification;
5. the operator reviews the final immutable head;
6. an expected-head-protected merge is explicitly authorized;
7. exact-main verification succeeds.

Independent human review is not claimed. Production identity and external execution remain blocked.

## Rollback

Before merge, abandon or close the branch. After an authorized squash merge, revert the single squash commit and restore the prior registry reference. No database or external compensation is required because this standard does not mutate runtime state.

`external_action_performed: false`
