# AIGC Quest Work-Acceptance Gate v1

## Decision semantics

This gate governs an internal AIGC lifecycle decision:

```text
Quest PROPOSED
→ APPROVAL_REQUIRED
→ WORK_ACCEPTED
```

`WORK_ACCEPTED` means the accountable operator has authorized AIGC to undertake the bounded internal work described by the Quest. It does **not**:

- accept an external contract;
- submit an application or bid;
- message a counterparty;
- use credentials;
- deliver work;
- receive or send payment;
- deploy software;
- perform any other consequential external action.

Completed-work review remains a later and distinct gate:

```text
REVIEW_REQUIRED
→ REWORK_REQUIRED | ACCEPTED_FOR_DELIVERY
```

Generic canonical `ACCEPTED` is prohibited.

## Operator sequence

### 1. Create the proposed Quest

The existing candidate workflow remains separate:

```text
Candidate DISCOVERED
→ Candidate QUALIFIED
→ Quest PROPOSED
```

Qualification never creates or accepts work by itself.

### 2. Request work approval

```http
POST /api/v1/quests/{quest_id}/request-work-approval
Content-Type: application/json
```

```json
{
  "expected_revision": 1,
  "operator_role": "ACCOUNTABLE_OPERATOR",
  "reason": "Review the bounded internal work commitment."
}
```

The transition is optimistic-revision checked, atomic, audited, and idempotent. It creates:

- an `APPROVAL_REQUIRED` Quest;
- a deterministic approval-request identifier;
- a planned `APPROVAL_REQUIRED → WORK_ACCEPTED` transition digest;
- a revision binding;
- the exact authorization action, scope, purpose, resource and evidence requirements.

No work is accepted at this step.

### 3. Prepare the local authorization bundle

```http
GET /api/v1/quests/{quest_id}/work-acceptance-authorization-bundle
```

The response contains a strict local-simulation authorization bundle bound to:

- the current Quest identifier and revision;
- action `accept_work`;
- scope `quest:work_accept`;
- purpose `work_acceptance`;
- the approval-request evidence identifier;
- the transition-digest evidence identifier;
- IAL0/AAL0/FAL0 local-simulation assurance.

The bundle is synthetic local evidence. It does not establish production identity.

### 4. Evaluate and persist authorization

```http
POST /api/v1/identity/authorize
Content-Type: application/json
```

Send the returned `bundle` object as the request body. Continue only when:

```json
{
  "result": "PERMIT",
  "passed": true
}
```

The authorization service stores an immutable SQLite receipt. The receipt itself records:

- `state_changed: false`;
- `external_action_performed: false`.

Authorization evaluation does not mutate the Quest.

### 5. Accept bounded internal work

```http
POST /api/v1/quests/{quest_id}/accept-work
Content-Type: application/json
```

```json
{
  "expected_revision": 2,
  "operator_role": "ACCOUNTABLE_OPERATOR",
  "authorization_receipt_id": "AUTHZ-...",
  "authorization_request": {
    "request_id": "REQ-WORK-ACCEPT-..."
  },
  "reason": "Proceed with bounded internal work."
}
```

The complete authorization request returned by step 3 must be supplied. The gate verifies that the durable `PERMIT` receipt is bound to the exact:

- source revision;
- Quest resource;
- action;
- scope;
- purpose;
- request digest;
- approval-request evidence;
- transition digest.

A changed or substituted request fails closed. Successful acceptance persists:

- lifecycle state `WORK_ACCEPTED`;
- consumed approval-request evidence;
- receipt and decision identifiers;
- authorization request digest and exact revision;
- principal identifier;
- append-only audit evidence;
- `external_action_performed: false`.

The response also states `external_contract_accepted: false`.

## Rejection and cancellation

### Reject a proposed or approval-pending Quest

```http
POST /api/v1/quests/{quest_id}/reject
```

```json
{
  "expected_revision": 1,
  "operator_role": "ACCOUNTABLE_OPERATOR",
  "reason": "Outside the bounded operating scope."
}
```

### Cancel a proposed, approval-pending, or work-accepted Quest

```http
POST /api/v1/quests/{quest_id}/cancel
```

```json
{
  "expected_revision": 2,
  "operator_role": "ACCOUNTABLE_OPERATOR",
  "reason": "Operator withdrew the internal work proposal."
}
```

Both commands require a reason, use optimistic revisions, write atomic audit evidence, and recover identical retries idempotently. Changed retries fail closed.

## Composite Quest Board projection

```http
GET /api/v1/quest-board
```

The read model returns:

- candidates;
- active Quests;
- candidate and lifecycle counts;
- canonical work/delivery acceptance semantics;
- local assurance state;
- `external_action_performed: false`.

Optional query filters:

- `candidate_status`;
- `quest_state`.

## Browser interface

Open:

```text
http://127.0.0.1:8000/quest-board
```

The interface exposes only explicit commands:

- `Request work approval`;
- `Authorize and accept work`;
- `Reject Quest`;
- `Cancel Quest`.

There is no generic **Accept** button and no free-form decision prompt. An inline reason field records the operator basis. The browser performs the same authorization and lifecycle calls documented above.

## Failure behavior

The gate fails closed on:

- missing Quest;
- invalid lifecycle source state;
- stale revision;
- non-accountable operator;
- missing or non-`PERMIT` receipt;
- altered authorization request;
- wrong Quest resource;
- wrong action, scope or purpose;
- missing transition evidence;
- receipt/request exact-revision mismatch;
- changed idempotent replay;
- attempted external-action recording.

## Current assurance boundary

This implementation is local behavioral evidence only:

- IAL0/AAL0/FAL0;
- SQLite persistence;
- no production identity;
- no production deployment authorization;
- no live write connector;
- no external contract acceptance;
- no external action.

Production use requires a separately approved production identity/access architecture and revision-bound operational evidence.
