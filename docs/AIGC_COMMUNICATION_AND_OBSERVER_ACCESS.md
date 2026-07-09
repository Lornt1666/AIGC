# AIGC Communication and Employer Observer Access

## Purpose

This specification defines how AIGC should prepare communication access for employers, clients, or counterparties.

The operator requested two possible communication paths:

1. A future application/ChatGPT-style observer link where the employer can observe selected project/task/job progress.
2. A contact email where the operator can be reached:

```text
JustLornt95@gmail.com
```

## Current Implementation

This PR does not send invitations or emails automatically.

It prepares a governed observer-access packet that defines:

- who the counterparty is;
- what request/project/task/job they are associated with;
- what they may observe;
- what must remain private;
- which artifacts may be shared after redaction review;
- that observer access is read-only;
- that operator approval is required before sending any invite or communication.

## Files

```text
config/communication_observer_access.json
schemas/communication_observer_access.schema.json
src/core/communication_observer_access.py
src/communication_observer_access_cli.py
```

## Command

```powershell
python .\src\communication_observer_access_cli.py --counterparty-request .\config\counterparty_request_example.json
```

Outputs:

```text
reports/artifacts/communications/<packet_id>/communication_observer_access.json
reports/artifacts/communications/<packet_id>/communication_observer_access.md
```

## Observer Access Principles

Observer access must be:

- read-only;
- counterparty-specific;
- project-specific;
- time-limited where supported;
- revocable by the operator;
- redacted by default;
- limited to selected artifacts;
- separated from unrelated clients;
- separated from private repo internals;
- separated from secrets, credentials, and private operator notes.

## Employer/Client Can See

Only after operator approval, an employer/client may see selected items such as:

- counterparty request summary;
- agreed deliverables;
- acceptance criteria;
- project status;
- selected audit receipts;
- selected evidence packet;
- selected final deliverable.

## Employer/Client Must Not See By Default

- raw secrets;
- credentials;
- private repo internals;
- unrelated client records;
- private operator notes;
- unreviewed drafts;
- internal risk discussion unless operator approves sharing;
- hidden prompts or private reasoning.

## Communication Model

AIGC may draft communication.

AIGC may prepare an invitation packet.

AIGC may prepare a shareable observer packet.

AIGC may not send the invite, email, message, or observer link without operator approval.

## Future ChatGPT/Application Observer Link

A future UI can implement:

```text
Employer Observer View
```

The view should show:

- project/task/job title;
- counterparty request;
- deliverables;
- acceptance criteria;
- current status;
- approved artifacts;
- audit receipts;
- communication log.

It must not expose private AIGC internals or unrelated work.

## Core Rule

The counterparty should be able to observe the work they are entitled to observe.

They should not be able to see private system internals, secrets, unrelated work, or unapproved drafts.

The operator controls visibility and sends/approves all external invitations.
