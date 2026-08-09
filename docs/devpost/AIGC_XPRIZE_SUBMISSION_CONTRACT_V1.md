# AIGC Build with Gemini XPRIZE Submission Contract V1

Status: `LIVE REQUIREMENTS SNAPSHOT — FINAL SUBMISSION BLOCKED`

## Purpose

Bind the current connected Devpost requirements to machine-readable AIGC evidence states so the public project page and final submission cannot outrun repository, runtime, business **or eligibility** evidence.

Requirements were re-fetched from the authenticated Devpost integration on 2026-08-09 at `2026-08-09T15:20:21Z`.

## Current challenge facts

```text
challenge = Build with Gemini XPRIZE
slug = xprize
submission_period_start = 2026-05-19 10:00 Pacific Time
submissions_end = 2026-08-17T20:00:00Z
host_timezone = Pacific Time (US & Canada)
current_phase = submissions_open
video_required = true
zip_file_required = true
website_required = false
```

Judging criteria:

```text
Business Viability
AI-Native Operations
Category Impact
```

## Independent eligibility gate

Final readiness now independently requires every applicable eligibility item to be resolved as `EVIDENCED` or `NOT_APPLICABLE`.

Tracked eligibility includes:

```text
new_project_after_submission_start
pre_existing_work_disclosure
entrant_type_and_representative
age_and_geographic_eligibility
organization_size_if_entering_as_organization
third_party_integration_rights
original_work_and_ip_rights
no_disqualifying_sponsor_or_administrator_support
```

This prevents a technically complete, financially evidenced, authority-approved submission from being declared ready while a competition-eligibility defect remains unresolved.

The new-project chronology and framework-reuse evidence are documented in:

```text
docs/devpost/AIGC_XPRIZE_PRE_EXISTING_RESOURCES_DISCLOSURE_V1.md
```

Current bounded chronology:

```text
Submission Period start = 2026-05-19
Earliest AIGC repository baseline observed in this audit = 2026-07-02
Dedicated governed Gemini PR #145 = created 2026-07-27
Representative Gemini workflow/canary/Devpost paths = absent at PR #145 base, present at head
```

This supports a post-start competition-specific Gemini build using disclosed AIGC framework foundations, but Sponsor/Administrator eligibility remains externally determinative and the final Entrant start-date declaration remains reviewable.

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

- resolved entrant/project eligibility;
- GitHub repository access for the specified judge/testing accounts;
- three-minute demonstration video;
- required submission ZIP archive;
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

The exact eligibility states, required field IDs and deliverable states are versioned in `config/xprize_submission_contract.json`.

## Fail-closed validator

`scripts/validate_xprize_submission_contract.py` refuses final readiness unless:

```text
all applicable eligibility items = EVIDENCED or NOT_APPLICABLE
all required custom fields = EVIDENCED or NOT_APPLICABLE
all deliverable evidence classes = EVIDENCED or NOT_APPLICABLE
required submission ZIP = EVIDENCED
public project copy = CURRENT
authority.public_project_update = true
authority.final_submission_update = true
authority.devpost_submission = true
```

Neither evidence nor authority can bypass unresolved eligibility.

## Critical current blockers

```text
new-project eligibility = STRONG_PARTIAL / NOT FINAL
pre-existing-work disclosure = PARTIAL
entrant type / representative = UNRESOLVED
age/geographic eligibility = UNRESOLVED
IP / third-party rights = UNVERIFIED
sponsor-support conflict check = UNVERIFIED
judge repository share = UNVERIFIED
video = MISSING
submission ZIP = MISSING
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

Do not edit the public Devpost copy to claim current Nexus V1 runtime behavior until the exact G5/G6/G7 receipts exist. Do not submit while eligibility remains unresolved even if runtime evidence later passes.

When those receipts and eligibility evidence exist:

```text
eligibility closeout
+
Nexus runtime receipts
→ claim/evidence matrix
→ Devpost field answers
→ redacted uploads
→ submission ZIP
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
