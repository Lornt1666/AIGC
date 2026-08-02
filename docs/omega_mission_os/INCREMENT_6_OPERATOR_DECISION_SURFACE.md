# Increment 6 — Governed Operator Decision Surface

Status: **Implemented for review; local decision recording only**

## Purpose

Increment 6 gives the accountable human operator a bounded local surface to review an exact internal proposal and record one of three decisions:

- `REJECT`
- `REQUEST_REVISION`
- `AUTHORIZE_EXACT_PROPOSAL`

Authorization is a decision receipt. It is **not** execution evidence and does not submit, message, invoice, collect payment, invoke a connector, or transition canonical state.

## Security and authority gates

A decision write requires all of the following:

1. Loopback client.
2. Valid `X-Operator-Token` matching `MISSION_OS_OPERATOR_TOKEN` or an injected local test/runtime token.
3. Exact current `proposal_id`.
4. Exact current 64-character proposal revision digest.
5. Named operator ID and non-empty rationale.
6. Complete counterparty and submission-channel binding for authorization.
7. Explicit requested changes for `REQUEST_REVISION`.

Stale proposal revisions and incomplete bindings fail closed.

## Local decision ledger

Decision receipts are appended to:

```text
.aigc/mission_os/operator_decisions.jsonl
```

The path is configurable for tests and local operation. It is prohibited from residing beneath canonical `data`, `memory`, `governance`, or `config` roots.

Each receipt records:

- decision and status;
- proposal ID and exact revision;
- accountable operator ID;
- rationale and requested changes;
- counterparty and submission channel;
- binding state;
- timestamp;
- SHA-256 receipt digest;
- authorization state;
- explicit `external_action_performed: false`;
- explicit `canonical_state_mutated: false`.

## API

Read decision receipts:

```text
GET /api/v1/operator/decisions
```

Record a decision:

```text
POST /api/v1/operator/decisions
X-Operator-Token: <local secret>
```

Example authorization request:

```json
{
  "decision": "AUTHORIZE_EXACT_PROPOSAL",
  "proposal_id": "proposal_internal_01_example",
  "exact_revision": "<64-character digest>",
  "operator_id": "ACCOUNTABLE_OPERATOR",
  "rationale": "Reviewed scope, evidence, price classification, counterparty, and submission channel."
}
```

## Explicitly absent

There is no route for:

- proposal submission;
- email or platform messaging;
- connector execution;
- contract acceptance;
- invoice issuance;
- payment requests or collection;
- Quest transitions;
- canonical-state mutation.

## Validation

```bash
python -m pytest tests/test_mission_decisions.py
python -m pytest
```

Hosted CI must pass on the exact PR head before the increment may leave draft status.
