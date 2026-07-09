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
Find work -> prepare application -> operator submits manually -> prepare work plan -> assist execution -> quality gate -> operator delivers manually
```

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

- auto-apply without the approval-gated action process;
- auto-submit without the approval-gated action process;
- auto-message without the approval-gated action process;
- auto-bid without the approval-gated action process;
- use credentials without reviewed integration;
- bypass platform rules;
- fabricate credentials;
- self-approve.

## Mandatory Counterparty Request Intake

AIGC must not accept vague or unsupported work.

Before any acceptance, bid, submission, payment, purchase, deployment, message, or external delivery can become proceed-capable, the operator must see the counterparty's request and a statement-of-work style review.

See:

```text
docs/AIGC_COUNTERPARTY_REQUEST_INTAKE.md
```

The counterparty intake gate verifies:

- counterparty identity;
- source/platform;
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

If required information is missing, AIGC must ask for clarification before any proceed path is enabled.

## Communication and Observer Access

AIGC may prepare communication and employer/client observer access only through a redacted, read-only, counterparty-specific packet.

See:

```text
docs/AIGC_COMMUNICATION_AND_OBSERVER_ACCESS.md
```

The operator contact email is configured as:

```text
JustLornt95@gmail.com
```

No invite, email, message, or observer link is sent automatically in this PR.

## Work Performance Controls

Once the operator has work, AIGC should assist execution through:

1. Scope clarification.
2. Acceptance criteria definition.
3. Deliverable decomposition.
4. Evidence/source trail.
5. Quality gate.
6. Revision log.
7. Operator review before delivery.

This is how AIGC moves from finding work to helping perform work at a high standard.

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

The operator sees what is being accepted.

The counterparty sees only approved, selected, redacted project artifacts.

The operator crosses the external threshold.

External actions remain manual unless a future reviewed PR implements scoped official integrations with terms review, explicit operator approval, counterparty request visibility, secret-broker controls, audit logging, and blocked-by-default tests.
