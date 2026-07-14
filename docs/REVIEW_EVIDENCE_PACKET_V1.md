# Review Evidence Packet v1 and Human Judgment Gate

Status: implementation candidate on a stacked review branch.  
Packet contract: `AIGC-REVIEW-EVIDENCE-PACKET-001`  
Judgment contract: `AIGC-REVIEW-JUDGMENT-RECEIPT-001`  
Production identity configured: No  
Delivery performed: No  
External action performed: No

## Purpose

Review Evidence Packet v1 creates an immutable, structured record of what bounded internal work claims to have accomplished. It does not judge the work, change Quest state, accept delivery, or perform an external action.

A separate accountable human judgment gate decides whether evidence supports:

- `ACCEPTED_FOR_DELIVERY`; or
- `REWORK_REQUIRED`.

Acceptance for delivery is an internal readiness decision. It does not transmit, publish, submit, deploy, message, invoice, receive payment, or deliver anything externally.

## Governed flow

```text
WORK_ACCEPTED or REWORK_REQUIRED Quest
→ server-owned review PIBC preflight
→ immutable PIBC receipt
→ Review Evidence Packet generation
→ packet persisted append-only; Quest unchanged
→ identity-bound submit_review authorization
→ immutable authorization receipt
→ Quest repository transition to REVIEW_REQUIRED
→ accountable reviewer PIBC receipt
→ identity-bound judge_review authorization
→ immutable authorization receipt
→ immutable Review Judgment Receipt
→ Quest repository transition to
   ACCEPTED_FOR_DELIVERY or REWORK_REQUIRED
```

Omega-X is not involved in this implementation.

## Packet contents

Every packet binds:

- Quest ID and exact Quest revision;
- source lifecycle state;
- exact source revision;
- reviewer identity, tenant and project;
- persisted PIBC receipt;
- persisted work-authorization receipt;
- work-acceptance request digest;
- executive summary;
- every Quest acceptance criterion;
- criterion status and evidence references;
- artifact paths and SHA-256 values;
- test receipts;
- source references and rights status;
- security, privacy and policy findings;
- unresolved blockers;
- rework recommendations;
- evidence identifiers;
- deterministic request and packet digests;
- advisory and human-review boundaries.

The service derives criterion text from the persisted Quest. Callers cannot rewrite the acceptance criteria inside a packet.

## Evidence maturity

Artifact entries declare one of:

- `DECLARED`;
- `HASH_VERIFIED`;
- `TESTED`;
- `CI_OBSERVED`.

These values communicate evidence maturity. They do not independently prove production operation.

Test receipts declare:

- `PASS`;
- `FAIL`; or
- `NOT_APPLICABLE`.

The service replaces any caller revision with the server-owned exact revision before contract validation and persistence.

## Readiness calculation

A packet is a delivery candidate only when:

```text
all acceptance criteria = SATISFIED
and all test receipts = PASS or NOT_APPLICABLE
and at least one test receipt exists
and unresolved blockers = empty
```

Otherwise the recommended decision is `REWORK_REQUIRED`.

The recommendation remains advisory. Only the human judgment command changes Quest state.

## Packet immutability

Migration:

```text
migrations/sqlite/0003_review_evidence_packet_v1.sql
```

Tables:

```text
review_evidence_packets
review_judgment_receipts
```

Database triggers prohibit update and deletion.

One Quest revision may have only one Review Evidence Packet. One packet may have only one human judgment. Changed evidence requires a later Quest revision and a new packet.

## Review identity

The local review preflight endpoint accepts only:

- Quest ID from the route;
- expected Quest revision;
- literal `ACCOUNTABLE_OPERATOR` role.

It resolves principal, membership, session, tenant, project and assurance exclusively from the repository-owned local fixture.

It is fixed to local simulation and cannot establish production identity.

## Authorization

Both state-changing review commands use the existing:

- `AuthorizationApplicationService`;
- `PrincipalAuthorityBindingKernel`;
- immutable authorization receipt repository;
- exact-revision, resource, action, scope, purpose and evidence checks.

Actions:

| Command | Action | Scope | Purpose |
|---|---|---|---|
| Open review gate | `submit_review` | `quest:review_submit` | `review_submission` |
| Human judgment | `judge_review` | `quest:review_judge` | `review_judgment` |

Authorization receipts must include the PIBC receipt and required packet evidence identifiers.

## API

### Review identity preflight

```text
POST /api/v1/quests/{quest_id}/local-review-identity-preflight
```

```json
{
  "expected_revision": 3,
  "operator_role": "ACCOUNTABLE_OPERATOR"
}
```

### Generate packet

```text
POST /api/v1/quests/{quest_id}/review-packets
```

The request supplies evidence content, not authority. Unknown fields are rejected.

Packet generation returns:

```text
quest_state_changed = false
human_judgment_required = true
external_action_performed = false
```

### Open the review gate

```text
POST /api/v1/quests/{quest_id}/review-gate/open
```

```json
{
  "expected_revision": 3,
  "packet_id": "REP-AAAAAAAAAAAAAAAAAAAAAAAA",
  "identity_receipt_id": "IDR-BBBBBBBBBBBBBBBBBBBBBBBB",
  "operator_role": "ACCOUNTABLE_OPERATOR"
}
```

### Judge the packet

```text
POST /api/v1/quests/{quest_id}/review-gate/judge
```

```json
{
  "expected_revision": 4,
  "packet_id": "REP-AAAAAAAAAAAAAAAAAAAAAAAA",
  "identity_receipt_id": "IDR-CCCCCCCCCCCCCCCCCCCCCCCC",
  "operator_role": "ACCOUNTABLE_OPERATOR",
  "decision": "ACCEPTED_FOR_DELIVERY",
  "reason": "Acceptance criteria and test evidence are satisfactory."
}
```

The service rejects `ACCEPTED_FOR_DELIVERY` when the packet is not a delivery candidate.

### Query evidence

```text
GET /api/v1/quests/{quest_id}/review-packets
GET /api/v1/review-packets/{packet_id}
```

## Failure behavior

The implementation fails closed on:

- missing or forged PIBC receipt;
- expired identity evidence;
- incorrect operator role;
- stale Quest revision;
- unsupported Quest state;
- mismatched packet and Quest revision;
- changed packet content on the same Quest revision;
- missing work-authorization evidence;
- principal mismatch between work acceptance and review identity;
- incomplete acceptance-criteria assessment;
- missing evidence or notes for a criterion;
- altered exact revision;
- authorization denial;
- premature delivery acceptance;
- second, conflicting judgment;
- unknown request fields.

## Rollback

Runtime wiring may be reverted through a reviewed change. The additive tables and prior immutable evidence should remain. Do not delete or rewrite packets, judgments, authorization receipts or audit events during rollback.

## Non-scope

This component does not include:

- Omega-X orchestration;
- automatic work execution;
- automatic human judgment;
- live OIDC or workload identity;
- hosted production authentication;
- external delivery;
- deployment;
- contract acceptance;
- application or bid submission;
- messaging;
- payment;
- publication;
- readiness-score promotion.

## Required review gates

Before merge:

1. exact-head CI passes;
2. contract and redaction validation passes;
3. migration and append-only tests pass;
4. full existing Quest and identity regressions pass;
5. the operator reviews the stacked diff;
6. dependency PRs are handled in order;
7. merge remains an explicit decision.

> Procurement grants direction. Implementation supplies substance. Verification supplies proof. The operator grants authority.
