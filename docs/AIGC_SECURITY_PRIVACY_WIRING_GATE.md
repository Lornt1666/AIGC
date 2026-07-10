# AIGC Security & Privacy Wiring Gate

## Purpose

The Security & Privacy Wiring Gate is the mandatory corridor for sensitive AIGC actions.

It prevents work acquisition, counterparty intake, observer access, chat-log sharing, approval-gated external actions, and communication packets from bypassing the security architecture.

The gate is contract-first and receipt-driven.

## Core Wiring Model

```text
input/request/job/observer/action
-> hard-block precheck
-> counterparty request intake
-> observer authority verification
-> redaction/privacy review
-> Sentinel policy review
-> approval-gated procedure packet
-> operator popup review
-> audit receipt
```

No sensitive path should go directly from request to action.

## Files

```text
schemas/security_privacy_wiring_receipt.schema.json
config/security_privacy_wiring_policy.json
src/core/security_privacy_wiring.py
src/security_privacy_wiring_cli.py
tests/test_security_privacy_wiring.py
docs/AIGC_SECURITY_PRIVACY_WIRING_GATE.md
```

## Command

```powershell
python .\src\security_privacy_wiring_cli.py --request .\config\counterparty_request_example.json
```

Output:

```text
reports/artifacts/security_privacy_wiring/<receipt_id>/security_privacy_wiring_receipt.json
reports/artifacts/security_privacy_wiring/<receipt_id>/security_privacy_wiring_report.md
```

## Required Controls

### 1. Counterparty request intake

No action approval is allowed unless the counterparty request is complete enough for the operator to see:

- who is asking;
- what they need done;
- requested action;
- deliverables;
- acceptance criteria;
- compensation, obligations, costs, or terms;
- timeline;
- constraints;
- communication history;
- risk flags and missing information.

If the intake gate returns `insufficient_information` or `blocked_pending_risk_review`, the wiring receipt blocks the path.

### 2. Observer authority verification

No observer access is allowed unless the observer has verified authority.

Required authority evidence:

- identity proof;
- organization or platform linkage;
- role authority;
- specific project/request scope;
- counterparty request linkage;
- expiry;
- revocation;
- audit receipt.

The observer must not receive whole-account access, backend access, raw chat-log access, or unrelated project visibility.

### 3. Redaction and privacy review

The wiring gate blocks requests that contain raw secret markers or private-data markers.

Sharing actions require explicit redaction review before proceeding.

Sharing actions include:

- messages;
- deliverables;
- observer access;
- chat-log packet sharing;
- observer packet sharing.

### 4. Sentinel policy review

The Sentinel policy must remain:

- deny-by-default;
- operator-popup required;
- audit-receipt required;
- external-action performed false by default.

### 5. Approval-gated procedure packet

External action families require an approval-gated procedure packet.

External action families include:

- apply;
- submit;
- accept;
- pay;
- purchase;
- deploy;
- bid;
- message;
- deliver work.

The procedure packet remains preparation-only. Live execution stays blocked unless a future connector PR satisfies every required gate.

## Receipt Fields

Each reviewed action produces:

```text
security_privacy_wiring_receipt.json
```

Required fields:

- `decision_state`
- `blocked_reason`
- `required_next_step`
- `enabled_controls`
- `disabled_controls`
- `gate_results`
- `operator_popup_required`
- `proceed_enabled`
- `external_action_performed=false`

## Decision States

Typical states:

```text
blocked
ready_for_operator_review
ready_for_operator_review_high_risk
```

A blocked receipt must include a specific blocked reason and required next step.

## Future Cockpit Tab

Future UI tab:

```text
Security & Privacy Gate
```

The cockpit should display:

- request ID;
- requested action;
- counterparty intake status;
- observer authority status;
- redaction/privacy status;
- Sentinel status;
- procedure-packet status;
- proceed enabled / disabled;
- blocked reason;
- required next step;
- audit receipt path.

## Non-Negotiable Hard Blocks

The gate blocks:

- raw secrets;
- raw chat-log sharing;
- whole-account access;
- backend access;
- self-approval;
- fabricated credentials;
- platform-rule bypass;
- unverified observer authority;
- silent external sharing.

## Future Live Connector Rule

No future connector may perform a live external action until it proves:

- counterparty request intake passed;
- observer authority verification passed when observer/sharing is involved;
- redaction/privacy review passed;
- approval-gated procedure packet exists;
- operator clicked Proceed;
- audit receipt was written;
- rollback/correction plan exists;
- tests prove hard-blocked actions remain blocked.

## Core Doctrine

AIGC routes sensitive work through one visible, auditable, operator-controlled security corridor.

The system prepares. The operator reviews. External execution remains blocked unless a future approved connector satisfies every gate.
