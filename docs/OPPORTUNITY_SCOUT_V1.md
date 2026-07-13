# AIGC Opportunity Scout v1

Status: draft, local-only, read-only, operator-invoked.

## Purpose

Opportunity Scout reads public opportunity records through existing Phase 2 adapters, applies the existing AIGC classifier and radar scorer, filters rejected or prohibited records, and persists eligible records through the governed Quest Candidate application service.

It does not implement a second crawler, second candidate model, or second database.

```text
operator invocation
→ fixed repository-owned source configuration
→ existing Phase 2 read-only connector
→ normalized OpportunityRecord
→ classifier and radar scorer
→ reject prohibited / failed records
→ QuestCandidateApplicationService
→ schema validation
→ SQLite candidate and append-only audit evidence
→ Quest Board
```

## Local API

```text
POST /api/v1/opportunities/discover?limit=6
```

Default sources:

- `weworkremotely`;
- `remotive`.

A caller may select one or more reviewed sources with repeated query parameters:

```text
POST /api/v1/opportunities/discover?limit=6&source_id=weworkremotely&source_id=remotive
```

Currently allowlisted source IDs:

| Source ID | Connector | Interface |
|---|---|---|
| `weworkremotely` | `wwr_rss` | public RSS |
| `remotive` | `remotive` | public API |
| `remoteok` | `remoteok` | public API |
| `github` | `github_search` | public issue-search API |

The limit must be from 1 through 25 and applies to the final candidate selection. Each selected connector is also bounded to that per-source maximum.

## Source authority

The API caller cannot provide:

- a URL;
- an RSS address;
- an API endpoint;
- request headers;
- credentials;
- a connector implementation;
- an application instruction;
- a message or submission payload.

Source definitions come only from `config/phase2_sources.json`. A source must:

- be enabled;
- be classified green or yellow;
- use an allowlisted existing connector;
- require no API key or account registration;
- declare explicit forbidden actions;
- map to an existing Quest Candidate source identity.

Unknown, disabled, credentialed, or unreviewed sources fail closed.

## Candidate normalization

Opportunity Scout preserves available source facts and does not invent missing commercial terms.

Mapped fields include:

- stable candidate ID derived from the Phase 2 opportunity ID;
- direct source link;
- title and plain-text description;
- employer or client when present;
- location and remote state when present;
- detected skills and tools;
- domain derived from existing Phase 2 taxonomy;
- compensation only when supplied by the source;
- conservative risk class derived from existing findings;
- source rights class;
- `existing_read_only_adapter` ingestion evidence.

When compensation or deadline information is absent:

```text
budget_range = null
deadline_days = null
deadline_at = null
```

The Scout does not insert placeholder values such as `$500–$5,000` or `14 days`.

## Filtering

Every normalized record passes through the existing Phase 2:

- `Classifier`;
- `RadarScorer`;
- forbidden-signal rules;
- risk flags;
- fit scoring.

Records with a `REJECT` radar decision or forbidden flags are not persisted to the Quest Board.

This initial filtering does not replace later Ology Assessor, Risk Scout, compliance review, or accountable-operator qualification.

## Idempotency

Phase 2 opportunity identifiers are deterministic. Re-running discovery for the same unchanged posting recovers the existing Quest Candidate rather than creating a duplicate.

The response distinguishes:

- `new_candidates`;
- `existing_candidates`;
- source errors;
- ingestion errors;
- eligible and selected record counts.

## Failure behavior

One source failure does not discard successful results from another source. The response status becomes `partial` and includes the bounded source error.

When every requested source fails, the endpoint returns a structured upstream failure with an audited run report. It does not claim success or create placeholder candidates.

## Audit evidence

Each successful candidate ingestion already creates a `quest_candidate.ingested` event.

Every Scout run additionally appends an `opportunity_scout.completed` event containing only bounded summary evidence:

- run ID;
- selected source IDs;
- source count;
- assessed and eligible counts;
- new and existing candidate counts;
- error classes;
- whether public reads occurred;
- `external_action_performed: false`.

Raw postings and secret material are not copied into the Scout run-summary event.

## Quest Board

The local Quest Board includes an explicit **Read-only Opportunity Scout** control. It defaults to We Work Remotely and Remotive and allows the operator to select the other reviewed adapters.

Discovery is operator-invoked. It is not scheduled automatically by this implementation.

## Safety boundary

Opportunity Scout may:

- read fixed public feeds and APIs;
- normalize records;
- classify and score records;
- persist internal candidates;
- display them on the local Quest Board;
- write internal audit evidence.

Opportunity Scout may not:

- accept arbitrary URLs;
- crawl or scrape unapproved pages;
- use credentials;
- apply to jobs;
- bid;
- message employers or clients;
- submit proposals or deliverables;
- accept contracts or platform terms;
- purchase or pay;
- create accounts;
- invoke a write connector;
- authorize work acceptance;
- create external side effects.

```json
{
  "external_action_performed": false
}
```

## Validation

Focused tests use injected fake connectors and never call the public internet:

```powershell
python -m pytest tests/application/test_opportunity_scout.py tests/api/test_opportunity_scout_api.py
python -m pytest
```

Coverage includes:

- successful fixed-source discovery;
- classifier rejection of prohibited records;
- candidate persistence;
- idempotent replay;
- preservation of missing budget and deadline data;
- denial of unconfigured and credentialed sources;
- complete upstream failure evidence;
- API status mapping;
- Quest Board Scout controls;
- append-only Scout audit events.
