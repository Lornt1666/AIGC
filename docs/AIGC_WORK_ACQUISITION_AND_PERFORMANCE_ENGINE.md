# AIGC Work Acquisition and Performance Engine

## Purpose

This module turns AIGC into a governed work-acquisition and work-performance operator.

The objective is to help the operator:

- search approved work domains;
- rank work opportunities;
- draft truthful application/proposal packets;
- prepare interview and work-scope materials;
- execute paid work using professional delivery standards;
- produce evidence-backed deliverables;
- keep all external commitments manual and operator-controlled.

## Correct Scope

AIGC is not merely a job-search bot.

AIGC is a governed work engine:

```text
Find work -> capture counterparty request -> prepare application -> operator submits manually -> prepare work plan -> assist execution -> quality gate -> operator reviews -> external delivery only if approved
```

## Mandatory Counterparty Intake

AIGC must not accept, bid, submit, pay, purchase, deploy, message, or deliver against vague work.

Before any approval-gated external action can proceed, AIGC must build a counterparty request and acceptance review packet using:

```text
config/counterparty_request_example.json
schemas/counterparty_request_packet.schema.json
schemas/counterparty_acceptance_review.schema.json
src/core/counterparty_request_intake.py
src/counterparty_request_intake_cli.py
docs/AIGC_COUNTERPARTY_REQUEST_INTAKE.md
```

This gate requires the operator to see:

- counterparty identity;
- request source;
- requested action;
- work description;
- success outcome;
- deliverables;
- acceptance criteria;
- terms, compensation, obligations, costs, or payment details;
- timeline;
- constraints;
- attachments;
- communication history;
- missing information;
- risk flags.

If the counterparty request is vague, incomplete, risky, or unsupported by the other party's description, AIGC must ask for clarification before any Proceed path is enabled.

## Domain Registry

Configured in:

```text
config/work_domain_registry.json
```

Initial domain families:

- USAJOBS
- Greenhouse
- Lever
- Ashby
- RemoteOK
- Remotive
- We Work Remotely RSS
- Adzuna
- The Muse
- Arbeitnow
- Jobicy
- Upwork
- Freelancer.com
- Devpost

Each domain defines:

- source mode;
- priority;
- allowed actions;
- blocked actions;
- terms-review requirement;
- operator-commit requirement.

## Work Profile

Configured in:

```text
config/work_acquisition_profile.json
```

The profile defines:

- operator name;
- AIGC positioning;
- skills;
- target work types;
- truthful application standards;
- work performance standards.

## Command

```powershell
python .\src\work_acquisition_cli.py
```

Outputs:

```text
reports/artifacts/work_acquisition/<packet_id>/work_acquisition_packet.json
reports/artifacts/work_acquisition/<packet_id>/work_performance_packet.json
reports/artifacts/work_acquisition/<packet_id>/work_acquisition_report.md
```

Counterparty intake command:

```powershell
python .\src\counterparty_request_intake_cli.py --request .\config\counterparty_request_example.json
```

## Application Preparation Controls

AIGC may:

- search/read approved or public/read-only sources;
- rank opportunity fit;
- draft cover letters;
- draft proposals;
- draft work scopes;
- draft interview notes;
- open/copy links for the operator.

AIGC may not:

- accept vague work;
- auto-apply;
- auto-submit;
- auto-message;
- auto-bid;
- use credentials;
- bypass platform rules;
- fabricate credentials;
- self-approve.

## Work Performance Controls

Once the operator has work, AIGC should assist execution through:

1. Counterparty request intake.
2. Scope clarification.
3. Acceptance criteria definition.
4. Deliverable decomposition.
5. Evidence/source trail.
6. Quality gate.
7. Revision log.
8. Operator review before delivery.

This is how AIGC moves from finding work to helping perform work at a high standard.

## Approval-Gated External Actions

AIGC may prepare approval-gated actions only through:

```text
docs/AIGC_APPROVAL_GATED_EXTERNAL_ACTIONS.md
docs/AIGC_EXTERNAL_ACTION_PROCESSES_AND_PROCEDURES.md
```

The operator must see the exact action, payload, destination, terms, cost/risk state, and audit requirements before clicking Proceed.

## Professional Standard

AIGC should behave like a senior operator assistant:

- precise;
- honest;
- documented;
- evidence-backed;
- scope-aware;
- quality-gated;
- client-useful;
- risk-conscious.

It should surface uncertainty instead of pretending certainty.

It should never claim skills, education, credentials, work history, or completed work that is not real.

## Safety Boundary

AIGC prepares the work path.

The operator crosses the external threshold.

External actions remain manual unless a future reviewed PR implements scoped official integrations with terms review, explicit operator approval, counterparty request validation, secret-broker controls, audit logging, and blocked-by-default tests.
