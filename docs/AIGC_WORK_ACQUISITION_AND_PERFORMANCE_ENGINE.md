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

The operator crosses the external threshold.

External actions remain manual unless a future reviewed PR implements scoped official integrations with terms review, explicit operator approval, secret-broker controls, audit logging, and blocked-by-default tests.
