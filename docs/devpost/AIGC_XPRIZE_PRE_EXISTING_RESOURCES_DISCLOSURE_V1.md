# AIGC XPRIZE Pre-Existing Resources & New-Project Disclosure V1

Status: `ELIGIBILITY EVIDENCE — FINAL ENTRANT DECLARATION / SPONSOR DETERMINATION PENDING`

## Purpose

Provide a conservative, repository-backed explanation of what is the Build with Gemini XPRIZE **Project**, what AIGC framework components existed before the dedicated competition vertical slice, and what was newly introduced during the Submission Period.

This document is designed to support the XPRIZE `New Projects Only` requirement without hiding framework reuse or overstating what Git history proves.

## Governing rule snapshot

The authenticated Build with Gemini XPRIZE rules fetched on 2026-08-09 state:

```text
Submission Period starts:
May 19, 2026 at 10:00 AM Pacific Time

New Projects Only:
Projects must be newly created by the Entrant after the start of the Hackathon Submission Period.
If pre-existing generic templates, frameworks, boilerplates, or code snippets were used to build the final project,
Entrants must explain how their Project utilized pre-existing work.
```

The Sponsor/Administrator retain final eligibility authority.

## Project identity used for this disclosure

For eligibility analysis, the competition Project is the bounded application/business slice represented on Devpost as:

```text
AIGC — Governed Gemini Opportunity Assessment
```

It is **not** represented as every historical idea, framework, governance primitive, or future capability ever associated with AIGC or RegenExcalibur.

## Chronology supported by Git evidence

### 1. Earliest observed AIGC repository baseline in the evidence reviewed here

The exact base commit of PR #1 is:

```text
commit = dd4a2e1b785ebfddee68ee33866d8f7b9d0e21a9
message = Build Milestone B security hardening
created_at = 2026-07-02T15:02:58Z
```

PR #1 itself was created at:

```text
2026-07-02T15:43:08Z
```

This is after the May 19, 2026 Submission Period start.

Important limitation:

```text
EARLIEST OBSERVED GIT EVIDENCE != PROOF OF REPOSITORY GENESIS
```

The connector used for this audit does not expose a definitive repository creation timestamp or prove that no conceptual/off-repository AIGC work existed before July 2. Therefore this document does not use July 2 as an unsupported claim that AIGC itself was first conceived or first worked on that day.

### 2. Generic opportunity/work framework existed before the dedicated Gemini slice

Repository history contains generic AIGC opportunity/work orchestration before PR #145. For example:

```text
2026-07-13
commit f70f4ec182a50001bc9e5cfa535e2132bfa7aa58
feat(quests): add governed Scout, work-acceptance gate, and Quest Board (#77)
```

That generic framework includes opportunity discovery, assessment, candidate/Quest workflows, work-acceptance governance, receipts, audit evidence and idempotency.

It is disclosed here as framework/background capability rather than relabeled as newly invented solely for the Gemini competition Project.

### 3. Dedicated governed Gemini Project slice was introduced during the Submission Period

PR #145:

```text
number = 145
title = Add governed Gemini opportunity assessment workflow
created_at = 2026-07-27T03:56:03Z
base = 84d8fbe57e65eb9b93070646934b71863ac5a4db
head = fcf943a50806e8fd07c2c60ae3afb2d8978ef958
commits = 26
changed_files = 65
additions = 18,215
deletions = 58
```

Its stated outcome is an end-to-end, default-deny governed Gemini opportunity-assessment workflow under RegenExcalibur's business identity.

The PR added a dedicated Gemini architecture including, among other items:

```text
src/gemini_workflow/*
Dockerfile.gemini
cloudbuild.gemini.yaml
requirements-gemini.txt
migrations/002_gemini_runtime_controls.sql
scripts/run_controlled_gemini_canary.py
scripts/deploy_gemini_staging.py
scripts/validate_gemini_staging_authorization.py
config/gemini_* contracts
docs/DEVPOST_GEMINI_WORKFLOW.md
docs/GEMINI_COMPLETION_RUNBOOK.md
docs/GEMINI_REQUIREMENTS_EVIDENCE_MATRIX.md
dedicated Gemini control/runtime/deployment/judge tests
```

### 4. Base-versus-head path existence check

Three representative competition-specific anchor paths were checked against PR #145's exact base commit:

```text
src/gemini_workflow/service.py
scripts/run_controlled_gemini_canary.py
docs/DEVPOST_GEMINI_WORKFLOW.md
```

At base commit:

```text
84d8fbe57e65eb9b93070646934b71863ac5a4db
```

all three returned `404 Not Found`.

At PR #145 head:

```text
fcf943a50806e8fd07c2c60ae3afb2d8978ef958
```

the paths exist and implement the governed Gemini workflow, one-call canary contract and Devpost-specific Gemini architecture.

This is strong repository evidence that those competition-specific components were introduced on the post-May-19 project branch rather than merely renamed from identical pre-existing files.

## Pre-existing/reused resource classes

The Project reuses and evolves AIGC/RegenExcalibur foundations including applicable portions of:

```text
governance and human-approval patterns
evidence/receipt patterns
security and redaction controls
secret-broker concepts
opportunity/work lifecycle concepts
generic orchestration concepts
repository/CI conventions
shared Python/web application foundations
```

These are treated as reused framework capabilities where applicable.

The competition-specific Project adds/extends them into a Gemini-backed business workflow with dedicated:

```text
Gemini provider integration
durable Gemini runtime controls
Gemini-specific intake/assessment/policy contracts
controlled one-call canary semantics
Canadian staging/deployment controls
Gemini-specific evidence and judge receipts
operator/judge surfaces
Devpost/XPRIZE evidence mapping
```

## What this evidence supports

Current evidence supports the following bounded statement:

> The dedicated `AIGC — Governed Gemini Opportunity Assessment` vertical slice was introduced in repository work during the May 19–August 17, 2026 XPRIZE Submission Period, while reusing disclosed AIGC governance/orchestration foundations.

## What this evidence does NOT prove by itself

Do not infer from this document alone that:

```text
all AIGC concepts were created after May 19
RegenExcalibur was created after May 19
no off-repository work existed before May 19
the Sponsor has pre-approved eligibility
July 27 is necessarily the operator's actual first day of work on the competition Project
pre-existing IP/license review is complete
```

## Devpost project-start-date handling

The earliest **competition-specific repository timestamp established here** is PR #145 creation on July 27, 2026.

That timestamp is suitable as evidence of the Project existing by that date. It should not be substituted for an earlier truthful actual start date if the Entrant knows the dedicated competition Project work began earlier.

Therefore the submission contract currently keeps:

```text
project_start_date = PARTIAL
```

until the final Entrant declaration is reconciled with this repository chronology.

## Required remaining eligibility closeout

Before final submission, explicitly resolve:

```text
1. actual competition Project start date;
2. Entrant type: individual, team or organization;
3. Representative authority if team/organization;
4. age/geographic eligibility;
5. organization size <25 employees if entering as organization;
6. exact third-party/open-source/provider license and terms compliance;
7. original-work/IP ownership declaration;
8. confirmation that no disqualifying Sponsor/Administrator financial or preferential support applies;
9. final pre-existing-resource disclosure wording on Devpost.
```

## Completion boundary

```text
repository chronology evidence = STRONG_PARTIAL
new-project eligibility final = false
pre-existing-work disclosure final = false
sponsor eligibility determination = external
Devpost submission authority = false
```
