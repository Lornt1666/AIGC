# AIGC Engineering Review Council Charter

## Status

Proposed governance charter. It defines reviewer roles and procedures but does not appoint real people, grant repository access, or satisfy an independent-review gate by itself.

## Purpose

The AIGC Engineering Review Council provides a standing, role-based human review structure for significant architectural, security, privacy, identity, accessibility, operational, documentation, and release decisions.

## Initial seats

1. Architecture and Systems Reviewer
2. Security, Privacy, and Identity Reviewer
3. Software Quality, Testing, and Data Reviewer
4. Accessibility, Documentation, and Public-Trust Reviewer
5. External Independent General Reviewer

Members review only within declared competence. One person may cover multiple advisory domains, but an independent review must come from an identity distinct from the author/operator.

## Authority model

- AI agents produce advisory evidence.
- Domain reviewers issue reasoned findings.
- An eligible independent human submits GitHub `APPROVE` or `REQUEST_CHANGES` where policy requires it.
- The operator makes the final merge decision after mandatory gates pass.
- No participant may override constitutional, security, privacy, or authorization gates silently.

## Reviewer eligibility

A reviewer must:

- use their own attributable GitHub identity;
- be distinct from the PR author when independence is required;
- disclose material conflicts of interest;
- acknowledge confidentiality and acceptable-use terms;
- review within declared competence;
- inspect the exact head SHA;
- preserve private repository information;
- submit a reasoned decision rather than a courtesy approval.

## Review classification

- `LOW`: one independent general reviewer where required.
- `MODERATE`: one domain reviewer plus one independent reviewer.
- `HIGH`: relevant specialist plus independent reviewer.
- `CONSTITUTIONAL`: domain review, independent review, and operator ratification.
- `RELEASE_CRITICAL`: required specialists, operations/recovery evidence, independent review, and operator authorization.

## Workflow

```text
PR classified
→ required reviewer roles resolved
→ conflicts checked
→ revision-bound review packet issued
→ reviewers accept or decline
→ findings submitted
→ blocking findings resolved
→ independent GitHub decision submitted
→ operator merge decision
→ outcome and lessons recorded
```

## Onboarding packet

Each candidate receives:

- plain-language AIGC overview;
- this charter;
- confidentiality and acceptable-use statement;
- role description;
- minimum review standard;
- Review Packet Generator guide;
- sample decision sheet;
- access-expiry and revocation terms;
- conflict-of-interest declaration;
- escalation and contact procedure.

## Access rules

Repository access must be least-privilege, individually attributable, time-bounded where practical, reviewable, and revocable. Credentials are never transmitted through repository files.

## Compensation ethics

Compensation may cover time and professional analysis. It must never purchase a predetermined approval. Paid arrangements require transparent scope, rate, deliverables, confidentiality, and conflict disclosure.

## Service targets

Targets are not guarantees:

- assignment acknowledgment within two business days;
- small bounded PR review within three to five business days;
- high-risk review timeline agreed after packet inspection;
- small-change re-review within two business days.

Reviewers may decline because of availability, conflict, or insufficient expertise.

## Initial operational milestone

The council becomes minimally operational when:

- at least three distinct eligible people accept defined roles;
- confidentiality, conflict, access, expiry, and revocation procedures exist;
- one legitimate independent review is completed using a revision-bound packet;
- outcomes and lessons are recorded without weakening human judgment.

## PR #29 campaign

The first recruitment objective is one legitimate reviewer for PR #29. The invitation must state the private-repository status, exact PR and head SHA, CI status, bounded review scope, estimated effort, decision options, confidentiality expectations, and access revocation after completion.
