# AIGC Build with Gemini XPRIZE Submission Contract V1

Status: `LIVE REQUIREMENTS SNAPSHOT — FINAL SUBMISSION BLOCKED`

## Purpose

Bind the current connected Devpost requirements to machine-readable AIGC evidence states so the public project page and final submission cannot outrun the repository/runtime evidence.

Requirements were retrieved from the authenticated Devpost integration on 2026-08-09.

## Current challenge facts

```text
challenge = Build with Gemini XPRIZE
slug = xprize
submissions_end = 2026-08-17T20:00:00Z
host_timezone = Pacific Time (US & Canada)
current_phase = submissions_open
```

Judging criteria:

```text
Business Viability
AI-Native Operations
Category Impact
```

## Current AIGC Devpost project

```text
project_id = 1289277
slug = facade-excalibur
name = AIGC — Governed Gemini Opportunity Assessment
state = published
video_url = absent
```

The public copy remains technically stale because its narrative describes PR #170 / the older Gemini release train, while the canonical repository integration has advanced to PR #181 / Nexus V1.

`PUBLIC PROJECT EXISTS != CURRENT SUBMISSION EVIDENCE`

## Mandatory evidence classes

The connected host requirements demand evidence covering at least:

- GitHub repository access for the specified judge/testing accounts;
- three-minute demonstration video;
- 500–1000-word description of AI operations and human/AI responsibilities;
- revenue evidence and simple P&L;
- hackathon-period expenses including marketing/customer-acquisition spend even when zero;
- product evidence such as agent execution/API/dashboard evidence;
- customer/user evidence;
- Google Cloud usage;
- Gemini API use where the project uses an LLM;
- project-running evidence upload including Google Cloud billing/cost evidence and Gemini observability evidence;
- users acquired and paying-user counts;
- pre-existing resource disclosure.

The exact required field IDs are versioned in `config/xprize_submission_contract.json`.

## Fail-closed validator

`scripts/validate_xprize_submission_contract.py` refuses final readiness unless:

```text
all required custom fields = EVIDENCED or NOT_APPLICABLE
all deliverable evidence classes = EVIDENCED or NOT_APPLICABLE
public project copy = CURRENT
authority.public_project_update = true
authority.final_submission_update = true
authority.devpost_submission = true
```

Evidence alone cannot create submission authority, and authority alone cannot substitute for missing runtime/business evidence.

## Critical current blockers

```text
judge repository share = UNVERIFIED
video = MISSING
live Google Cloud runtime proof = UNVERIFIED
live Gemini API call proof = MISSING
project-running evidence upload = MISSING
P&L upload = MISSING
revenue fields = UNRESOLVED
expense fields = UNRESOLVED
user/paying-user fields = UNRESOLVED
public project copy = STALE
final update/submission authority = false
```

## Synchronization rule

Do not edit the public Devpost copy to claim current Nexus V1 runtime behavior until the exact G5/G6/G7 receipts exist.

When those receipts exist:

```text
Nexus runtime receipts
→ claim/evidence matrix
→ Devpost field answers
→ redacted uploads
→ video
→ judge-access verification
→ public project synchronization
→ final submission authorization
→ submission receipt
```

## Authority boundary

This contract is read/validate only.

```text
public_project_update=false
final_submission_update=false
devpost_submission=false
external_action_performed=false
```
